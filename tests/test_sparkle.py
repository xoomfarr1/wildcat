from __future__ import annotations

import math
import random

from wildcat.gui.sparkle_logic import (
    DEFAULT_COUNT,
    Particle,
    alpha_at,
    init_particles,
    make_particle,
    step,
)


def test_init_particles_in_bounds():
    rng = random.Random(0)
    ps = init_particles(10, 360, 28, rng)
    assert len(ps) == 10
    for p in ps:
        assert 0 <= p.x <= 360
        assert 0 <= p.y <= 28
        assert 1.0 <= p.size <= 2.6
        assert 0.0 <= p.phase <= math.tau


def test_alpha_is_bounded_twinkle():
    rng = random.Random(1)
    p = make_particle(360, 28, rng)
    for t in (0.0, 0.3, 1.0, 2.5, 5.0):
        assert 0.1 <= alpha_at(p.phase, t) <= 0.9


def test_alpha_oscillates_with_time():
    rng = random.Random(2)
    p = make_particle(360, 28, rng)
    a0 = alpha_at(p.phase, 0.0)
    a1 = alpha_at(p.phase, 0.0 + math.pi / 1.3)
    # half a period later the sine flips sign -> the value changes.
    assert a0 != a1


def test_step_advances_positions():
    rng = random.Random(3)
    ps = init_particles(DEFAULT_COUNT, 360, 28, rng)
    ps2 = step(ps, 1.0, 1 / 30, 360, 28, rng)
    assert len(ps2) == DEFAULT_COUNT
    moved = sum(1 for a, b in zip(ps, ps2) if a.x != b.x or a.y != b.y)
    assert moved > 0


def test_step_dt_zero_keeps_positions():
    rng = random.Random(4)
    ps = init_particles(8, 360, 28, rng)
    ps2 = step(ps, 1.0, 0.0, 360, 28, rng)
    for a, b in zip(ps, ps2):
        assert a.x == b.x and a.y == b.y


def test_step_respawns_offscreen_particles():
    rng = random.Random(5)
    ps = init_particles(10, 360, 28, rng)
    ps[0] = Particle(-1000.0, -1000.0, 0.0, 0.0, 1.5, 0.0)
    ps2 = step(ps, 1.0, 1 / 30, 360, 28, rng)
    assert len(ps2) == 10
    # the off-screen mote is replaced with one inside the bar.
    assert 0 <= ps2[0].x <= 360
    assert 0 <= ps2[0].y <= 28


def test_step_is_deterministic_with_seed():
    rng1, rng2 = random.Random(42), random.Random(42)
    ps1 = init_particles(10, 360, 28, rng1)
    ps2 = init_particles(10, 360, 28, rng2)
    out1 = step(ps1, 1.0, 1 / 30, 360, 28, rng1)
    out2 = step(ps2, 1.0, 1 / 30, 360, 28, rng2)
    for a, b in zip(out1, out2):
        assert a.x == b.x and a.y == b.y and a.size == b.size
