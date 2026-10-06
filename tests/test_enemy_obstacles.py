"""Enemies obey the same obstacle rules as the player, scaled to their own health."""

from __future__ import annotations

import pytest

from nova_strike import config as cfg
from nova_strike.enemies import Enemy
from nova_strike.game import Game
from nova_strike.obstacles import Asteroid, LaserGate, Mine, Spinner, Wall

from .conftest import step


def heavy_at(game: Game, x: float, y: float) -> Enemy:
    """A heavy that can't steer away, so these tests see the damage rules alone (avoidance is in test_ai)."""
    e = Enemy("heavy", 1)
    e.x, e.y, e.speed, e.sway, e.fire_cooldown, e.agility = x, y, 0, 0, 1e9, 0
    game.enemies = [e]
    return e


def wall_across(y: float) -> Wall:
    wall = Wall(1, 0)
    wall.y = y
    return wall


def test_hitting_a_wall_costs_the_same_share_of_health_as_for_the_player(game: Game) -> None:
    wall = wall_across(300)
    left_end = wall.segments[0][1]
    heavy = heavy_at(game, max(40, left_end - 40), 300)
    game.walls = [wall]
    step(game)
    share = cfg.WALL_DAMAGE / cfg.PLAYER_MAX_HEALTH
    assert heavy.health == pytest.approx(heavy.max_health * (1 - share))
    assert heavy.alive


def test_flying_through_a_gap_is_safe(game: Game) -> None:
    wall = wall_across(300)
    gap_middle = (wall.segments[0][1] + wall.segments[1][0]) / 2
    heavy = heavy_at(game, gap_middle, 300)
    heavy.w = 20  # slim enough for any gap, so only the gap's safety is tested
    game.walls = [wall]
    step(game)
    assert heavy.health == heavy.max_health


def test_hits_are_spaced_out_by_the_same_invulnerability_window(game: Game) -> None:
    wall = wall_across(300)
    heavy = heavy_at(game, max(40, wall.segments[0][1] - 40), 300)
    game.walls = [wall]
    step(game)
    after_first = heavy.health
    step(game, int(cfg.HIT_INVULN * 60) - 2)  # still protected
    assert heavy.health == after_first
    step(game, 4)  # protection over: the wall bites again
    assert heavy.health < after_first


def test_staying_in_a_wall_eventually_destroys_it_without_scoring(game: Game) -> None:
    wall = wall_across(300)
    heavy = heavy_at(game, max(40, wall.segments[0][1] - 40), 300)
    game.walls = [wall]
    step(game, 60 * 3)
    assert not heavy.alive
    assert game.score == 0  # the player didn't shoot it
    assert not game.powerups


def test_laser_gate_only_hurts_while_on(game: Game) -> None:
    gate = LaserGate(1, 0)
    gate.y, gate.phase, gate.age = 300, 0.0, 0.0  # off
    heavy = heavy_at(game, cfg.WIDTH / 2, 300)
    game.hazards = [gate]
    step(game)
    assert heavy.health == heavy.max_health
    gate.age = gate.off_time + 0.1  # on
    step(game)
    assert heavy.health == pytest.approx(heavy.max_health * (1 - LaserGate.damage / cfg.PLAYER_MAX_HEALTH))


def test_spinner_arms_hurt(game: Game) -> None:
    spinner = Spinner(1, 0)
    spinner.x, spinner.y, spinner.angle, spinner.omega = 240, 300, 0.0, 0.0
    heavy = heavy_at(game, 240 + 70, 300)
    game.hazards = [spinner]
    step(game)
    assert heavy.health == pytest.approx(heavy.max_health * (1 - Spinner.damage / cfg.PLAYER_MAX_HEALTH))


def test_ramming_an_asteroid_smashes_it(game: Game) -> None:
    rock = Asteroid("large", 200, 300, 0, 0)
    heavy = heavy_at(game, 200, 300)
    game.asteroids = [rock]
    step(game)
    assert not game.asteroids
    assert heavy.health == pytest.approx(heavy.max_health * (1 - rock.ram_damage / cfg.PLAYER_MAX_HEALTH))
    assert game.score == 0


def test_flying_into_a_mine_sets_it_off(game: Game) -> None:
    mine = Mine(200, 300, 0)
    heavy = heavy_at(game, 200, 300)
    game.hazards = [mine]
    step(game)
    assert not game.hazards
    assert heavy.health == pytest.approx(heavy.max_health * (1 - Mine.damage / cfg.PLAYER_MAX_HEALTH))


@pytest.mark.parametrize("kind", ["scout", "fighter"])
def test_every_enemy_type_follows_the_same_rules(game: Game, kind: str) -> None:
    wall = wall_across(300)
    e = Enemy(kind, 1)
    e.x, e.y, e.speed, e.sway, e.fire_cooldown = max(30, wall.segments[0][1] - 30), 300, 0, 0, 1e9
    game.enemies = [e]
    game.walls = [wall]
    step(game)
    assert e.health < e.max_health or not e.alive
