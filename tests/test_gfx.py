from __future__ import annotations

import math

import pygame
import pytest

from nova_strike import gfx
from nova_strike.config import SS


@pytest.mark.parametrize(
    ("value", "lo", "hi", "expected"),
    [(5, 0, 10, 5), (-3, 0, 10, 0), (12, 0, 10, 10), (0.5, 0.0, 1.0, 0.5), (1.5, 0.0, 1.0, 1.0)],
)
def test_clamp(value: float, lo: float, hi: float, expected: float) -> None:
    assert gfx.clamp(value, lo, hi) == expected


def test_lerp_color_endpoints_and_midpoint() -> None:
    a, b = (0, 0, 0), (200, 100, 50)
    assert gfx.lerp_color(a, b, 0) == a
    assert gfx.lerp_color(a, b, 1) == b
    assert gfx.lerp_color(a, b, 0.5) == (100, 50, 25)


def test_rotated_moves_forward_along_angle_and_sideways_perpendicular() -> None:
    x, y = gfx.rotated(10, 20, 0.0, forward=5, side=0)
    assert (x, y) == pytest.approx((15, 20))
    x, y = gfx.rotated(0, 0, math.pi / 2, forward=4, side=0)  # pointing down the screen
    assert (x, y) == pytest.approx((0, 4))
    x, y = gfx.rotated(0, 0, 0.0, forward=0, side=3)  # side offset is perpendicular to the heading
    assert (x, y) == pytest.approx((0, 3))


@pytest.mark.parametrize(
    ("cx", "cy", "r", "hit"),
    [
        (5, 5, 1, True),  # centre inside the rect
        (-3, 5, 4, True),  # overlaps the left edge
        (-5, 5, 4, False),  # just clear of the left edge
        (13, 13, 5, True),  # reaches the corner (distance ~4.24)
        (15, 15, 5, False),  # corner is out of reach (distance ~7.07)
    ],
)
def test_circle_hits_rect(cx: float, cy: float, r: float, hit: bool) -> None:
    assert gfx.circle_hits_rect(cx, cy, r, pygame.Rect(0, 0, 10, 10)) is hit


def test_supersampling_helpers_scale_coordinates() -> None:
    ss = SS
    assert gfx.sc(1.5, 2) == (int(1.5 * ss), 2 * ss)
    assert gfx.sp([(1, 2)]) == [(ss, 2 * ss)]
    assert gfx.sr(1, 2, 3, 4) == pygame.Rect(ss, 2 * ss, 3 * ss, 4 * ss)


def test_glow_surface_is_cached_and_sized(display: None) -> None:
    first = gfx.glow_surface(10, (255, 0, 0))
    assert first.get_size() == (20, 20)
    assert gfx.glow_surface(10, (255, 0, 0)) is first
    assert gfx.glow_surface(10, (0, 255, 0)) is not first


def test_glow_is_brightest_at_the_centre(display: None) -> None:
    glow = gfx.glow_surface(10, (255, 255, 255))
    assert glow.get_at((10, 10)).r > glow.get_at((2, 10)).r


def test_make_flash_keeps_shape_but_turns_white(display: None) -> None:
    sprite = pygame.Surface((4, 4), pygame.SRCALPHA)
    sprite.fill((0, 0, 0, 0))
    sprite.set_at((1, 1), (200, 20, 20, 255))
    flash = gfx.make_flash(sprite)
    assert tuple(flash.get_at((1, 1))) == (255, 255, 255, 255)
    assert flash.get_at((0, 0)).a == 0
