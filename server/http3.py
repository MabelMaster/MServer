import argparse
import asyncio
from pathlib import Path

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived
from aioquic.quic.configuration import QuicConfiguration

from server.static import read_asset

ROOT = Path(__file__).resolve().parents[1] / "web"


class HttpServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = H3Connection(self._quic)

    def quic_event_received(self, event):
        for http_event in self._http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                self._handle_headers(http_event)
        self.transmit()

    def _handle_headers(self, event):
        headers = {name: value for name, value in event.headers}
        method = headers.get(b":method", b"GET").decode()
        path = headers.get(b":path", b"/").decode()
        if method != "GET":
            self._reply(event.stream_id, 405, b"method not allowed", "text/plain; charset=utf-8")
            return
        try:
            body, content_type = read_asset(ROOT, path)
            self._reply(event.stream_id, 200, body, content_type)
        except PermissionError:
            self._reply(event.stream_id, 403, b"forbidden", "text/plain; charset=utf-8")
        except FileNotFoundError:
            self._reply(event.stream_id, 404, b"not found", "text/plain; charset=utf-8")

    def _reply(self, stream_id, status, body, content_type):
        self._http.send_headers(
            stream_id,
            [
                (b":status", str(status).encode()),
                (b"content-type", content_type.encode()),
                (b"content-length", str(len(body)).encode()),
            ],
        )
        self._http.send_data(stream_id, body, end_stream=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default="certs/cert.pem")
    parser.add_argument("--key", default="certs/key.pem")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    args = parser.parse_args()

    configuration = QuicConfiguration(alpn_protocols=H3_ALPN, is_client=False)
    configuration.load_cert_chain(args.cert, args.key)

    async def run():
        for host in ("127.0.0.1", "::1"):
            await serve(
                host,
                args.port,
                configuration=configuration,
                create_protocol=HttpServerProtocol,
            )
        print(f"https://localhost:{args.port}")
        await asyncio.Future()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()