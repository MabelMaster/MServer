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

async function start() {
  const pc = new RTCPeerConnection();
  pc.addTransceiver("video", { direction: "recvonly" });
  pc.addEventListener("connectionstatechange", () => {
    status.textContent = pc.connectionState;
  });

  await pc.setLocalDescription(await pc.createOffer());
  await waitUntilGathered(pc);

  const transport = new WebTransport("https://localhost:4433/wt");
  await transport.ready;
  const stream = await transport.createBidirectionalStream();
  const writer = stream.writable.getWriter();
  await writer.write(new TextEncoder().encode(JSON.stringify({
    type: "offer",
    sdp: pc.localDescription.sdp,
  }) + "\n"));

  const answer = await readLine(stream.readable.getReader());
  if (answer.type !== "answer") throw new Error(answer.error || "no answer");
  await pc.setRemoteDescription(answer);
}

start().catch((error) => {
  status.textContent = error.message;
});