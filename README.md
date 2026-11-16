# MServer

A small HTTP/3 page that plays a synthetic bouncing ball over WebRTC and prints how far the detected center is from the server's ground truth.

Developed on macOS. Graders on Linux can run the same Python server, tests, and Dockerfile.

## Run locally

```sh
python3 -m venv Mserver
source Mserver/bin/activate
pip install -e ".[dev]"
./scripts/gen_certs.sh
python -m server.http3
```

`gen_certs.sh` writes `certs/cert.pem` and `certs/key.pem`, and prints the SPKI SHA-256 of the certificate. Quit Chrome with Command+Q, then start it with that hash:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir=/tmp/mserver-chrome \
  --origin-to-force-quic-on=localhost:4433 \
  --ignore-certificate-errors-spki-list=THE_HASH \
  https://localhost:4433
```

The server listens on `127.0.0.1` and `::1`, because Chrome resolves `localhost` to IPv6 first and will not fall back when QUIC is forced. Regenerating the certificate changes the hash.

SIGINT and SIGTERM both stop the process: open peer connections are closed, then the UDP sockets.

## Docker

Certificates stay on the host and are mounted in. The image does not contain a private key.

```sh
docker build -t mserver .
docker run --rm \
  -p 4433:4433/udp \
  -p 50000:50000/udp \
  -v "$PWD/certs:/certs:ro" \
  mserver
```

Use the same Chrome command as above. `docker stop` sends SIGTERM, which the process handles.

Inside the container the media socket is pinned to UDP 50000 and the answer's host candidates are rewritten to `127.0.0.1`. aiortc has no shared UDP mux, and Docker Desktop on macOS has no host network, so a fixed published port is how the browser reaches the video. One media port means one viewer at a time.

## Message flow

1. The browser loads `GET /` over HTTP/3.
2. It creates a recvonly video offer and waits until ICE gathering finishes. Candidates are in the SDP; there is no trickle.
3. It opens one WebTransport session at `/wt`, then one bidirectional stream.
4. Each message is one JSON object followed by a newline.
5. The browser writes `{"type":"offer","sdp":"..."}`.
6. The server adds the ball track, creates the answer, and gathers its own candidates. The track starts producing frames during `setLocalDescription`, before the answer is written, so ground-truth lines are held until the answer line is on the stream.
7. The server writes `{"type":"answer","sdp":"..."}`, then one ground-truth line per frame: `{"t": milliseconds, "x": center, "y": center, "frame": index}`.
8. The browser sets the remote description and plays the track. For each presented frame it subtracts the first frame's RTP timestamp, divides by 3000 (90 kHz / 30 fps), and uses that as the frame index.

`t` is the media time of that frame. `x` and `y` are the ball center after moving one thirtieth of a second, which is the same position drawn into the frame. The origin is the top-left corner.

## Design

The ball lives in `sim/`. Each step reflects at most once per axis, and a step that would tunnel through a wall is rejected so the previous position stays. `sim/frame.py` paints a white disk on black. A pixel is inside the disk when its center is within the radius, and detection uses that same center.

`server/track.py` moves the ball once per frame and hands the bitmap to aiortc, which encodes it. The browser finds the white pixels and averages their centers. The page shows the distance between that point and the ground truth for the same frame index.

Signaling and ground truth share the WebTransport stream because a server-opened unidirectional stream did not survive in this Chrome. The answer is always the first line so the video negotiation is not parsed as a position update.

## Tradeoffs

1. Ground truth goes on the reliable stream instead of a datagram. A lost datagram would make that frame unscorable, and the stream keeps the answer ahead of the positions.
2. The frame index comes from the RTP timestamp, not from when the frame arrives. Encoding and the network add delay, so arrival time does not identify the drawn position.
3. The picture is generated in process and encoded by aiortc's VP8 encoder. There is no media file to seek.
4. Host ICE candidates are enough on one machine. The Docker path rewrites them and publishes a single UDP port rather than pretending the container's address is reachable from the browser.
