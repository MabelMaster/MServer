import numpy as np

from sim.ball import Ball
from sim.frame import render,detect_center

WHITE = [255, 255, 255]
BLACK = [0, 0, 0]


def test_render_shape_and_corners():
    ball = Ball(x=20, y=30, vx=0, vy=0, radius=10, width=100, height=80)
    frame = render(ball)
    assert frame.shape == (80, 100, 3)
    assert frame.dtype == np.uint8
    assert frame[0, 0].tolist() == BLACK
    assert frame[0, -1].tolist() == BLACK
    assert frame[-1, 0].tolist() == BLACK
    assert frame[-1, -1].tolist() == BLACK


def test_render_paints_the_center_white():
    ball = Ball(x=20, y=30, vx=0, vy=0, radius=10, width=100, height=80)
    frame = render(ball)
    assert frame[30, 20].tolist() == WHITE


def test_white_pixel_follows_the_ball():
    ball = Ball(x=30, y=50, vx=200, vy=0, radius=10, width=100, height=100)
    before = render(ball)
    assert before[50, 30].tolist() == WHITE
    ball.move(0.1)
    after = render(ball)
    assert after[50, 30].tolist() == BLACK
    assert after[50, 50].tolist() == WHITE

def test_detect_center_matches_the_ball():
    ball = Ball(x=50, y=60, vx=0, vy=0, radius=30, width=200, height=160)
    detected = detect_center(render(ball))
    assert detected is not None
    x, y = detected
    assert abs(x - 50) < 1 and abs(y - 60) < 1