import argparse
import asyncio
import errno
import json
import signal
from pathlib import Path

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import HeadersReceived, WebTransportStreamDataReceived
from aioquic.quic.configuration import QuicConfiguration
from aiortc import RTCPeerConnection, RTCSessionDescription
from server.signaling import advertise_host, answer_message, listen_hosts, parse_message, truth_message
from server.static import read_asset
from server.track import BallTrack

ROOT = Path(__file__).resolve().parents[1] / "web"
PEERS = set()
ADVERTISE = ""
ICE_PORT = 0


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
            asyncio.create_task(self._answer(event.stream_id, event.session_id, line.decode()))

    async def _answer(self, stream_id, session_id, line):
        pc = RTCPeerConnection()
        PEERS.add(pc)
        try:
            offer = parse_message(line)
            await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type="offer"))
            # The track starts during setLocalDescription, before the answer is
            # written. Hold ground truth until that answer line is on the stream.
            queued = []
            gate = {"open": False}

            def publish(index, x, y):
                payload = truth_message(index, x, y)
                if not gate["open"]:
                    queued.append(payload)
                    return
                self._quic.send_stream_data(stream_id, payload)
                self.transmit()

            pc.addTrack(BallTrack(publish))
            async with pinned_ice_port(ICE_PORT):
                await pc.setLocalDescription(await pc.createAnswer())
                while pc.iceGatheringState != "complete":
                    await asyncio.sleep(0.05)
            sdp = pc.localDescription.sdp
            if ADVERTISE:
                sdp = advertise_host(sdp, ADVERTISE)
            payload = answer_message(sdp)
        except Exception as exc:
            payload = (json.dumps({"type": "error", "error": str(exc)}) + "\n").encode()
            queued = None
        self._quic.send_stream_data(stream_id, payload)
        if queued is not None:
            gate["open"] = True
            for item in queued:
                self._quic.send_stream_data(stream_id, item)
        self.transmit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", default="certs/cert.pem")
    parser.add_argument("--key", default="certs/key.pem")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--advertise", default="", help="address written into ICE candidates")
    parser.add_argument("--ice-port", type=int, default=0, help="fixed UDP port for the media socket")
    args = parser.parse_args()

    global ADVERTISE, ICE_PORT
    ADVERTISE = args.advertise
    ICE_PORT = args.ice_port

    configuration = QuicConfiguration(alpn_protocols=H3_ALPN, is_client=False,max_datagram_frame_size=65536)
    configuration.load_cert_chain(args.cert, args.key)

    async def run():
        servers = []
        for host in listen_hosts(args.host):
            try:
                servers.append(await serve(
                    host,
                    args.port,
                    configuration=configuration,
                    create_protocol=HttpServerProtocol,
                ))
            except OSError as exc:
                if servers and exc.errno in (errno.EADDRINUSE, errno.EAFNOSUPPORT):
                    continue
                raise
        print(f"https://localhost:{args.port}")
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await stop.wait()
        for pc in list(PEERS):
            await pc.close()
        for server in servers:
            server.close()

    asyncio.run(run())


class _PinnedIce:
    def __init__(self, port):
        self.port = port
        self.loop = None
        self.original = None
        self.used = False

    async def __aenter__(self):
        if not self.port:
            return
        self.loop = asyncio.get_running_loop()
        self.original = self.loop.create_datagram_endpoint

        async def patched(protocol_factory, local_addr=None, *args, **kwargs):
            if local_addr is not None and local_addr[1] == 0:
                if self.used:
                    raise OSError(errno.EADDRINUSE, "ice port already bound")
                local_addr = ("0.0.0.0", self.port)
                self.used = True
            return await self.original(protocol_factory, local_addr, *args, **kwargs)

        self.loop.create_datagram_endpoint = patched

    async def __aexit__(self, exc_type, exc, tb):
        if self.original is not None:
            self.loop.create_datagram_endpoint = self.original


def pinned_ice_port(port):
    return _PinnedIce(port)


if __name__ == "__main__":
    main()