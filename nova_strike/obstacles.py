"""Scrolling obstacles: asteroids, girder walls, laser gates, mines and spinners."""

from __future__ import annotations

import math
import random
from functools import partial
from typing import TYPE_CHECKING, ClassVar

import pygame

from . import config as cfg
from .config import ASTEROID_RADII, HEIGHT, WHITE
from .gfx import blit_glow, circle_hits_rect, clamp, lerp_color, make_flash, rotated
from .sprites import ASTEROID_SPRITES, SPRITES

if TYPE_CHECKING:
    from .config import Point
    from .game import Game


class Asteroid:
    HP: ClassVar[dict[str, int]] = {"large": 6, "small": 2}
    SCORE: ClassVar[dict[str, int]] = {"large": 20, "small": 10}
    RAM: ClassVar[dict[str, int]] = {"large": 40, "small": 20}

    def __init__(self, size: str, x: float, y: float, vx: float, vy: float) -> None:
        self.size = size
        self.radius = ASTEROID_RADII[size]
        self.sprite = random.choice(ASTEROID_SPRITES[size])
        self.flash_sprite = make_flash(self.sprite)
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.angle = random.uniform(0, 360)
        self.spin = random.uniform(-90, 90)
        self.health: float = self.HP[size]
        self.score_value = self.SCORE[size]
        self.ram_damage = self.RAM[size]
        self.flash = 0.0
        self.alive = True

    def update(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle = (self.angle + self.spin * dt) % 360
        self.flash = max(0.0, self.flash - dt)
        if self.x < self.radius or self.x > cfg.WIDTH - self.radius:
            self.vx = -self.vx
            self.x = clamp(self.x, self.radius, cfg.WIDTH - self.radius)
        if self.y > HEIGHT + self.radius * 2:
            self.alive = False

    def hits_rect(self, rect: pygame.Rect) -> bool:
        return circle_hits_rect(self.x, self.y, self.radius * 0.85, rect)

    def hit(self, dmg: float) -> bool:
        self.health -= dmg
        self.flash = 0.06
        if self.health <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        sprite = self.flash_sprite if self.flash > 0 else self.sprite
        rotated = pygame.transform.rotozoom(sprite, self.angle, 1.0)
        surface.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))))


def draw_girder(
    surf: pygame.Surface, a: int, b: int, h: int, *, cap_left: bool = False, cap_right: bool = False
) -> None:
    """Steel truss girder occupying x in [a, b) of surf, with optional hazard-striped end caps."""
    seg = pygame.Rect(a, 0, b - a, h)
    surf.set_clip(seg)
    for i in range(h):
        pygame.draw.line(surf, lerp_color((120, 125, 140), (40, 43, 52), i / h), (a, i), (b, i))
    for tx in range(a - (a % 24), b, 24):
        pygame.draw.line(surf, (30, 32, 40), (tx, 4), (tx + 12, h - 4), 2)
        pygame.draw.line(surf, (30, 32, 40), (tx + 12, h - 4), (tx + 24, 4), 2)
    pygame.draw.rect(surf, (175, 180, 195), (a, 0, b - a, 4))
    pygame.draw.rect(surf, (70, 74, 88), (a, h - 4, b - a, 4))
    for rx in range(a + 6, b - 4, 12):
        pygame.draw.circle(surf, (220, 225, 235), (rx, 2), 1)
        pygame.draw.circle(surf, (110, 115, 130), (rx, h - 2), 1)
    for cap_x, wanted in ((a, cap_left), (b - 10, cap_right)):
        if wanted:
            draw_hazard_cap(surf, cap_x, h)
            surf.set_clip(seg)
    surf.set_clip(None)
    pygame.draw.rect(surf, (15, 16, 22), seg, 1)


def draw_hazard_cap(surf: pygame.Surface, x: int, h: int, w: int = 10) -> None:
    cap = pygame.Rect(x, 0, w, h)
    surf.set_clip(cap)
    surf.fill((240, 200, 40), cap)
    for sx in range(x - h, x + w, 7):
        pygame.draw.line(surf, (25, 25, 25), (sx, h), (sx + h, 0), 3)
    surf.set_clip(None)
    pygame.draw.rect(surf, (15, 16, 22), cap, 1)


