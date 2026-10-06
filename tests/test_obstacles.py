from __future__ import annotations

import random
from types import SimpleNamespace

import pygame
import pytest

from nova_strike import config as cfg
from nova_strike.obstacles import Asteroid, LaserGate, Mine, SlidingWall, Spinner, Wall


def gaps(wall: Wall) -> list[tuple[int, int]]:
    edges = [b for _, b in wall.segments[:-1]]
    starts = [a for a, _ in wall.segments[1:]]
    return list(zip(edges, starts, strict=True))


@pytest.mark.parametrize("level", [1, 5, 12])
def test_walls_span_the_screen_with_passable_gaps(display: None, level: int) -> None:
    random.seed(level)
    wall = Wall(level, 100)
    assert wall.segments[0][0] == 0
    assert wall.segments[-1][1] == cfg.WIDTH
    assert gaps(wall)
    assert all(end - start >= 99 for start, end in gaps(wall))  # wider than the ship's 26px body


def test_wall_rescale_keeps_it_full_width(display: None) -> None:
    wall = Wall(1, 100)
    cfg.WIDTH = 960
    wall.rescale(2.0, 480)
    assert wall.segments[-1][1] == 960


def test_sliding_wall_gap_moves(display: None) -> None:
    wall = SlidingWall(3, 0)
    before = wall.segments
    wall.update(0.5)
    assert wall.segments != before
    assert wall.segments[1][0] - wall.segments[0][1] == pytest.approx(wall.gap_w, abs=1)


def test_laser_gate_only_hurts_when_on(display: None) -> None:
    gate = LaserGate(1, 0)
    gate.y = 300
    middle = pygame.Rect(cfg.WIDTH // 2, 295, 20, 10)
    gate.phase, gate.age = 0.0, 0.0
    assert gate.state() == "off"
    assert not gate.touches(middle)
    gate.age = gate.off_time - 0.1
    assert gate.state() == "warn"
    gate.age = gate.off_time + 0.1
    assert gate.state() == "on"
    assert gate.touches(middle)
    assert gate.laser_stop(cfg.WIDTH / 2, 3, 600) is not None


def test_laser_gate_pylons_are_always_solid(display: None) -> None:
    gate = LaserGate(1, 0)
    gate.y, gate.phase, gate.age = 300, 0.0, 0.0
    assert gate.touches(pygame.Rect(2, 295, 6, 6))


def test_mine_arms_and_homes_in(display: None) -> None:
    mine = Mine(200, 300, 0)
    player = SimpleNamespace(alive=True, x=260, y=360)
    game = SimpleNamespace(player=player, sfx=SimpleNamespace(play=lambda *a, **k: None))
    mine.update(1 / 60, game)  # type: ignore[arg-type]
    assert mine.armed
    start = (player.x - mine.x) ** 2 + (player.y - mine.y) ** 2
    for _ in range(30):
        mine.update(1 / 60, game)  # type: ignore[arg-type]
    assert (player.x - mine.x) ** 2 + (player.y - mine.y) ** 2 < start


def test_mine_stays_dormant_when_far_away(display: None) -> None:
    mine = Mine(50, 100, 0)
    game = SimpleNamespace(player=SimpleNamespace(alive=True, x=400, y=600), sfx=None)
    mine.update(1 / 60, game)  # type: ignore[arg-type]
    assert not mine.armed


def test_spinner_arm_collision(display: None) -> None:
    spinner = Spinner(1, 0)
    spinner.x, spinner.y, spinner.angle = 240, 300, 0.0  # arms point left and right
    assert spinner.touches(pygame.Rect(240 + 60, 296, 8, 8))  # on an arm
    assert not spinner.touches(pygame.Rect(240 + 60, 340, 8, 8))  # below it
    assert spinner.touches(pygame.Rect(236, 296, 8, 8))  # the hub


def test_asteroid_takes_hits_and_bounces_off_edges(display: None) -> None:
    rock = Asteroid("small", 20, 100, -100, 0)
    rock.update(0.1)
    assert rock.vx > 0  # bounced off the left edge
    assert not rock.hit(1)
    assert rock.hit(1)
    assert not rock.alive
