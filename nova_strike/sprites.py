"""Sprite artwork, drawn in code at 4x size and smoothly scaled down, plus the loaded sprite registry."""

from __future__ import annotations

import math
import random
from functools import partial

import pygame

from . import config as cfg
from .config import (
    ASTEROID_RADII,
    BG,
    BOSS_CORE_OFFSET,
    BOSS_SIZE,
    BOSS_TURRETS,
    ENEMY_TYPES,
    HEIGHT,
    PICKUP_SIZE,
    PICKUPS,
    PLAYER_SIZE,
    SS,
    WEAPON_ORDER,
    WHITE,
)
from .gfx import build_sprite, gradient_polygon, lerp_color, make_flash, sc, sp, sr


def draw_player_sprite(s: pygame.Surface) -> None:
    outline = (18, 22, 40)
    wing = [(22, 13), (43, 37), (43, 44), (31, 41), (13, 41), (1, 44), (1, 37)]
    gradient_polygon(s, sp(wing), (90, 110, 160), (35, 45, 80))
    pygame.draw.polygon(s, outline, sp(wing), SS)
    for sign in (-1, 1):
        stripe = [(22 + sign * 7, 21), (22 + sign * 19, 35), (22 + sign * 19, 38), (22 + sign * 7, 26)]
        pygame.draw.polygon(s, (70, 210, 255), sp(stripe))
    for cx in (3, 41):
        pygame.draw.rect(s, (165, 175, 195), sr(cx - 1.5, 25, 3, 18), border_radius=SS)
        pygame.draw.rect(s, (40, 45, 60), sr(cx - 1.5, 25, 3, 18), SS, border_radius=SS)
        pygame.draw.rect(s, (120, 230, 255), sr(cx - 0.75, 25, 1.5, 3))
    for ex in (17, 27):
        pygame.draw.rect(s, (55, 60, 75), sr(ex - 3, 38, 6, 12), border_radius=2 * SS)
        pygame.draw.rect(s, (255, 170, 80), sr(ex - 2, 48, 4, 2))
    body = [(22, 0), (27, 9), (29, 22), (28, 41), (25, 47), (19, 47), (16, 41), (15, 22), (17, 9)]
    gradient_polygon(s, sp(body), (235, 242, 255), (95, 105, 140), horizontal=True)
    pygame.draw.line(s, WHITE, sc(19.5, 9), sc(17, 30), SS)
    pygame.draw.line(s, (70, 80, 110), sc(22, 30), sc(22, 45), SS)
    pygame.draw.polygon(s, outline, sp(body), SS)
    pygame.draw.ellipse(s, (15, 25, 50), sr(18.5, 11, 7, 14))
    pygame.draw.ellipse(s, (60, 190, 255), sr(19.5, 12, 5, 12))
    pygame.draw.ellipse(s, (200, 245, 255), sr(20.2, 13, 1.8, 5))
    pygame.draw.circle(s, (255, 90, 90), sc(22, 4), int(1.1 * SS))


def draw_scout_sprite(s: pygame.Surface) -> None:
    wings = [(16, 12), (31, 2), (30, 9), (19, 22), (13, 22), (2, 9), (1, 2)]
    gradient_polygon(s, sp(wings), (110, 20, 45), (225, 55, 85))
    pygame.draw.polygon(s, (40, 5, 15), sp(wings), SS)
    for sign in (-1, 1):
        pygame.draw.line(s, (255, 130, 150), sc(16 + sign * 5, 11), sc(16 + sign * 13, 5), SS)
    body = [(16, 30), (20, 20), (20, 6), (16, 0), (12, 6), (12, 20)]
    gradient_polygon(s, sp(body), (215, 215, 230), (85, 85, 100), horizontal=True)
    pygame.draw.polygon(s, (30, 10, 20), sp(body), SS)
    pygame.draw.circle(s, (60, 20, 10), sc(16, 17), int(3.4 * SS))
    pygame.draw.circle(s, (255, 210, 60), sc(16, 17), int(2.6 * SS))
    pygame.draw.circle(s, WHITE, sc(15.4, 16.2), int(1.0 * SS))


