from __future__ import annotations

import math

import pytest

from nova_strike import config as cfg
from nova_strike.boss import Boss, EnemyMissile
from nova_strike.game import Game
from nova_strike.weapons import Bullet

from .conftest import step


@pytest.fixture
def boss_fight(game: Game) -> tuple[Game, Boss]:
    boss = Boss(0)
    boss.state = "fighting"
    boss.y = Boss.STOP_Y
    boss.place_parts()
    game.boss = boss
    return game, boss


def test_core_is_shielded_until_every_turret_is_down(display: None) -> None:
    boss = Boss(0)
    assert boss.shielded
    assert boss.targets() == boss.turrets
    for turret in boss.turrets:
        turret.hit(turret.max_health)
    assert not boss.shielded
    assert boss.targets() == [boss.core]


def test_later_bosses_are_tougher(display: None) -> None:
    assert Boss(1).max_total > Boss(0).max_total


def test_shots_bounce_off_the_shielded_core(boss_fight: tuple[Game, Boss]) -> None:
    game, boss = boss_fight
    shot = Bullet(boss.core.x, boss.core.y + 5)
    assert game.bullet_hits_boss(shot, shot.rect())
    assert boss.core.health == boss.core.max_health


def test_destroying_turrets_exposes_the_core_and_scores(boss_fight: tuple[Game, Boss]) -> None:
    game, boss = boss_fight
    for turret in boss.turrets:
        turret.hit(turret.max_health)
        game.destroy_turret(boss, turret)
    assert game.score == 300 * len(boss.turrets)
    assert game.banner is not None and game.banner.title == "CORE EXPOSED!"


def test_defeating_the_boss_pays_out_and_advances_exactly_one_level(boss_fight: tuple[Game, Boss]) -> None:
    game, boss = boss_fight
    game.level = 20
    game.kill_boss(boss)
    assert boss.state == "dying"
    step(game, 60 * 4)
    assert game.boss is None
    assert game.score >= 5000
    assert game.level == 21
    assert game.next_boss_level == 40
    assert any(p.kind == "nuke" for p in game.powerups)


def test_turrets_launch_homing_missiles(boss_fight: tuple[Game, Boss]) -> None:
    game, _ = boss_fight
    step(game, 60 * 3)
    assert any(isinstance(b, EnemyMissile) for b in game.enemy_bullets)


def test_enemy_missiles_can_be_shot_down(game: Game) -> None:
    missile = EnemyMissile(200, 300, math.pi / 2)
    game.enemy_bullets = [missile]
    game.shoot_down_missile(missile)
    assert not missile.alive
    assert game.score == 10


def test_boss_arrives_at_the_boss_level(display: None) -> None:
    g = Game(sound=False, start_level=cfg.BOSS_LEVEL)
    g.reset()
    g.player.invuln = 1e9
    step(g, 60 * 4)
    assert g.boss is not None
    assert g.practice  # starting part-way in doesn't record high scores
