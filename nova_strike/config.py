"""Game-wide settings, tuning tables and shared type definitions.

WIDTH is the one mutable setting: it follows the window's aspect ratio (see ``Game.set_play_width``).
Always read it as ``config.WIDTH`` so the current value is used.
"""

from __future__ import annotations

import os
import sys
from typing import Protocol, TypedDict, TypeVar

import pygame

Color = tuple[int, ...]


Point = tuple[float, float]


Samples = list[float]  # mono audio samples in -1..1


ScoreEntry = tuple[str, int]  # (initials, score)


Num = TypeVar("Num", int, float)


class Target(Protocol):
    """Anything a homing missile can lock on to."""

    @property
    def x(self) -> float: ...
    @property
    def y(self) -> float: ...
    @property
    def alive(self) -> bool: ...


class KeyState(Protocol):
    """The pressed-key lookup returned by pygame.key.get_pressed()."""

    def __getitem__(self, key: int, /) -> bool: ...


class HasY(Protocol):
    @property
    def y(self) -> float: ...


class WeaponSpec(TypedDict):
    name: str
    label: str
    color: Color


class PickupSpec(TypedDict):
    name: str
    label: str | None
    color: Color


class EnemySpec(TypedDict):
    size: tuple[int, int]
    speed: tuple[float, float]  # random range, px/s
    hp: int
    score: int
    fire: tuple[float, float]  # random range of seconds between shots
    sway: float
    freq: float
    shot_damage: int
    ram_damage: int
    agility: float  # sideways speed when steering around obstacles, px/s


class WeaponSlot(TypedDict):
    level: int
    ammo: float | None  # None means unlimited


# HEIGHT is fixed; WIDTH follows the window's aspect ratio (see Game.set_play_width), so a
# fullscreen or resized window gets a wider playfield instead of black bars.
BASE_WIDTH, HEIGHT = 480, 720


WIDTH = BASE_WIDTH


MAX_WIDTH = 1400


FPS = 60


DEFAULT_LIVES = 3


MAX_LIVES = 9


EXTRA_LIFE_EVERY = 1000


POINTS_PER_LEVEL = 300


MAX_WEAPON = 3


INVINCIBLE_TIME = 8.0


WALL_DAMAGE = 30
PLAYER_MAX_HEALTH = 100
HIT_INVULN = 0.6  # seconds of protection after taking a hit (player and enemies alike)


WEAPON_ORDER = ("blaster", "spread", "laser", "missile", "nuke")


WEAPON_AMMO: dict[str, float] = {
    "spread": 60,
    "laser": 6.0,
    "missile": 40,
    "nuke": 1,
}  # volleys, seconds of beam, missiles, bombs


AMMO_CAP = 3  # a weapon can hold at most this many pickups' worth of ammo


TRAY_H = 44  # height of the weapon tray along the bottom of the screen


SLOWMO_TIME = 4.0  # seconds each slow-motion charge lasts


SLOWMO_FACTOR = 0.3  # world speed while slow motion is active


MAX_SLOWMO = 3


# Weapon switching uses the modifier keys beside the space bar so you can keep firing:
# Cmd (Mac) / Alt (Windows, Linux) selects the next weapon, Ctrl the previous one.
IS_MAC = sys.platform == "darwin"
IS_WEB = sys.platform == "emscripten"  # running in a browser via pygbag (WebAssembly)


def available_keys(*names: str) -> tuple[int, ...]:
    """Key codes for whichever of these names this pygame build has (the browser build lacks K_LGUI)."""
    return tuple(dict.fromkeys(getattr(pygame, n) for n in names if hasattr(pygame, n)))


NEXT_WEAPON_KEYS = available_keys("K_LGUI", "K_RGUI", "K_LMETA", "K_RMETA", "K_LALT", "K_RALT")
PREV_WEAPON_KEYS = available_keys("K_LCTRL", "K_RCTRL")
SLOWMO_KEYS = available_keys("K_LSHIFT", "K_RSHIFT")


SCOREBOARD_SIZE = 10