def draw_fighter_sprite(s: pygame.Surface) -> None:
    wings = [(21, 10), (41, 0), (40, 18), (30, 28), (12, 28), (2, 18), (1, 0)]
    gradient_polygon(s, sp(wings), (60, 20, 95), (165, 65, 210))
    pygame.draw.polygon(s, (25, 5, 40), sp(wings), SS)
    panel = [(21, 14), (34, 7), (33, 16), (21, 22), (9, 16), (8, 7)]
    gradient_polygon(s, sp(panel), (40, 12, 65), (90, 35, 130))
    for gx in (6, 36):
        pygame.draw.rect(s, (150, 150, 170), sr(gx - 1.5, 10, 3, 18), border_radius=SS)
        pygame.draw.rect(s, (30, 25, 45), sr(gx - 1.5, 10, 3, 18), SS, border_radius=SS)
        pygame.draw.rect(s, (255, 90, 70), sr(gx - 1, 26, 2, 2))
    hull = [(21, 38), (26, 28), (26, 6), (21, 0), (16, 6), (16, 28)]
    gradient_polygon(s, sp(hull), (215, 210, 230), (90, 80, 115), horizontal=True)
    pygame.draw.polygon(s, (25, 15, 35), sp(hull), SS)
    pygame.draw.ellipse(s, (15, 30, 20), sr(17.5, 17, 7, 12))
    pygame.draw.ellipse(s, (90, 255, 150), sr(18.5, 18, 5, 10))
    pygame.draw.ellipse(s, (220, 255, 230), sr(19.3, 19, 1.6, 4))


def draw_heavy_sprite(s: pygame.Surface) -> None:
    for ex in (14, 50):
        pygame.draw.rect(s, (60, 60, 72), sr(ex - 5, 0, 10, 9), border_radius=2 * SS)
        pygame.draw.rect(s, (255, 150, 60), sr(ex - 3, 1, 6, 3), border_radius=SS)
    hull = [(32, 48), (44, 40), (62, 30), (63, 14), (52, 3), (12, 3), (1, 14), (2, 30), (20, 40)]
    gradient_polygon(s, sp(hull), (70, 45, 30), (190, 110, 45))
    pygame.draw.polygon(s, (35, 20, 10), sp(hull), SS)
    armor = [(32, 42), (42, 35), (54, 28), (54, 16), (46, 9), (18, 9), (10, 16), (10, 28), (22, 35)]
    gradient_polygon(s, sp(armor), (215, 140, 65), (120, 70, 35))
    pygame.draw.polygon(s, (60, 35, 15), sp(armor), SS)
    pygame.draw.line(s, (60, 35, 15), sc(10, 22), sc(22, 22), SS)
    pygame.draw.line(s, (60, 35, 15), sc(42, 22), sc(54, 22), SS)
    for gx, gy in ((20, 34), (32, 38), (44, 34)):
        pygame.draw.rect(s, (150, 150, 160), sr(gx - 2, gy, 4, 10), border_radius=SS)
        pygame.draw.rect(s, (40, 40, 50), sr(gx - 2, gy, 4, 10), SS, border_radius=SS)
    pygame.draw.circle(s, (40, 20, 20), sc(32, 22), int(7 * SS))
    pygame.draw.circle(s, (255, 90, 40), sc(32, 22), int(5 * SS))
    pygame.draw.circle(s, (255, 230, 180), sc(32, 22), int(2 * SS))
    for rx, ry in ((14, 14), (50, 14), (14, 30), (50, 30), (24, 12), (40, 12)):
        pygame.draw.circle(s, (250, 200, 130), sc(rx, ry), int(0.9 * SS))