class Wall:
    """A girder wall spanning the screen with one or two gaps to fly through."""

    H = 22

    def __init__(self, level: int, speed: float) -> None:
        gap_w = max(100, 160 - level * 6)
        gaps = 2 if level >= 3 and random.random() < 0.5 else 1
        lo, hi = gap_w / 2 + 12, cfg.WIDTH - gap_w / 2 - 12
        for _ in range(50):
            centers = sorted(random.uniform(lo, hi) for _ in range(gaps))
            if gaps == 1 or centers[1] - centers[0] > gap_w * 1.8:
                break
        else:
            centers = [random.uniform(lo, hi)]
        segments: list[tuple[float, float]] = []
        x = 0.0
        for c in centers:
            segments.append((x, c - gap_w / 2))
            x = c + gap_w / 2
        segments.append((x, cfg.WIDTH))
        self.segments = [(int(a), int(b)) for a, b in segments if b - a > 4]
        self.y: float = -self.H
        self.speed = speed
        self.age = 0.0
        self.alive = True
        self.render()

    def render(self) -> None:
        self.surface = pygame.Surface((cfg.WIDTH, self.H), pygame.SRCALPHA)
        for a, b in self.segments:
            draw_girder(self.surface, a, b, self.H, cap_left=a > 0, cap_right=b < cfg.WIDTH)

    def rescale(self, ratio: float, old_width: int) -> None:
        self.segments = [
            (round(a * ratio), cfg.WIDTH if b >= old_width else round(b * ratio)) for a, b in self.segments
        ]
        self.render()

    def rects(self) -> list[pygame.Rect]:
        return [pygame.Rect(a, int(self.y), b - a, self.H) for a, b in self.segments]

    def segments_at(self, ahead: float) -> list[tuple[int, int]]:
        """Solid spans `ahead` seconds from now (fixed for a plain wall)."""
        return self.segments

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        self.age += dt
        if self.y > HEIGHT:
            self.alive = False

    def draw_gap_lights(self, surface: pygame.Surface) -> None:
        if int(self.age * 4) % 2 == 0:
            cy = int(self.y + self.H / 2)
            for a, b in self.segments:
                for lx, facing_gap in ((a + 5, a > 0), (b - 5, b < cfg.WIDTH)):
                    if facing_gap:
                        blit_glow(surface, lx, cy, 14, (255, 50, 40))
                        pygame.draw.circle(surface, (255, 200, 190), (lx, cy), 3)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.surface, (0, int(self.y)))
        self.draw_gap_lights(surface)


class SlidingWall(Wall):
    """A girder wall whose single gap slides from side to side as it scrolls down."""

    def __init__(
        self, level: int, speed: float
    ) -> None:  # sets up its own moving segments instead of calling Wall.__init__
        self.gap_w = max(110, 170 - level * 5)
        self.amp = random.uniform(80, cfg.WIDTH / 2 - self.gap_w / 2 - 20)
        self.freq = random.uniform(0.9, 1.3) + level * 0.03
        self.phase = random.uniform(0, math.tau)
        self.y: float = -self.H
        self.speed = speed
        self.age = 0.0
        self.alive = True
        self.render()
        self.cap = pygame.Surface((10, self.H), pygame.SRCALPHA)
        draw_hazard_cap(self.cap, 0, self.H)
        self._place()

    def render(self) -> None:
        self.girder = pygame.Surface((cfg.WIDTH, self.H), pygame.SRCALPHA)
        draw_girder(self.girder, 0, cfg.WIDTH, self.H)

    def rescale(self, ratio: float, old_width: int) -> None:
        self.amp *= ratio
        self.render()
        self._place()

    def _place(self) -> None:
        self.segments = self.segments_at(0.0)

    def segments_at(self, ahead: float) -> list[tuple[int, int]]:
        c = cfg.WIDTH / 2 + math.sin((self.age + ahead) * self.freq + self.phase) * self.amp
        return [(0, int(c - self.gap_w / 2)), (int(c + self.gap_w / 2), cfg.WIDTH)]

    def update(self, dt: float) -> None:
        super().update(dt)
        self._place()

    def draw(self, surface: pygame.Surface) -> None:
        y = int(self.y)
        (_, left_end), (right_start, _) = self.segments
        surface.blit(self.girder, (0, y), area=pygame.Rect(0, 0, left_end, self.H))
        surface.blit(self.girder, (right_start, y), area=pygame.Rect(right_start, 0, cfg.WIDTH - right_start, self.H))
        surface.blit(self.cap, (left_end - 10, y))
        surface.blit(self.cap, (right_start, y))
        # chevrons in the gap show which way it is sliding
        direction = 1 if math.cos(self.age * self.freq + self.phase) > 0 else -1
        cx, cy = (left_end + right_start) / 2, y + self.H / 2
        for i in (-1, 0, 1):
            px = cx + i * 12
            pygame.draw.lines(
                surface,
                (255, 200, 60),
                False,
                [(px - 3 * direction, cy - 5), (px + 3 * direction, cy), (px - 3 * direction, cy + 5)],
                2,
            )
        self.draw_gap_lights(surface)


