from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

import pytest

from nova_strike import config as cfg
from nova_strike.weapons import Bullet, Missile, PowerUp, random_pickup_kind


def test_bullet_sweep_rect_covers_the_whole_frame_of_travel() -> None:
    b = Bullet(100, 300, vy=-600)
    b.update(1 / 30)  # moves 20px: more than its own height
    sweep = b.sweep_rect()
    assert sweep.top <= b.y - b.hh
    assert sweep.bottom >= 300 + b.hh


def test_bullet_dies_once_off_screen() -> None:
    b = Bullet(100, 5, vy=-640)
    b.update(0.1)
    assert not b.alive


@dataclass
class FakeTarget:
    x: float
    y: float
    alive: bool = True


def test_missile_turns_towards_its_target() -> None:
    m = Missile(100, 400, -math.pi / 2)  # launched straight up
    target = FakeTarget(300, 400)  # directly to the right
    for _ in range(30):
        m.steer(1 / 60, [target])
        m.update(1 / 60)
    assert m.target is target
    assert m.vx > 0  # now heading right


def test_missile_ignores_dead_targets_and_expires() -> None:
    m = Missile(100, 400, -math.pi / 2)
    m.steer(1 / 60, [FakeTarget(300, 400, alive=False)])
    assert m.target is None
    m.age = 2.99
    m.update(0.02)
    assert not m.alive


def test_powerup_drifts_down_and_expires(display: None) -> None:
    p = PowerUp(100, 100, "repair")
    p.update(1.0)
    assert p.y == pytest.approx(180)
    p.y = cfg.HEIGHT + 30
    p.update(0.01)
    assert not p.alive


def test_every_pickup_kind_has_a_sprite_and_label(display: None) -> None:
    for kind in cfg.PICKUPS:
        p = PowerUp(0, 0, kind)
        assert p.sprite.get_size() == (cfg.PICKUP_SIZE, cfg.PICKUP_SIZE)
        assert p.label.get_width() > 0


def test_pickup_rarity() -> None:
    random.seed(7)
    counts = Counter(random_pickup_kind() for _ in range(20000))
    assert set(counts) == set(cfg.PICKUP_WEIGHTS)
    assert counts["nuke"] / 20000 < 0.02  # nukes stay very rare
    assert counts["repair"] > counts["invincible"]
