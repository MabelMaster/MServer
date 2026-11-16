const status = document.querySelector("#status");

function waitUntilGathered(pc) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    pc.addEventListener("icegatheringstatechange", () => {
      if (pc.iceGatheringState === "complete") resolve();
    });
  });
}

async function readLine(reader) {
  const decoder = new TextDecoder();
  let buffer = "";
  while (!buffer.includes("\n")) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
  }
  return JSON.parse(buffer.split("\n")[0]);
}

const errorText = document.querySelector("#error");
const truths = new Map();

function detectBall(video) {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) return null;
  const canvas = detectBall.canvas || (detectBall.canvas = document.createElement("canvas"));
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(video, 0, 0, width, height);
  const pixels = context.getImageData(0, 0, width, height).data;
  let sumX = 0;
  let sumY = 0;
  let count = 0;
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      if (pixels[(row * width + col) * 4] > 200) {
        sumX += col + 0.5;
        sumY += row + 0.5;
        count += 1;
      }
    }
  }
  if (!count) return null;
  return { x: sumX / count, y: sumY / count };
}

function frameIndex(rtpTimestamp, origin) {
  return Math.round((((rtpTimestamp - origin) >>> 0) / 3000));
}



function watchFrames(video) {
  let origin = null;
  const onFrame = (now, metadata) => {
    try {
      if (origin === null) origin = metadata.rtpTimestamp;
      const frame = frameIndex(metadata.rtpTimestamp, origin);
      const detected = detectBall(video);
      const truth = truths.get(frame);
      if (detected && truth) {
        const error = Math.hypot(detected.x - truth.x, detected.y - truth.y);
        errorText.textContent = `frame ${frame} error ${error.toFixed(2)}`;
      } else {
        errorText.textContent = `frame ${frame} ${video.videoWidth}x${video.videoHeight}`;
      }
    } catch (error) {
      errorText.textContent = error.message;
    }
    video.requestVideoFrameCallback(onFrame);
  };
  video.requestVideoFrameCallback(onFrame);
}

function watchStats(pc, video) {
  setInterval(async () => {
    let packets = 0;
    let decoded = 0;
    const stats = await pc.getStats();
    stats.forEach((report) => {
      if (report.type === "inbound-rtp" && report.kind === "video") {
        packets = report.packetsReceived || 0;
        decoded = report.framesDecoded || 0;
      }
    });
    status.textContent = `${pc.connectionState} rx ${packets} decoded ${decoded} ${video.videoWidth}x${video.videoHeight}`;
  }, 500);
}

async function start() {
  const pc = new RTCPeerConnection();
  const video = document.querySelector("video");
  pc.addEventListener("track", (event) => {
    const remote = event.streams[0];
    video.srcObject = remote && remote.getTracks().includes(event.track)
      ? remote
      : new MediaStream([event.track]);
    video.muted = true;
    const play = () => video.play().catch((error) => {
      errorText.textContent = `play ${error.message}`;
    });
    event.track.onunmute = play;
    play();
    errorText.textContent = `track ${event.track.readyState}`;
    watchFrames(video);
  });
  pc.addTransceiver("video", { direction: "recvonly" });
  pc.addEventListener("connectionstatechange", () => {
    status.textContent = pc.connectionState;
  });
  watchStats(pc, video);

  await pc.setLocalDescription(await pc.createOffer());
  await waitUntilGathered(pc);

  const transport = new WebTransport("https://localhost:4433/wt");
  await transport.ready;
  const stream = await transport.createBidirectionalStream();
  const writer = stream.writable.getWriter();
  const reader = stream.readable.getReader();
  await writer.write(new TextEncoder().encode(JSON.stringify({
    type: "offer",
    sdp: pc.localDescription.sdp,
  }) + "\n"));
  
  const decoder = new TextDecoder();
  let buffer = "";
  let answered = false;
  while (true) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      const message = JSON.parse(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf("\n");
      if (message.type === "answer" && !answered) {
        answered = true;
        await pc.setRemoteDescription(message);
        await new Promise((resolve) => setTimeout(resolve, 0));
        continue;
      }
      if (message.frame !== undefined) {
        truths.set(message.frame, message);
        continue;
      }
      if (!answered) throw new Error(message.error || "no answer");
    }
  }
}

start().catch((error) => {
  status.textContent = error.message;
});