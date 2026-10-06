"""Shared fixtures. Tests run headless using SDL's dummy video and audio drivers."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# (the environment above must be set before pygame is imported)

from collections.abc import Iterator
from pathlib import Path

import pygame
import pytest

from nova_strike import config as cfg
from nova_strike.game import Game
from nova_strike.sprites import load_sprites


class Keys(dict[int, bool]):
    """Stand-in for pygame.key.get_pressed(): any key not set reads as not pressed."""

    def __missing__(self, key: int) -> bool:
        return False


@pytest.fixture(autouse=True)
def isolated_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Never let a test read or write the player's real high score file."""
    path = tmp_path / "highscores.json"
    monkeypatch.setattr(cfg, "SCORES_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def restore_width() -> Iterator[None]:
    """Some tests resize the playfield; put it back so tests stay independent."""
    yield
    cfg.WIDTH = cfg.BASE_WIDTH


@pytest.fixture(scope="session")
def display() -> Iterator[None]:
    pygame.init()
    pygame.display.set_mode((cfg.BASE_WIDTH, cfg.HEIGHT))
    load_sprites()
    yield
    pygame.quit()


@pytest.fixture
def game(display: None) -> Game:
    """A game in progress with nothing spawning, so each test controls exactly what's on screen."""
    g = Game(sound=False)
    g.reset()
    g.banner = None
    g.player.invuln = 0.0
    g.spawn_timer = g.barrier_timer = g.rock_timer = g.pickup_timer = 1e9
    return g


def step(game: Game, frames: int = 1, keys: Keys | None = None, dt: float = 1 / 60) -> None:
    for _ in range(frames):
        game.update(dt, keys or Keys())
