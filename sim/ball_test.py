import math

import pytest

from sim.ball import Ball


def test_step_moves_without_bounce():
    ball = Ball(width=100, height=80, x=20, y=30, vx=50, vy=-20, radius=10)
    ball.move(0.1)
    assert ball.position() == (25, 28)
    assert ball.velocity() == (50, -20)


@pytest.mark.parametrize(
    ("x", "y", "vx", "vy", "want_pos", "want_velocity"),
    [
        (15, 50, -100, 0, (15, 50), (100, 0)),
        (85, 50, 100, 0, (85, 50), (-100, 0)),
        (50, 15, 0, -100, (50, 15), (0, 100)),
        (50, 85, 0, 100, (50, 85), (0, -100)),
        (12, 12, -100, -100, (18, 18), (100, 100)),
    ],
)
def test_step_bounces_off_each_wall(x, y, vx, vy, want_pos, want_velocity):
    ball = Ball(width=100, height=100, x=x, y=y, vx=vx, vy=vy, radius=10)
    ball.move(0.1)
    assert ball.position() == want_pos
    assert ball.velocity() == want_velocity


def test_step_is_deterministic():
    def run():
        ball = Ball(width=640, height=480, x=40, y=50, vx=180, vy=140, radius=30)
        for _ in range(300):
            ball.move(1 / 30)
        return ball.position()

    assert run() == run()
    x, y = run()
    assert 30 <= x <= 610 and 30 <= y <= 450


def test_step_rejects_a_tunneling_move():
    ball = Ball(width=100, height=100, x=50, y=50, vx=10000, vy=0, radius=10)
    with pytest.raises(ValueError):
        ball.move(0.1)
    assert ball.position() == (50, 50)


def test_new_rejects_bad_config():
    bad = [
        dict(radius=0),
        dict(width=20, x=10),
        dict(x=5),
        dict(vx=math.nan),
    ]
    base = dict(width=100, height=100, x=50, y=50, vx=0, vy=0, radius=10)
    for overrides in bad:
        kwargs = dict(base)
        kwargs.update(overrides)
        with pytest.raises(ValueError):
            Ball(**kwargs)