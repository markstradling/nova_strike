"""Enemy obstacle avoidance.

Each frame an enemy looks LOOKAHEAD seconds ahead and predicts when and where it will meet each
obstacle, allowing for obstacles that scroll faster than it does and so catch it from behind.
From that it picks a plan:

* girder walls: head sideways for the nearest gap it fits through (where a sliding gap will be),
  slowing down or speeding up if that's what it takes to get there before the wall does
* laser gates: pick a speed so it crosses while the beam is off
* asteroids, mines and spinners: sidestep towards whichever side has more room

The plan is only a wish: an enemy steers at its own agility, so a sluggish heavy may not make it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING

from . import config as cfg
from .gfx import clamp
from .obstacles import Asteroid, LaserGate, Mine, Spinner, Wall

if TYPE_CHECKING:
    from .enemies import Enemy
    from .obstacles import Hazard

LOOKAHEAD = 1.6  # seconds ahead an enemy watches for obstacles
PLAN_HORIZON = 4.0  # seconds ahead it considers when working out how to get past one
MARGIN = 8  # extra clearance kept from obstacles, px
SPEED_OPTIONS = (1.0, 0.6, 1.4, 0.3, 1.8)  # speed scales the planner may choose, most preferred first
GATE_SAMPLE = 0.05  # how finely a gate crossing is checked, seconds


@dataclass(frozen=True)
class Track:
    """Something moving straight down the screen: centre y, downward speed and height."""

    y: float
    speed: float
    height: float


@dataclass
class Plan:
    target_x: float | None = None  # where to steer sideways; None means fly normally
    speed_scale: float = 1.0
    reason: str = ""  # what the enemy is avoiding, for debugging and tests


def crossing_window(me: Track, other: Track, horizon: float = LOOKAHEAD) -> tuple[float, float] | None:
    """When, within [0, horizon] seconds, two tracks overlap vertically: (start, end), or None."""
    gap, closing, reach = other.y - me.y, other.speed - me.speed, (me.height + other.height) / 2
    if abs(closing) < 1e-9:
        return (0.0, horizon) if abs(gap) < reach else None
    t1, t2 = (-reach - gap) / closing, (reach - gap) / closing
    start, end = max(min(t1, t2), 0.0), min(max(t1, t2), horizon)
    return (start, end) if start <= end else None


def plan_route(enemy: Enemy, walls: Sequence[Wall], hazards: Sequence[Hazard], asteroids: Sequence[Asteroid]) -> Plan:
    """Choose how the enemy should fly for the next moment to stay clear of obstacles."""
    height, half = _footprint(enemy)
    gates = [h for h in hazards if isinstance(h, LaserGate)]
    wall = _gap_target(enemy.x, Track(enemy.y, enemy.speed, height), half, walls)
    if wall is None:
        return _open_flight(enemy, gates, hazards, asteroids)
    return _get_through_wall(enemy, gates, walls) or Plan(target_x=wall[0], reason="wall")


def _footprint(enemy: Enemy) -> tuple[float, float]:
    """The enemy's collision height, and the half-width it needs clear including a safety margin."""
    box = enemy.hitbox()
    return box.height, box.width / 2 + MARGIN


def _open_flight(
    enemy: Enemy, gates: Sequence[LaserGate], hazards: Sequence[Hazard], asteroids: Sequence[Asteroid]
) -> Plan:
    """No wall in the way: time any laser gates, and sidestep smaller obstacles."""
    height, half = _footprint(enemy)
    scale = next(
        (s for s in SPEED_OPTIONS if _gates_safe(Track(enemy.y, enemy.speed * s, height), gates)),
        1.0,
    )
    plan = Plan(speed_scale=scale, reason="gate" if scale != 1.0 else "")
    dodge = _dodge_target(enemy.x, Track(enemy.y, enemy.speed * scale, height), half, hazards, asteroids)
    if dodge is not None:
        plan.target_x, plan.reason = dodge
    return plan