class LaserGate:
    """A full-width energy beam between two pylons that cycles off -> warning -> on."""

    name = "LASER GATES"
    damage = 25
    PYLON_W = 18
    WARN = 0.5

    def __init__(self, level: int, speed: float) -> None:
        self.y = -20.0
        self.speed = speed
        self.age = 0.0
        self.alive = True
        self.on_time = 1.2 + min(0.6, level * 0.06)
        self.off_time = max(1.0, 1.6 - level * 0.05)
        self.phase = random.uniform(0, self.on_time + self.off_time)

    def state(self, ahead: float = 0.0) -> str:
        """The beam's state now, or `ahead` seconds from now: "off", "warn" or "on"."""
        t = (self.age + ahead + self.phase) % (self.on_time + self.off_time)
        if t < self.off_time - self.WARN:
            return "off"
        return "warn" if t < self.off_time else "on"

    def beam_rect(self) -> pygame.Rect:
        return pygame.Rect(self.PYLON_W, int(self.y - 4), cfg.WIDTH - 2 * self.PYLON_W, 8)

    def pylon_rects(self) -> list[pygame.Rect]:
        top = int(self.y - 17)
        return [pygame.Rect(0, top, self.PYLON_W, 34), pygame.Rect(cfg.WIDTH - self.PYLON_W, top, self.PYLON_W, 34)]

    def touches(self, rect: pygame.Rect) -> bool:
        if rect.collidelist(self.pylon_rects()) != -1:
            return True
        return self.state() == "on" and rect.colliderect(self.beam_rect())

    blocks = touches

    def laser_stop(self, x: float, half: float, top: float) -> float | None:
        beam = self.beam_rect()
        if self.state() == "on" and beam.bottom <= top:
            return beam.bottom
        return None

    def update(self, dt: float, game: Game) -> None:
        was_on = self.state() == "on"
        self.y += self.speed * dt
        self.age += dt
        if not was_on and self.state() == "on" and 0 < self.y < HEIGHT:
            game.sfx.play("gate_on")
        if self.y > HEIGHT + 20:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        state = self.state()
        y = int(self.y)
        x0, x1 = self.PYLON_W, cfg.WIDTH - self.PYLON_W
        if state == "on":
            beam = pygame.Surface((x1 - x0, 20))
            for half, color in ((9, (70, 10, 20)), (5, (150, 25, 45)), (3, (255, 60, 90)), (1, (255, 230, 235))):
                pygame.draw.rect(beam, color, (0, 10 - half, x1 - x0, half * 2))
            surface.blit(beam, (x0, y - 10), special_flags=pygame.BLEND_RGB_ADD)
            pts = [(x, y + random.uniform(-4, 4)) for x in range(x0, x1 + 1, 16)]
            pygame.draw.lines(surface, (255, 190, 210), False, pts, 1)
        elif state == "warn":
            if int(self.age * 16) % 2 == 0:
                pygame.draw.line(surface, (200, 60, 70), (x0, y), (x1, y), 1)
        else:
            for x in range(x0 + 4, x1, 14):
                pygame.draw.line(surface, (90, 40, 55), (x, y), (x + 5, y))

        lens = {"off": (80, 255, 120), "warn": (255, 210, 60), "on": (255, 60, 80)}[state]
        for px in (0, cfg.WIDTH - self.PYLON_W):
            surface.blit(SPRITES["pylon"], (px, y - 17))
            cx = px + self.PYLON_W // 2
            blit_glow(surface, cx, y, 16, lens, strength=0.9)
            pygame.draw.circle(surface, lens, (cx, y), 4)
            pygame.draw.circle(surface, WHITE, (cx, y), 2)


class Mine:
    """Spiked mine that homes in once you get close. Shoot it and the blast hurts anything nearby."""

    name = "MINE FIELDS"
    RADIUS = 12
    BLAST = 60
    ARM_RANGE = 150
    damage = 35
    score_value = 25

    def __init__(self, x: float, y: float, speed: float) -> None:
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, speed
        self.speed = speed
        self.health: float = 2
        self.angle = random.uniform(0, 360)
        self.armed = False
        self.age = 0.0
        self.flash = 0.0
        self.alive = True

    def hits_rect(self, rect: pygame.Rect) -> bool:
        return circle_hits_rect(self.x, self.y, self.RADIUS * 0.9, rect)

    touches = blocks = hits_rect

    def laser_stop(self, x: float, half: float, top: float) -> float | None:
        if self.y < top and abs(self.x - x) < self.RADIUS + half:
            return self.y + self.RADIUS * 0.6
        return None

    def hit(self, dmg: float) -> bool:
        self.health -= dmg
        self.flash = 0.06
        return self.health <= 0

    def update(self, dt: float, game: Game) -> None:
        self.age += dt
        self.flash = max(0.0, self.flash - dt)
        p = game.player
        if p.alive:
            dx, dy = p.x - self.x, p.y - self.y
            d = math.hypot(dx, dy) or 1
            if d < self.ARM_RANGE and not self.armed:
                self.armed = True
                game.sfx.play("mine_arm")
            if self.armed:
                ease = min(1.0, dt * 2.5)
                self.vx += (dx / d * 140 - self.vx) * ease
                self.vy += (dy / d * 140 + self.speed * 0.4 - self.vy) * ease
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.angle = (self.angle + (180 if self.armed else 40) * dt) % 360
        if self.y > HEIGHT + 30 or not -40 < self.x < cfg.WIDTH + 40:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        sprite = SPRITES["mine_flash"] if self.flash > 0 else SPRITES["mine"]
        rotated = pygame.transform.rotozoom(sprite, self.angle, 1.0)
        surface.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))))
        if int(self.age * (12 if self.armed else 3)) % 2 == 0:
            blit_glow(surface, self.x, self.y, 14 if self.armed else 9, (255, 40, 40))
            pygame.draw.circle(surface, (255, 120, 110), (int(self.x), int(self.y)), 2)
        if self.armed:
            pulse = (self.age * 2) % 1.0
            color = tuple(int(c * (1 - pulse) * 0.6) for c in (255, 60, 60))
            pygame.draw.circle(surface, color, (int(self.x), int(self.y)), int(self.RADIUS + 4 + pulse * 20), 1)


