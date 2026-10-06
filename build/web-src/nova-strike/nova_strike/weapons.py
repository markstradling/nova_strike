"""Player projectiles and collectable power-ups."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from functools import partial
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .config import CYAN, HEIGHT, ORANGE, PICKUP_SIZE, PICKUP_WEIGHTS, PICKUPS, WEAPONS, WHITE
from .gfx import blit_glow, clamp, get_font, rotated
from .sprites import SPRITES

if TYPE_CHECKING:
    from .config import Color, Target


class Bullet:
    def __init__(
        self,
        x: float,
        y: float,
        *,
        vx: float = 0,
        vy: float = -640,
        enemy: bool = False,
        color: Color = CYAN,
        radius: int = 3,
        damage: float = 1,
    ) -> None:
        self.x, self.y = x, y
        self.prev_x, self.prev_y = x, y
        self.vx, self.vy = vx, vy
        self.enemy = enemy
        self.color = color
        self.radius = radius
        self.damage = damage
        self.alive = True
        self.hw, self.hh = (radius, radius) if enemy else (2, 7)

    def update(self, dt: float) -> None:
        self.prev_x, self.prev_y = self.x, self.y
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.y < -20 or self.y > HEIGHT + 20 or self.x < -20 or self.x > cfg.WIDTH + 20:
            self.alive = False

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.hw), int(self.y - self.hh), self.hw * 2, self.hh * 2)

    def sweep_rect(self) -> pygame.Rect:
        """Rect covering the whole path travelled this frame, so fast shots can't tunnel."""
        left = min(self.x, self.prev_x) - self.hw
        top = min(self.y, self.prev_y) - self.hh
        right = max(self.x, self.prev_x) + self.hw
        bottom = max(self.y, self.prev_y) + self.hh
        return pygame.Rect(int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top)))

    def draw(self, surface: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        if self.enemy:
            blit_glow(surface, x, y, self.radius * 4, self.color)
            pygame.draw.circle(surface, self.color, (x, y), self.radius)
            pygame.draw.circle(surface, WHITE, (x, y), max(1, self.radius - 2))
        else:
            blit_glow(surface, x, y, 12, self.color)
            pygame.draw.rect(surface, self.color, (x - 2, y - 7, 4, 14), border_radius=2)
            pygame.draw.line(surface, WHITE, (x, y - 5), (x, y + 5))


def random_pickup_kind() -> str:
    kinds = list(PICKUP_WEIGHTS)
    return random.choices(kinds, weights=[PICKUP_WEIGHTS[k] for k in kinds])[0]


class PowerUp:
    def __init__(self, x: float, y: float, kind: str) -> None:
        self.x, self.y = x, y
        self.kind = kind
        self.color = PICKUPS[kind]["color"]
        self.sprite = SPRITES["pickup_" + kind]
        font = get_font(11, bold=True)
        name = PICKUPS[kind]["name"]
        self.label = font.render(name, True, self.color)
        self.label_shadow = font.render(name, True, (0, 0, 0))
        self.age = 0.0
        self.alive = True

    def update(self, dt: float) -> None:
        self.age += dt
        self.y += 80 * dt
        self.x += math.sin(self.age * 3) * 25 * dt
        if self.y > HEIGHT + 20:
            self.alive = False

    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 15), int(self.y - 15), 30, 30)

    def draw(self, surface: pygame.Surface) -> None:
        x, y = int(self.x), int(self.y)
        blit_glow(surface, x, y, 26, self.color, strength=0.45 + 0.15 * math.sin(self.age * 6))

        # Expanding beacon ring, once a second, to draw the eye.
        ring_t = self.age % 1.0
        ring_color = tuple(int(c * (1 - ring_t)) for c in self.color)
        pygame.draw.circle(surface, ring_color, (x, y), int(18 + ring_t * 16), 2)

        sprite = self.sprite
        if self.kind == "invincible":
            sprite = pygame.transform.rotozoom(sprite, -self.age * 120, 1.0)
        else:
            scale = 1.0 + 0.06 * math.sin(self.age * 5)
            sprite = pygame.transform.rotozoom(sprite, 0, scale)
        surface.blit(sprite, sprite.get_rect(center=(x, y)))

        ly = y + PICKUP_SIZE // 2 + 8
        surface.blit(self.label_shadow, self.label_shadow.get_rect(center=(x + 1, ly + 1)))
        surface.blit(self.label, self.label.get_rect(center=(x, ly)))


class Missile(Bullet):
    """Homing missile: accelerates and turns towards the nearest enemy."""

    def __init__(self, x: float, y: float, angle: float) -> None:
        super().__init__(x, y, color=WEAPONS["missile"]["color"], damage=3)
        self.hw = self.hh = 4
        self.angle = angle
        self.speed = 260.0
        self.target: Target | None = None
        self.turn_rate = 5.0
        self.age = 0.0
        self.set_velocity()

    def set_velocity(self) -> None:
        self.vx = math.cos(self.angle) * self.speed
        self.vy = math.sin(self.angle) * self.speed

    def steer(self, dt: float, enemies: Sequence[Target]) -> None:
        if self.target is None or not self.target.alive:
            live = [e for e in enemies if e.alive and e.y > -10]
            self.target = min(live, key=lambda e: math.hypot(e.x - self.x, e.y - self.y)) if live else None
        if self.target:
            desired = math.atan2(self.target.y - self.y, self.target.x - self.x)
            diff = (desired - self.angle + math.pi) % math.tau - math.pi
            self.angle += clamp(diff, -self.turn_rate * dt, self.turn_rate * dt)
        self.speed = min(560, self.speed + 500 * dt)
        self.set_velocity()

    def update(self, dt: float) -> None:
        self.age += dt
        super().update(dt)
        if self.age > 3.0:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        pt = partial(rotated, self.x, self.y, self.angle)
        blit_glow(surface, *pt(-7, 0), 9, ORANGE)
        pygame.draw.polygon(surface, (90, 90, 100), [pt(-6, -4), pt(-3, 0), pt(-6, 4)])
        pygame.draw.polygon(surface, (225, 225, 235), [pt(7, 0), pt(3, -2), pt(-6, -2), pt(-6, 2), pt(3, 2)])
        pygame.draw.polygon(surface, (255, 90, 60), [pt(7, 0), pt(3, -2), pt(3, 2)])
