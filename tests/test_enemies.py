from __future__ import annotations

import random

import pytest

from nova_strike import config as cfg
from nova_strike.enemies import Enemy, max_heavies, pick_enemy_kind


@pytest.mark.parametrize(("level", "cap"), [(1, 0), (2, 0), (3, 1), (7, 2), (11, 3), (40, 3)])
def test_max_heavies(level: int, cap: int) -> None:
    assert max_heavies(level) == cap


def test_no_heavies_before_level_three() -> None:
    random.seed(1)
    assert all(pick_enemy_kind(2, []) != "heavy" for _ in range(500))


def test_no_more_heavies_once_at_the_cap(display: None) -> None:
    random.seed(1)
    on_screen = [Enemy("heavy", 12) for _ in range(max_heavies(12))]
    assert all(pick_enemy_kind(12, on_screen) != "heavy" for _ in range(500))
    assert any(pick_enemy_kind(12, []) == "heavy" for _ in range(500))


def test_health_scales_slowly_with_level(display: None) -> None:
    assert Enemy("heavy", 1).health == cfg.ENEMY_TYPES["heavy"]["hp"]
    assert Enemy("heavy", 24).health == cfg.ENEMY_TYPES["heavy"]["hp"] + 4
    assert Enemy("scout", 8).health == cfg.ENEMY_TYPES["scout"]["hp"] + 2


@pytest.mark.parametrize(("kind", "shots"), [("scout", 1), ("fighter", 2), ("heavy", 5)])
def test_fire_patterns_and_damage(display: None, kind: str, shots: int) -> None:
    e = Enemy(kind, 1)
    e.y = 200
    e.fire_cooldown = 0
    fired = e.try_fire((e.x, 600))
    assert len(fired) == shots
    assert all(b.enemy and b.damage == cfg.ENEMY_TYPES[kind]["shot_damage"] for b in fired)
    assert e.try_fire((e.x, 600)) == []  # cooldown restarted


def test_enemies_hold_fire_until_on_screen(display: None) -> None:
    e = Enemy("fighter", 1)
    e.fire_cooldown = 0
    assert e.try_fire((0, 0)) == []


def test_hit_and_destroy(display: None) -> None:
    e = Enemy("fighter", 1)
    assert not e.hit(1)
    assert e.flash > 0
    assert e.hit(10)
    assert not e.alive
