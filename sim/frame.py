import numpy as np

def render(ball):
    height = int(ball.arena.height)
    width = int(ball.arena.width)
    cx,cy=ball.position()
    row,col=np.ogrid[0:height,0:width]
    dist_sq=(col+0.5-cx)**2+(row+0.5-cy)**2
    ball_pixels=dist_sq<=ball.radius**2
    frame=np.zeros((height,width,3),dtype=np.uint8)
    frame[ball_pixels]=255
    return frame

def detect_center(frame):
    white = frame[:, :, 0] > 200
    rows, cols = np.nonzero(white)
    if len(cols) == 0:
        return None
    return float((cols + 0.5).mean()), float((rows + 0.5).mean())