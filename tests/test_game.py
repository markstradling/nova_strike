from __future__ import annotations

import json
from pathlib import Path

import pygame
import pytest

from nova_strike import config as cfg
from nova_strike.enemies import Enemy
from nova_strike.game import Game
from nova_strike.obstacles import Asteroid, Mine, Wall
from nova_strike.weapons import Bullet, PowerUp

from .conftest import Keys, step


def stationary_enemy(kind: str, x: float, y: float) -> Enemy:
    e = Enemy(kind, 1)
    e.x, e.y, e.speed, e.sway, e.fire_cooldown = x, y, 0, 0, 1e9
    return e


def test_new_game_state(game: Game) -> None:
    assert game.state == "playing"
    assert game.lives == cfg.DEFAULT_LIVES
    assert game.level == 1
    assert game.slowmo_charges == 1


def test_level_follows_score(game: Game) -> None:
    game.score = cfg.POINTS_PER_LEVEL * 2
    step(game)
    assert game.level == 3


def test_extra_life_every_threshold_up_to_the_cap(game: Game) -> None:
    game.score = cfg.EXTRA_LIFE_EVERY
    step(game)
    assert game.lives == cfg.DEFAULT_LIVES + 1
    game.lives = cfg.MAX_LIVES
    game.score = cfg.EXTRA_LIFE_EVERY * 2
    step(game)
    assert game.lives == cfg.MAX_LIVES


def test_shooting_an_enemy_scores(game: Game) -> None:
    game.enemies = [stationary_enemy("scout", 200, 300)]
    game.bullets = [Bullet(200, 330)]
    step(game, 5)
    assert not game.enemies
    assert game.score == cfg.ENEMY_TYPES["scout"]["score"]


@pytest.mark.parametrize("kind", ["scout", "fighter", "heavy"])
def test_each_enemy_shot_does_its_own_damage(game: Game, kind: str) -> None:
    p = game.player
    damage = cfg.ENEMY_TYPES[kind]["shot_damage"]
    game.enemy_bullets = [Bullet(p.x, p.y, vy=1, enemy=True, radius=4, damage=damage)]
    step(game)
    assert p.health == p.max_health - damage


def test_ramming_an_enemy_costs_its_ram_damage(game: Game) -> None:
    p = game.player
    game.enemies = [stationary_enemy("heavy", p.x, p.y)]
    step(game)
    assert p.health == p.max_health - cfg.ENEMY_TYPES["heavy"]["ram_damage"]


def test_invincibility_deflects_everything(game: Game) -> None:
    p = game.player
    p.invincible = 5
    game.enemy_bullets = [Bullet(p.x, p.y, vy=1, enemy=True, radius=4, damage=50)]
    game.enemies = [stationary_enemy("heavy", p.x, p.y)]
    step(game)
    assert p.health == p.max_health
    assert not game.enemies  # rammed and destroyed


def test_wall_contact_hurts(game: Game) -> None:
    wall = Wall(1, 0)
    wall.y = game.player.y - wall.H / 2
    game.player.x = wall.segments[0][0] + 5
    game.walls = [wall]
    step(game)
    assert game.player.health == game.player.max_health - cfg.WALL_DAMAGE


def test_losing_all_health_costs_a_life_then_respawns(game: Game) -> None:
    game.damage_player(1000, 0, 0)
    step(game)
    assert not game.player.alive
    assert game.lives == cfg.DEFAULT_LIVES - 1
    step(game, 120)
    assert game.player.alive
    assert game.player.health == game.player.max_health


def test_last_life_lost_ends_the_game(game: Game) -> None:
    game.lives = 1
    game.kill_player()
    step(game, 120)
    assert game.state == "game_over"  # score 0 doesn't qualify for the table


def test_pickups(game: Game) -> None:
    p = game.player
    p.health = 50
    for kind in ("repair", "invincible", "slowmo", "laser"):
        game.powerups = [PowerUp(p.x, p.y, kind)]
        step(game)
    assert p.health == 85
    assert p.invincible > 0
    assert game.slowmo_charges == 2
    assert p.selected == "laser"


def test_slow_motion_slows_the_world_but_not_the_player(game: Game) -> None:
    enemy = stationary_enemy("fighter", 100, 100)
    enemy.speed = 100
    game.enemies = [enemy]
    game.handle_key(pygame.K_LSHIFT)
    assert game.slowmo_active
    assert game.slowmo_charges == 0
    game.player.x = x = 40.0  # room to fly right for a full second
    step(game, 60, Keys({pygame.K_RIGHT: True}))
    assert enemy.y - 100 == pytest.approx(100 * cfg.SLOWMO_FACTOR, rel=0.05)
    assert game.player.x - x == pytest.approx(game.player.speed, rel=0.05)