def _get_through_wall(enemy: Enemy, gates: Sequence[LaserGate], walls: Sequence[Wall]) -> Plan | None:
    """A wall is coming: find a speed at which the gap can be reached before it arrives.

    Slowing down buys time when the enemy is closing on a wall below; speeding up does when a
    faster-scrolling wall is catching it from above. The most preferred speed that works wins; if
    none does, the one that buys the most time. Returns None if no speed is safe through the gates.
    """
    height, half = _footprint(enemy)
    best: tuple[float, Plan] | None = None
    for scale in SPEED_OPTIONS:
        track = Track(enemy.y, enemy.speed * scale, height)
        if not _gates_safe(track, gates, PLAN_HORIZON):
            continue
        wall = _gap_target(enemy.x, track, half, walls, PLAN_HORIZON)
        if wall is None:  # at this speed the wall isn't met for a good while
            return Plan(speed_scale=scale, reason="wall")
        target, impact = wall
        plan = Plan(target_x=target, speed_scale=scale, reason="wall")
        if abs(target - enemy.x) <= enemy.agility * impact:
            return plan
        if best is None or impact > best[0]:
            best = (impact, plan)
    return best[1] if best else None


def _gates_safe(me: Track, gates: Sequence[LaserGate], horizon: float = LOOKAHEAD) -> bool:
    """Whether every laser gate ahead will be off for the whole time this track crosses it."""
    for gate in gates:
        window = crossing_window(me, Track(gate.y, gate.speed, 8), horizon)
        if window is None:
            continue
        t = window[0]
        while t <= window[1]:
            if gate.state(ahead=t) != "off":
                return False
            t += GATE_SAMPLE
    return True


def _gap_target(
    x: float, me: Track, half: float, walls: Sequence[Wall], horizon: float = LOOKAHEAD
) -> tuple[float, float] | None:
    """For the soonest wall the enemy would hit: (nearest x where it fits through a gap, seconds until impact)."""
    soonest: tuple[float, float] | None = None
    for wall in walls:
        window = crossing_window(me, Track(wall.y + wall.H / 2, wall.speed, wall.H), horizon)
        if window is None or (soonest and window[0] >= soonest[0]):
            continue
        segments = wall.segments_at(window[0])
        if not any(a - half < x < b + half for a, b in segments):
            continue  # already lined up with a gap
        gaps = [(b, a2) for (_, b), (a2, _) in pairwise(segments) if a2 - b >= 2 * half]
        if gaps:
            targets = [clamp(x, left + half, right - half) for left, right in gaps]
            soonest = (window[0], min(targets, key=lambda t: abs(t - x)))
    return (soonest[1], soonest[0]) if soonest else None


def _dodge_target(
    x: float, me: Track, half: float, hazards: Sequence[Hazard], asteroids: Sequence[Asteroid]
) -> tuple[float, str] | None:
    """Sidestep the soonest asteroid, mine or spinner in the enemy's path."""
    threats: list[tuple[float, float, float, float, float, float, str]] = []  # x, vx, y, vy, radius, clearance
    for a in asteroids:
        threats.append((a.x, a.vx, a.y, a.vy, a.radius, a.radius, "asteroid"))
    for h in hazards:
        if isinstance(h, Mine):
            threats.append((h.x, h.vx, h.y, h.vy, Mine.RADIUS, Mine.BLAST, "mine"))  # touching it sets off the blast
        elif isinstance(h, Spinner):
            reach = h.arm_len + h.ARM_W
            threats.append((h.x, 0.0, h.y, h.speed, reach, reach, "spinner"))

    best: tuple[float, float, str] | None = None
    for ox, ovx, oy, ovy, radius, clearance, kind in threats:
        window = crossing_window(me, Track(oy, ovy, 2 * radius))
        if window is None or (best and window[0] >= best[0]):
            continue
        future_x = ox + ovx * window[0]
        needed = clearance + half
        if abs(x - future_x) >= needed:
            continue
        left, right = future_x - needed, future_x + needed
        lo, hi = half, cfg.WIDTH - half
        options = [x for x in (left, right) if lo <= x <= hi]
        if not options:
            continue
        best = (window[0], min(options, key=lambda t: abs(t - x)), kind)
    return (best[1], best[2]) if best else None
