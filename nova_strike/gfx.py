"""Drawing and geometry helpers shared by every sprite and entity."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING

import pygame

from .config import SS

if TYPE_CHECKING:
    from .config import Color, Num, Point


def clamp(value: Num, lo: Num, hi: Num) -> Num:
    return max(lo, min(hi, value))


def lerp_color(a: Color, b: Color, t: float) -> Color:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_font_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("menlo,consolas,dejavusansmono,monospace", size, bold=bold)
    return _font_cache[key]


_glow_cache: dict[tuple[int, Color], pygame.Surface] = {}


def glow_surface(radius: float, color: Color) -> pygame.Surface:
    """Radial glow on a black surface, meant to be blitted with BLEND_RGB_ADD."""
    radius = max(1, int(radius))
    key = (radius, color)
    if key not in _glow_cache:
        surf = pygame.Surface((radius * 2, radius * 2))
        for r in range(radius, 0, -1):
            t = (1 - r / radius) ** 2
            pygame.draw.circle(surf, tuple(int(c * t) for c in color), (radius, radius), r)
        _glow_cache[key] = surf
    return _glow_cache[key]


def blit_glow(
    surface: pygame.Surface, x: float, y: float, radius: float, color: Color, *, strength: float = 1.0
) -> None:
    glow = glow_surface(radius, color)
    if strength < 1.0:
        glow = glow.copy()
        f = int(255 * clamp(strength, 0, 1))
        glow.fill((f, f, f), special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(
        glow, (int(x - glow.get_width() / 2), int(y - glow.get_height() / 2)), special_flags=pygame.BLEND_RGB_ADD
    )


def gradient_polygon(
    surf: pygame.Surface, points: Sequence[Point], start: Color, end: Color, *, horizontal: bool = False
) -> None:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = int(min(xs)), int(min(ys))
    w = max(1, math.ceil(max(xs)) - x0 + 1)
    h = max(1, math.ceil(max(ys)) - y0 + 1)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), [(px - x0, py - y0) for px, py in points])
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    steps = w if horizontal else h
    for i in range(steps):
        color = (*lerp_color(start, end, i / max(1, steps - 1)), 255)
        if horizontal:
            pygame.draw.line(grad, color, (i, 0), (i, h))
        else:
            pygame.draw.line(grad, color, (0, i), (w, i))
    mask.blit(grad, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(mask, (x0, y0))


def sp(points: Iterable[Point]) -> list[Point]:
    return [(x * SS, y * SS) for x, y in points]


def sc(x: float, y: float) -> tuple[int, int]:
    return (int(x * SS), int(y * SS))


def sr(x: float, y: float, w: float, h: float) -> pygame.Rect:
    return pygame.Rect(int(x * SS), int(y * SS), int(w * SS), int(h * SS))


def build_sprite(w: int, h: int, draw_fn: Callable[[pygame.Surface], None]) -> pygame.Surface:
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    draw_fn(big)
    return pygame.transform.smoothscale(big, (w, h)).convert_alpha()


def make_flash(sprite: pygame.Surface) -> pygame.Surface:
    flash = sprite.copy()
    flash.fill((255, 255, 255, 0), special_flags=pygame.BLEND_RGBA_MAX)
    return flash


def rotated(cx: float, cy: float, angle: float, forward: float, side: float) -> Point:
    """Point `forward` units along `angle` from (cx, cy), offset `side` units perpendicular to it."""
    ca, sa = math.cos(angle), math.sin(angle)
    return (cx + forward * ca - side * sa, cy + forward * sa + side * ca)


def circle_hits_rect(cx: float, cy: float, r: float, rect: pygame.Rect) -> bool:
    nx = clamp(cx, rect.left, rect.right)
    ny = clamp(cy, rect.top, rect.bottom)
    return (cx - nx) ** 2 + (cy - ny) ** 2 < r * r