def user_data_dir() -> str:
    """The per-user folder for saved data, used by the packaged desktop builds."""
    system: str = sys.platform  # a plain str, so mypy checks every branch rather than only this machine's
    if system == "win32":
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Nova Strike")
    if system == "darwin":
        return os.path.expanduser("~/Library/Application Support/Nova Strike")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "nova-strike")


# saved in the project folder, next to main.py. A packaged build (PyInstaller sets sys.frozen) runs
# from a temporary or read-only folder, so it saves in the user's data folder instead.
SCORES_FILE = (
    os.path.join(user_data_dir(), "highscores.json")
    if getattr(sys, "frozen", False)
    else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "highscores.json")
)


NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


DEFAULT_SCORES: list[ScoreEntry] = [
    ("NOV", 5000),
    ("ACE", 4000),
    ("ZAP", 3200),
    ("JET", 2500),
    ("SKY", 2000),
    ("ION", 1500),
    ("REX", 1000),
    ("MAX", 700),
    ("BOT", 400),
    ("CPU", 200),
]


TITLE_PAGE_TIME = 7.0  # the title screen alternates between info and high scores


SS = 4  # supersampling factor used when rendering sprites


WHITE = (255, 255, 255)


RED = (220, 60, 60)


GREEN = (60, 220, 100)


YELLOW = (240, 220, 80)


CYAN = (80, 220, 240)


ORANGE = (255, 140, 50)


MAGENTA = (230, 80, 255)


GRAY = (120, 120, 130)


BG = (6, 6, 18)


PLAYER_SIZE = (44, 52)


PICKUP_SIZE = 34


WEAPONS: dict[str, WeaponSpec] = {
    "blaster": {"name": "BLASTER", "label": "B", "color": (80, 200, 255)},
    "spread": {"name": "SPREAD", "label": "S", "color": (110, 255, 190)},
    "laser": {"name": "LASER", "label": "L", "color": (255, 80, 210)},
    "missile": {"name": "MISSILES", "label": "M", "color": (255, 160, 60)},
    "nuke": {"name": "NUKE", "label": "N", "color": (170, 255, 50)},
}


PICKUPS: dict[str, PickupSpec] = {
    **{kind: {"color": w["color"], "label": w["label"], "name": w["name"]} for kind, w in WEAPONS.items()},
    "repair": {"color": (255, 80, 100), "label": "+", "name": "REPAIR"},
    "invincible": {"color": (255, 215, 60), "label": None, "name": "INVINCIBLE"},
    "slowmo": {"color": (170, 140, 255), "label": None, "name": "SLOW-MO"},
}


PICKUP_WEIGHTS = {
    "blaster": 1,
    "spread": 1.2,
    "laser": 1,
    "missile": 1.2,
    "repair": 2,
    "invincible": 0.6,
    "slowmo": 1.3,
    "nuke": 0.1,  # nukes are deliberately very rare (about 1 pickup in 100)
}


ASTEROID_RADII = {"large": 28, "small": 15}


ENEMY_TYPES: dict[str, EnemySpec] = {
    "scout": {
        "size": (32, 30),
        "speed": (140, 180),
        "hp": 1,
        "score": 15,
        "fire": (2.2, 3.8),
        "sway": 90,
        "freq": 3.0,
        "shot_damage": 8,
        "ram_damage": 20,
        "agility": 170,
    },
    "fighter": {
        "size": (42, 38),
        "speed": (85, 115),
        "hp": 3,
        "score": 30,
        "fire": (1.5, 2.6),
        "sway": 40,
        "freq": 1.6,
        "shot_damage": 12,
        "ram_damage": 35,
        "agility": 120,
    },
    "heavy": {
        "size": (64, 48),
        "speed": (45, 60),
        "hp": 9,
        "score": 80,
        "fire": (1.8, 2.6),
        "sway": 15,
        "freq": 0.8,
        "shot_damage": 18,
        "ram_damage": 60,
        "agility": 75,
    },
}


BOSS_LEVEL = 20  # first boss at this level, then again every BOSS_LEVEL levels, tougher each time


BOSS_SIZE = (320, 150)


BOSS_TURRETS = ((-110, -13), (-55, 13), (55, 13), (110, -13))  # offsets from the ship's centre


BOSS_CORE_OFFSET = 5