def test_slow_motion_without_charges_does_nothing(game: Game) -> None:
    game.slowmo_charges = 0
    game.handle_key(pygame.K_LSHIFT)
    assert not game.slowmo_active


def test_nuke_clears_everything_on_screen(game: Game) -> None:
    game.enemies = [stationary_enemy("fighter", 100, 200), stationary_enemy("heavy", 300, 150)]
    game.asteroids = [Asteroid("large", 200, 300, 0, 0)]
    game.hazards = [Mine(150, 250, 0)]
    game.walls = [Wall(1, 0)]
    game.walls[0].y = 200
    game.enemy_bullets = [Bullet(10, 10, enemy=True)]
    offscreen = stationary_enemy("scout", 100, -200)
    game.enemies.append(offscreen)
    game.player.collect_weapon("nuke")
    game.handle_key(pygame.K_5)
    game.handle_key(pygame.K_SPACE)
    step(game)
    assert game.enemies == [offscreen]  # only things already on screen are destroyed
    assert not game.asteroids and not game.hazards and not game.walls and not game.enemy_bullets
    assert "nuke" not in game.player.arsenal
    assert game.player.selected == "blaster"


def test_holding_fire_never_launches_a_nuke(game: Game) -> None:
    game.player.collect_weapon("nuke")
    game.player.select("nuke")
    step(game, 30, Keys({pygame.K_SPACE: True}))
    assert game.player.arsenal["nuke"]["ammo"] == 1


def test_weapon_switching_keys(game: Game) -> None:
    for kind in ("spread", "laser"):
        game.player.collect_weapon(kind)
    game.player.select("blaster")
    for key in cfg.NEXT_WEAPON_KEYS[:1] + cfg.PREV_WEAPON_KEYS[:1]:
        assert key in (pygame.K_LGUI, pygame.K_LCTRL)
    game.handle_key(pygame.K_LGUI)
    assert game.player.selected == "spread"
    game.handle_key(pygame.K_LALT)
    assert game.player.selected == "laser"
    game.handle_key(pygame.K_LCTRL)
    assert game.player.selected == "spread"
    game.handle_key(pygame.K_1)
    assert game.player.selected == "blaster"


def test_high_score_name_entry_saves_to_the_table(game: Game, isolated_scores: Path) -> None:
    game.score = 4500
    game.end_game()
    assert game.state == "enter_name"
    game.state_time = 1.0  # past the guard that ignores a still-held fire key
    for key in (pygame.K_m, pygame.K_a, pygame.K_x, pygame.K_RETURN):
        game.handle_key(key)
    assert game.state == "game_over"
    assert game.scores[1] == ("MAX", 4500)
    assert game.new_rank == 1
    assert json.loads(isolated_scores.read_text())[1] == {"name": "MAX", "score": 4500}


def test_name_entry_arrows_cycle_letters(game: Game) -> None:
    game.score = 4500
    game.end_game()
    game.state_time = 1.0
    game.name = list("AAA")
    game.handle_key(pygame.K_UP)
    game.handle_key(pygame.K_RIGHT)
    game.handle_key(pygame.K_DOWN)
    assert "".join(game.name) == "B9A"


def test_game_over_space_returns_to_menu_after_a_short_guard(game: Game) -> None:
    game.end_game()
    assert game.state == "game_over"
    game.handle_key(pygame.K_SPACE)
    assert game.state == "game_over"  # ignored straight away
    game.state_time = 1.0
    game.handle_key(pygame.K_SPACE)
    assert game.state == "title"


def test_practice_runs_are_not_recorded(display: None, isolated_scores: Path) -> None:
    g = Game(sound=False, start_level=5)
    g.reset()
    g.score = 99999
    g.end_game()
    assert g.state == "game_over"
    assert not isolated_scores.exists()


def test_widening_the_playfield_moves_everything_across(game: Game) -> None:
    game.enemies = [stationary_enemy("scout", 120, 300)]
    game.walls = [Wall(1, 0)]
    x = game.player.x
    game.set_play_width(960)
    assert cfg.WIDTH == 960
    assert game.player.x == pytest.approx(x * 2)
    assert game.enemies[0].x == pytest.approx(240)
    assert game.walls[0].segments[-1][1] == 960
    assert game.canvas.get_width() == 960


def test_a_full_minute_of_play_runs_cleanly(display: None) -> None:
    g = Game(sound=False)
    g.reset()
    keys = Keys({pygame.K_SPACE: True})
    for i in range(3600):
        g.player.invuln = 1.0
        keys[pygame.K_LEFT] = (i // 60) % 2 == 0
        keys[pygame.K_RIGHT] = not keys[pygame.K_LEFT]
        g.update(1 / 60, keys)
        if i % 600 == 0:
            g.draw()
    assert g.state == "playing"
    assert g.score > 0
