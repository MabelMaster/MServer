from pathlib import Path

import av
import numpy as np

# RGB purple. Frames are BGR, so the stored order is reversed.
BACKGROUND_RGB = (110, 62, 144)
BACKGROUND = np.array([BACKGROUND_RGB[2], BACKGROUND_RGB[1], BACKGROUND_RGB[0]], dtype=np.uint8)
SPRITE_PATH = Path(__file__).resolve().parents[1] / "materials" / "tuxedocat.jpg"

_sprite = None
_sprite_radius = None


def _load_sprite():
    global _sprite, _sprite_radius
    if _sprite is not None:
        return _sprite, _sprite_radius
    with av.open(str(SPRITE_PATH)) as container:
        image = next(container.decode(video=0)).to_ndarray(format="bgr24")
    rgb = image[:, :, ::-1].astype(np.int16)
    painted = np.abs(rgb - 255).sum(axis=2) > 30
    ys, xs = np.nonzero(painted)
    height, width = image.shape[:2]
    center_y = (height - 1) / 2
    center_x = (width - 1) / 2
    _sprite = image
    _sprite_radius = float(np.hypot(xs - center_x, ys - center_y).max() * 0.96)
    return _sprite, _sprite_radius


def render(ball):
    height = int(ball.arena.height)
    width = int(ball.arena.width)
    frame = np.empty((height, width, 3), dtype=np.uint8)
    frame[:] = BACKGROUND
    cx, cy = ball.position()
    row, col = np.ogrid[0:height, 0:width]
    dist_sq = (col + 0.5 - cx) ** 2 + (row + 0.5 - cy) ** 2
    ball_pixels = dist_sq <= ball.radius ** 2
    sprite, source_radius = _load_sprite()
    sprite_height, sprite_width = sprite.shape[:2]
    scale = source_radius / ball.radius
    sample_y = (row + 0.5 - cy) * scale + (sprite_height - 1) / 2
    sample_x = (col + 0.5 - cx) * scale + (sprite_width - 1) / 2
    sample_y = np.clip(np.rint(sample_y), 0, sprite_height - 1).astype(np.int32)
    sample_x = np.clip(np.rint(sample_x), 0, sprite_width - 1).astype(np.int32)
    frame[ball_pixels] = sprite[sample_y, sample_x][ball_pixels]
    return frame


def detect_center(frame):
    difference = np.abs(frame.astype(np.int16) - BACKGROUND.astype(np.int16)).sum(axis=2)
    rows, cols = np.nonzero(difference > 80)
    if len(cols) == 0:
        return None
    return float((cols + 0.5).mean()), float((rows + 0.5).mean())
