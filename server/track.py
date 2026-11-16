from aiortc import VideoStreamTrack
from av import VideoFrame

from sim.ball import Ball
from sim.frame import render


class BallTrack(VideoStreamTrack):
    def __init__(self, on_frame):
        super().__init__()
        self.ball = Ball(x=40, y=50, vx=180, vy=140, radius=30, width=640, height=480)
        self.on_frame = on_frame
        self.index = 0

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        self.ball.move(1 / 30)
        x, y = self.ball.position()
        try:
            self.on_frame(self.index, x, y)
        except Exception:
            pass
        self.index += 1
        frame = VideoFrame.from_ndarray(render(self.ball), format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame