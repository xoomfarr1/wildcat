"""Pure-Python sparkle-particle engine for the Wildcat connection bar.

No Qt / no I/O, so it is unit-testable headless (see ``tests/test_sparkle.py``).
The Qt renderer lives in :mod:`wildcat.gui.sparkle`.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

#: Particles alive in the bar at once.
DEFAULT_COUNT = 18
#: Target animation cadence.
FPS = 30
DT = 1.0 / FPS


@dataclass
class Particle:
    """One glitter mote: position, drift velocity, size, twinkle phase."""

    x: float
    y: float
    vx: float
    vy: float
    size: float
    phase: float


def make_particle(width: float, height: float, rng: random.Random) -> Particle:
    """A single sparkle somewhere in the bar, drifting at twinkle speed."""
    margin = 2.0
    return Particle(
        x=rng.uniform(margin, max(margin, width - margin)),
        y=rng.uniform(margin, max(margin, height - margin)),
        vx=rng.uniform(-10.0, 10.0),
        vy=rng.uniform(-8.0, 8.0),
        size=rng.uniform(1.0, 2.6),
        phase=rng.uniform(0.0, math.tau),
    )


def init_particles(
    count: int, width: float, height: float, rng: random.Random
) -> list[Particle]:
    """Seed ``count`` particles inside a ``(width, height)`` bar."""
    return [make_particle(width, height, rng) for _ in range(count)]


def alpha_at(phase: float, t: float) -> float:
    """Twinkle opacity in [0.1, 0.9] (slow fade in/out, driven by wall time)."""
    a = 0.4 + 0.35 * math.sin(t * 1.3 + phase)
    return max(0.1, min(0.9, a))


def step(
    particles: list[Particle],
    t: float,
    dt: float,
    width: float,
    height: float,
    rng: random.Random,
    count: int | None = None,
) -> list[Particle]:
    """Advance one frame. Particles that drift off-screen are respawned in-bounds.

    The returned list always has exactly ``count`` entries (defaults to the input
    count) so the renderer can iterate with a stable length. Seeded ``rng`` makes
    the simulation deterministic.
    """
    if count is None:
        count = len(particles)
    margin = 4.0
    nxt: list[Particle] = []
    for p in particles:
        x = p.x + p.vx * dt
        y = p.y + p.vy * dt
        if x < -margin or x > width + margin or y < -margin or y > height + margin:
            nxt.append(make_particle(width, height, rng))
        else:
            nxt.append(Particle(x, y, p.vx, p.vy, p.size, p.phase))
    while len(nxt) < count:
        nxt.append(make_particle(width, height, rng))
    return nxt[:count]