def build_asteroid_sprite(radius: int) -> pygame.Surface:
    size = radius * 2 + 4

    def draw(s: pygame.Surface) -> None:
        c = size / 2
        n = random.randint(9, 13)
        pts = []
        for i in range(n):
            a = i / n * math.tau
            r = radius * random.uniform(0.78, 1.0)
            pts.append((c + math.cos(a) * r, c + math.sin(a) * r))
        gradient_polygon(s, sp(pts), (165, 150, 135), (55, 47, 42))
        for _ in range(radius // 6 + 2):
            a = random.uniform(0, math.tau)
            d = random.uniform(0, radius * 0.55)
            cx, cy = c + math.cos(a) * d, c + math.sin(a) * d
            cr = radius * random.uniform(0.1, 0.22)
            pygame.draw.circle(s, (70, 60, 54), sc(cx, cy), int(cr * SS))
            pygame.draw.circle(s, (150, 138, 125), sc(cx + cr * 0.25, cy + cr * 0.25), int(cr * SS), SS)
        pygame.draw.polygon(s, (30, 25, 22), sp(pts), SS)

    return build_sprite(size, size, draw)


def draw_pickup_sprite(s: pygame.Surface, kind: str) -> None:
    """Each pickup category has its own silhouette so they never read as bullets:
    weapons are hexagonal pods showing the gun, repair is a medkit, invincibility a star."""
    c = PICKUP_SIZE / 2
    color = PICKUPS[kind]["color"]
    dark = lerp_color(color, (10, 12, 25), 0.8)

    if kind == "repair":
        pygame.draw.rect(s, (255, 255, 255), sr(4, 4, 26, 26), border_radius=5 * SS)
        pygame.draw.rect(s, color, sr(4, 4, 26, 26), 2 * SS, border_radius=5 * SS)
        pygame.draw.rect(s, (225, 40, 60), sr(13.5, 8, 7, 18), border_radius=SS)
        pygame.draw.rect(s, (225, 40, 60), sr(8, 13.5, 18, 7), border_radius=SS)
        return

    if kind == "invincible":
        pts = []
        for i in range(10):
            a = i * math.pi / 5 - math.pi / 2
            r = 16 if i % 2 == 0 else 7
            pts.append((c + math.cos(a) * r, c + 1 + math.sin(a) * r))
        gradient_polygon(s, sp(pts), (255, 245, 170), (240, 160, 20))
        pygame.draw.polygon(s, WHITE, sp(pts), SS)
        pygame.draw.circle(s, WHITE, sc(c - 2, c - 2), int(2 * SS))
        return

    if kind == "slowmo":  # a clock face with an hourglass
        pygame.draw.circle(s, dark, sc(c, c), int(16 * SS))
        pygame.draw.circle(s, color, sc(c, c), int(16 * SS), int(2.2 * SS))
        for i in range(12):
            a = i * math.tau / 12
            pygame.draw.circle(s, color, sc(c + math.cos(a) * 12.5, c + math.sin(a) * 12.5), int(0.8 * SS))
        top = [(c - 6, c - 9), (c + 6, c - 9), (c, c)]
        bottom = [(c, c), (c + 6, c + 9), (c - 6, c + 9)]
        pygame.draw.polygon(s, (235, 230, 255), sp(top))
        pygame.draw.polygon(s, (235, 230, 255), sp(bottom))
        pygame.draw.polygon(s, (255, 210, 120), sp([(c - 3, c + 9), (c + 3, c + 9), (c, c + 4)]))
        pygame.draw.line(s, WHITE, sc(c - 7, c - 9), sc(c + 7, c - 9), SS)
        pygame.draw.line(s, WHITE, sc(c - 7, c + 9), sc(c + 7, c + 9), SS)
        return

    hexagon = [(c + math.cos(math.radians(60 * i)) * 16, c + math.sin(math.radians(60 * i)) * 16) for i in range(6)]
    gradient_polygon(s, sp(hexagon), lerp_color(dark, WHITE, 0.1), dark)
    pygame.draw.polygon(s, color, sp(hexagon), int(2.2 * SS))

    if kind == "blaster":
        for bx in (12.5, 21.5):
            pygame.draw.rect(s, color, sr(bx - 2, 8, 4, 16), border_radius=2 * SS)
            pygame.draw.line(s, WHITE, sc(bx, 10), sc(bx, 21), SS)
        pygame.draw.rect(s, (150, 160, 180), sr(9, 23, 16, 4), border_radius=SS)
    elif kind == "spread":
        for end in ((7, 11), (12, 7), (17, 6), (22, 7), (27, 11)):
            pygame.draw.line(s, color, sc(17, 26), sc(*end), int(1.6 * SS))
            pygame.draw.circle(s, WHITE, sc(*end), int(1.8 * SS))
        pygame.draw.circle(s, color, sc(17, 26), int(2.5 * SS))
    elif kind == "laser":
        pygame.draw.rect(s, color, sr(14, 5, 6, 19))
        pygame.draw.rect(s, WHITE, sr(16, 5, 2, 19))
        pygame.draw.rect(s, (150, 160, 180), sr(11, 23, 12, 5), border_radius=SS)
    elif kind == "missile":
        for mx in (12.5, 21.5):
            pygame.draw.polygon(s, (255, 80, 60), sp([(mx, 6), (mx - 2.5, 11), (mx + 2.5, 11)]))
            pygame.draw.rect(s, (235, 235, 245), sr(mx - 2.5, 11, 5, 11))
            pygame.draw.polygon(s, color, sp([(mx - 2.5, 17), (mx - 5, 23), (mx - 2.5, 22)]))
            pygame.draw.polygon(s, color, sp([(mx + 2.5, 17), (mx + 5, 23), (mx + 2.5, 22)]))
            pygame.draw.polygon(s, (255, 200, 80), sp([(mx - 1.5, 22), (mx + 1.5, 22), (mx, 28)]))
    elif kind == "nuke":  # radiation trefoil
        pygame.draw.circle(s, (255, 225, 40), sc(c, c), int(11 * SS))
        for centre in (-90, 30, 150):
            pts = [
                (c + math.cos(math.radians(a)) * r, c + math.sin(math.radians(a)) * r)
                for r, angles in (
                    (3.5, range(centre - 30, centre + 31, 10)),
                    (10, range(centre + 30, centre - 31, -10)),
                )
                for a in angles
            ]
            pygame.draw.polygon(s, (20, 20, 20), sp(pts))
        pygame.draw.circle(s, (20, 20, 20), sc(c, c), int(2.4 * SS))
        pygame.draw.circle(s, color, sc(c, c), int(11 * SS), SS)


SPRITES: dict[str, pygame.Surface] = {}


ASTEROID_SPRITES: dict[str, list[pygame.Surface]] = {}  # several random shapes per asteroid size


def load_sprites() -> None:
    SPRITES["player"] = build_sprite(*PLAYER_SIZE, draw_player_sprite)
    SPRITES["life_icon"] = pygame.transform.smoothscale(SPRITES["player"], (15, 18))
    for kind, fn in (("scout", draw_scout_sprite), ("fighter", draw_fighter_sprite), ("heavy", draw_heavy_sprite)):
        w, h = ENEMY_TYPES[kind]["size"]
        SPRITES[kind] = build_sprite(w, h, fn)
        SPRITES[kind + "_flash"] = make_flash(SPRITES[kind])
    for size, radius in ASTEROID_RADII.items():
        ASTEROID_SPRITES[size] = [build_asteroid_sprite(radius) for _ in range(4)]
    for kind in PICKUPS:
        SPRITES["pickup_" + kind] = build_sprite(PICKUP_SIZE, PICKUP_SIZE, partial(draw_pickup_sprite, kind=kind))
    SPRITES["pylon"] = build_sprite(18, 34, draw_pylon_sprite)
    SPRITES["mine"] = build_sprite(28, 28, draw_mine_sprite)
    SPRITES["mine_flash"] = make_flash(SPRITES["mine"])
    SPRITES["hub"] = build_sprite(40, 40, draw_hub_sprite)
    SPRITES["boss"] = build_sprite(*BOSS_SIZE, draw_boss_sprite)
    SPRITES["hud_slowmo"] = pygame.transform.smoothscale(SPRITES["pickup_slowmo"], (18, 18))
    for kind in WEAPON_ORDER:
        SPRITES["tray_" + kind] = pygame.transform.smoothscale(SPRITES["pickup_" + kind], (24, 24))


def build_nebula() -> pygame.Surface:
    surf = pygame.Surface((cfg.WIDTH, HEIGHT))
    surf.fill(BG)
    small = pygame.Surface((cfg.WIDTH // 4, HEIGHT // 4), pygame.SRCALPHA)
    palette = [(70, 25, 110), (25, 45, 120), (100, 25, 70), (20, 80, 100)]
    sw, sh = small.get_size()
    for _ in range(22):
        r = random.randint(10, 34)
        x, y = random.uniform(0, sw), random.uniform(0, sh)
        blob = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(blob, (*random.choice(palette), random.randint(25, 55)), (r, r), r)
        for yy in (y - sh, y, y + sh):  # wrap vertically so the scroll tiles seamlessly
            small.blit(blob, (int(x - r), int(yy - r)))
    blurred = pygame.transform.smoothscale(small, (sw // 3, sh // 3))
    blurred = pygame.transform.smoothscale(blurred, (cfg.WIDTH, HEIGHT))
    surf.blit(blurred, (0, 0))
    return surf


def draw_pylon_sprite(s: pygame.Surface) -> None:
    gradient_polygon(s, sp([(1, 0), (17, 0), (17, 34), (1, 34)]), (150, 155, 170), (45, 48, 58), horizontal=True)
    pygame.draw.rect(s, (20, 22, 30), sr(1, 0, 16, 34), SS)
    for yy in (4, 28):
        pygame.draw.rect(s, (240, 200, 40), sr(2, yy, 14, 3))
    pygame.draw.circle(s, (20, 22, 30), sc(9, 17), int(6 * SS))


def draw_mine_sprite(s: pygame.Surface) -> None:
    c = 14
    for i in range(8):
        a = i * math.tau / 8
        tip = (c + math.cos(a) * 14, c + math.sin(a) * 14)
        left = (c + math.cos(a - 0.3) * 8, c + math.sin(a - 0.3) * 8)
        right = (c + math.cos(a + 0.3) * 8, c + math.sin(a + 0.3) * 8)
        pygame.draw.polygon(s, (150, 150, 165), sp([left, tip, right]))
        pygame.draw.polygon(s, (30, 30, 40), sp([left, tip, right]), SS)
    pygame.draw.circle(s, (30, 30, 40), sc(c, c), int(9.5 * SS))
    pygame.draw.circle(s, (85, 85, 100), sc(c, c), int(8.5 * SS))
    pygame.draw.circle(s, (130, 130, 150), sc(c - 2, c - 2), int(5 * SS))
    pygame.draw.circle(s, (85, 85, 100), sc(c, c), int(4 * SS))
    pygame.draw.circle(s, (20, 10, 10), sc(c, c), int(3 * SS))


def draw_hub_sprite(s: pygame.Surface) -> None:
    c = 20
    pygame.draw.circle(s, (25, 27, 35), sc(c, c), int(19 * SS))
    pygame.draw.circle(s, (120, 125, 140), sc(c, c), int(17 * SS))
    pygame.draw.circle(s, (80, 84, 98), sc(c, c), int(12 * SS))
    for i in range(6):
        a = i * math.tau / 6
        pygame.draw.circle(s, (210, 215, 225), sc(c + math.cos(a) * 14.5, c + math.sin(a) * 14.5), int(1.4 * SS))
    pygame.draw.circle(s, (240, 200, 40), sc(c, c), int(6 * SS))
    pygame.draw.circle(s, (25, 25, 25), sc(c, c), int(6 * SS), SS)
    pygame.draw.line(s, (25, 25, 25), sc(c - 4, c - 4), sc(c + 4, c + 4), 2 * SS)


def draw_boss_sprite(s: pygame.Surface) -> None:
    cx, cy = BOSS_SIZE[0] / 2, BOSS_SIZE[1] / 2
    hull = [
        (160, 148),
        (200, 120),
        (300, 96),
        (318, 62),
        (300, 30),
        (232, 18),
        (205, 2),
        (115, 2),
        (88, 18),
        (20, 30),
        (2, 62),
        (20, 96),
        (120, 120),
    ]
    gradient_polygon(s, sp(hull), (125, 130, 150), (45, 48, 60))
    pygame.draw.polygon(s, (20, 22, 30), sp(hull), 2 * SS)
    inner = [
        (160, 132),
        (192, 110),
        (280, 88),
        (296, 62),
        (282, 40),
        (222, 30),
        (200, 14),
        (120, 14),
        (98, 30),
        (38, 40),
        (24, 62),
        (40, 88),
        (128, 110),
    ]
    gradient_polygon(s, sp(inner), (100, 105, 122), (58, 62, 76))
    pygame.draw.polygon(s, (30, 32, 42), sp(inner), SS)
    for sign in (-1, 1):
        stripe = [(cx + sign * 40, 38), (cx + sign * 132, 47), (cx + sign * 134, 53), (cx + sign * 42, 45)]
        pygame.draw.polygon(s, (200, 40, 50), sp(stripe))
        for px in (30, 82, 140):
            pygame.draw.line(s, (38, 40, 52), sc(cx + sign * px, 22), sc(cx + sign * px, 104 - px * 0.25), SS)
        for i in range(6):
            pygame.draw.circle(s, (190, 195, 210), sc(cx + sign * (40 + i * 22), 100 - i * 4), int(0.9 * SS))
    for ex in (125, 160, 195):
        pygame.draw.rect(s, (50, 52, 62), sr(ex - 10, 0, 20, 12), border_radius=2 * SS)
        pygame.draw.rect(s, (255, 140, 60), sr(ex - 7, 1, 14, 3))
    for ox, oy in BOSS_TURRETS:
        pygame.draw.circle(s, (25, 27, 35), sc(cx + ox, cy + oy), int(19 * SS))
        pygame.draw.circle(s, (85, 90, 105), sc(cx + ox, cy + oy), int(17 * SS))
        pygame.draw.circle(s, (40, 42, 52), sc(cx + ox, cy + oy), int(15 * SS))
    core = (cx, cy + BOSS_CORE_OFFSET)
    pygame.draw.circle(s, (20, 22, 30), sc(*core), int(31 * SS))
    pygame.draw.circle(s, (75, 80, 98), sc(*core), int(29 * SS))
    pygame.draw.circle(s, (30, 18, 22), sc(*core), int(23 * SS))
    for i in range(3):
        pygame.draw.circle(s, (255, 90, 90), sc(cx, 118 + i * 9), int(1.6 * SS))