class Spinner:
    """A hub with rotating girder arms: wait for an arm to sweep past, then slip by."""

    name = "SPINNERS"
    damage = 30
    HUB = 18
    ARM_W = 10

    def __init__(self, level: int, speed: float) -> None:
        self.arm_len = random.uniform(85, 115)
        self.x = random.uniform(self.arm_len * 0.6, cfg.WIDTH - self.arm_len * 0.6)
        self.y = -self.arm_len
        self.speed = speed
        self.arms = 3 if level >= 4 and random.random() < 0.5 else 2
        self.omega = random.choice((-1, 1)) * random.uniform(1.1, 1.6 + level * 0.05)
        self.angle = random.uniform(0, math.tau)
        self.age = 0.0
        self.alive = True

    def arm_angles(self) -> list[float]:
        return [self.angle + i * math.tau / self.arms for i in range(self.arms)]

    def touches(self, rect: pygame.Rect) -> bool:
        if circle_hits_rect(self.x, self.y, self.HUB, rect):
            return True
        for a in self.arm_angles():
            ca, sa = math.cos(a), math.sin(a)
            d = self.HUB
            while d <= self.arm_len:
                if circle_hits_rect(self.x + ca * d, self.y + sa * d, self.ARM_W / 2 + 1, rect):
                    return True
                d += 7
        return False

    blocks = touches

    def laser_stop(self, x: float, half: float, top: float) -> float | None:
        if self.y < top and abs(self.x - x) < self.HUB + half:
            return self.y + self.HUB * 0.6
        return None

    def update(self, dt: float, game: Game) -> None:
        self.age += dt
        self.y += self.speed * dt
        self.angle += self.omega * dt
        if self.y > HEIGHT + self.arm_len:
            self.alive = False

    def arm_point(self, angle: float, d: float, side: float) -> Point:
        """Point d along an arm; side is -1/+1 for its two edges, 0 for its centre line."""
        return rotated(self.x, self.y, angle, d, side * self.ARM_W / 2)

    def draw(self, surface: pygame.Surface) -> None:
        for a in self.arm_angles():
            at = partial(self.arm_point, a)
            body = [at(0, -1), at(self.arm_len - 10, -1), at(self.arm_len - 10, 1), at(0, 1)]
            pygame.draw.polygon(surface, (105, 110, 125), body)
            pygame.draw.line(surface, (180, 185, 200), at(0, -1), at(self.arm_len - 10, -1), 2)
            d = self.HUB
            while d < self.arm_len - 18:
                pygame.draw.line(surface, (45, 48, 58), at(d, -1), at(d + 8, 1), 2)
                d += 12
            cap = [at(self.arm_len - 10, -1), at(self.arm_len, -1), at(self.arm_len, 1), at(self.arm_len - 10, 1)]
            pygame.draw.polygon(surface, (240, 200, 40), cap)
            pygame.draw.line(surface, (25, 25, 25), at(self.arm_len - 7, -1), at(self.arm_len - 3, 1), 2)
            pygame.draw.polygon(surface, (20, 22, 30), body + cap[1:3], 1)
            if int(self.age * 4) % 2 == 0:
                tx, ty = at(self.arm_len - 2, 0)
                blit_glow(surface, tx, ty, 12, (255, 50, 40))
        hub = pygame.transform.rotozoom(SPRITES["hub"], -math.degrees(self.angle), 1.0)
        surface.blit(hub, hub.get_rect(center=(int(self.x), int(self.y))))


Hazard = LaserGate | Mine | Spinner
