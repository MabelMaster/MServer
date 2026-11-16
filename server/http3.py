import argparse
import asyncio
import json
from pathlib import Path

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration
from aiortc import RTCPeerConnection, RTCSessionDescription
from server.signaling import answer_message, parse_message
from server.static import read_asset

ROOT = Path(__file__).resolve().parents[1] / "web"


class HttpServerProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._http = H3Connection(self._quic, enable_webtransport=True)
        self._buffers = {}

    def quic_event_received(self, event):
        for http_event in self._http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                self._handle_headers(http_event)
            elif isinstance(http_event, WebTransportStreamDataReceived):
                self._handle_stream(http_event)
        self.transmit()

    def _handle_headers(self, event):
        headers = {name: value for name, value in event.headers}
        method = headers.get(b":method", b"GET").decode()
        path = headers.get(b":path", b"/").decode()
        protocol = headers.get(b":protocol", b"").decode()
        if method == "CONNECT" and protocol == "webtransport" and path.split("?", 1)[0] == "/wt":
            self._http.send_headers(event.stream_id, [
                (b":status", b"200"),
                (b"sec-webtransport-http3-draft", b"draft02"),
            ])
            return
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

    def _handle_stream(self, event):
        buffer = self._buffers.setdefault(event.stream_id, bytearray())
        buffer.extend(event.data)
        while b"\n" in buffer:
            line, _, rest = bytes(buffer).partition(b"\n")
            self._buffers[event.stream_id] = bytearray(rest)
            buffer = self._buffers[event.stream_id]
            asyncio.create_task(self._answer(event.stream_id, line.decode()))

    async def _answer(self, stream_id, line):
        pc = RTCPeerConnection()
        try:
            offer = parse_message(line)
            await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type="offer"))
            await pc.setLocalDescription(await pc.createAnswer())
            while pc.iceGatheringState != "complete":
                await asyncio.sleep(0.05)
            payload = answer_message(pc.localDescription.sdp)
        except Exception as exc:
            payload = (json.dumps({"type": "error", "error": str(exc)}) + "\n").encode()
        self._quic.send_stream_data(stream_id, payload)
        self.transmit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default="certs/cert.pem")
    parser.add_argument("--key", default="certs/key.pem")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    args = parser.parse_args()

    configuration = QuicConfiguration(alpn_protocols=H3_ALPN, is_client=False,max_datagram_frame_size=65536)
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