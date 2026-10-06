from __future__ import annotations

import pygame
import pytest

from nova_strike import config as cfg
from nova_strike.player import Player
from nova_strike.weapons import Missile

from .conftest import Keys


@pytest.fixture
def player(display: None) -> Player:
    p = Player()
    p.invuln = 0.0
    return p


def test_starts_with_only_the_unlimited_blaster(player: Player) -> None:
    assert player.arsenal == {"blaster": {"level": 1, "ammo": None}}
    assert player.weapon_type == "blaster"


def test_collecting_a_new_weapon_adds_and_selects_it(player: Player) -> None:
    player.collect_weapon("spread")
    assert player.selected == "spread"
    assert player.arsenal["spread"] == {"level": 1, "ammo": cfg.WEAPON_AMMO["spread"]}


def test_collecting_a_held_weapon_levels_up_and_adds_ammo_within_caps(player: Player) -> None:
    player.collect_weapon("laser")
    player.select("blaster")
    for _ in range(5):
        player.collect_weapon("laser")
    slot = player.arsenal["laser"]
    assert player.selected == "blaster"  # a weapon you already carry isn't auto-selected
    assert slot["level"] == cfg.MAX_WEAPON
    assert slot["ammo"] == cfg.WEAPON_AMMO["laser"] * cfg.AMMO_CAP


def test_nukes_stack_but_are_never_auto_selected(player: Player) -> None:
    for _ in range(5):
        player.collect_weapon("nuke")
    assert player.selected == "blaster"
    assert player.arsenal["nuke"]["ammo"] == cfg.AMMO_CAP


def test_cycle_skips_weapons_not_carried_and_wraps(player: Player) -> None:
    player.collect_weapon("missile")
    player.select("blaster")
    player.cycle(1)
    assert player.selected == "missile"
    player.cycle(1)
    assert player.selected == "blaster"
    player.cycle(-1)
    assert player.selected == "missile"


def test_select_ignores_weapons_not_carried(player: Player) -> None:
    player.select("laser")
    assert player.selected == "blaster"


def test_running_out_of_ammo_drops_the_weapon(player: Player) -> None:
    player.collect_weapon("laser")
    player.use_ammo(cfg.WEAPON_AMMO["laser"])
    assert "laser" not in player.arsenal
    assert player.emptied == "laser"
    assert player.selected == "blaster"


def test_blaster_never_runs_out(player: Player) -> None:
    player.use_ammo(10_000)
    assert player.arsenal["blaster"]["ammo"] is None


@pytest.mark.parametrize(("level", "shots"), [(1, 2), (2, 4), (3, 7)])
def test_blaster_shots_per_level(player: Player, level: int, shots: int) -> None:
    assert len(player.blaster_shots(level)) == shots


@pytest.mark.parametrize(("level", "shots"), [(1, 3), (2, 5), (3, 7)])
def test_spread_fans_out_and_uses_ammo(player: Player, level: int, shots: int) -> None:
    player.arsenal["spread"] = {"level": level, "ammo": 10}
    player.selected = "spread"
    fired = player.fire()
    assert len(fired) == shots
    assert player.arsenal["spread"]["ammo"] == 9
    assert player.fire() == []  # still cooling down


def test_missiles_fire_in_pairs_and_use_ammo(player: Player) -> None:
    player.arsenal["missile"] = {"level": 1, "ammo": 10}
    player.selected = "missile"
    fired = player.fire()
    assert sum(isinstance(b, Missile) for b in fired) == 2
    assert player.arsenal["missile"]["ammo"] == 8


def test_laser_and_nuke_fire_no_projectiles(player: Player) -> None:
    for kind in ("laser", "nuke"):
        player.arsenal[kind] = {"level": 1, "ammo": 1}
        player.selected = kind
        assert player.fire() == []


def test_hit_is_ignored_while_protected(player: Player) -> None:
    assert player.hit(30)
    assert player.health == 70
    assert not player.hit(30)  # brief invulnerability after a hit
    player.invuln = 0
    player.invincible = 5
    assert not player.hit(30)
    assert player.health == 70


def test_movement_stays_inside_the_playfield(player: Player) -> None:
    keys = Keys({pygame.K_RIGHT: True, pygame.K_DOWN: True})
    for _ in range(300):
        player.update(1 / 60, keys)
    assert player.x == pytest.approx(cfg.WIDTH - player.w / 2)
    assert player.y == pytest.approx(cfg.HEIGHT - cfg.TRAY_H - player.h / 2)  # can't fly over the weapon tray
