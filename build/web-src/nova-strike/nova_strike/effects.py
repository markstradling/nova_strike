"""Purely visual effects: background stars, particles, shockwaves and floating text."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .config import HEIGHT
from .gfx import blit_glow, clamp, get_font

if TYPE_CHECKING:
    from .config import Color


class Star:
    def __init__(self) -> None:
        self.x = random.uniform(0, cfg.WIDTH)
        self.y = random.uniform(0, HEIGHT)
        self.speed = random.uniform(30, 260)
        self.size = 1 if self.speed < 140 else 2

    def update(self, dt: float) -> None:
        self.y += self.speed * dt
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.uniform(0, cfg.WIDTH)

    def draw(self, surface: pygame.Surface) -> None:
        shade = clamp(int(self.speed), 70, 255)
        color = (shade, shade, min(255, shade + 30))
        if self.speed > 200:
            pygame.draw.line(surface, (shade // 3, shade // 3, shade // 2), (self.x, self.y - 6), (self.x, self.y))
        pygame.draw.rect(surface, color, (int(self.x), int(self.y), self.size, self.size))


class Particle:
    def __init__(
        self,
        x: float,
        y: float,
        color: Color,
        *,
        speed: tuple[float, float] = (40, 260),
        life: tuple[float, float] = (0.25, 0.6),
        size: tuple[float, float] = (2, 4),
    ) -> None:
        self.x, self.y = x, y
        angle = random.uniform(0, math.tau)
        spd = random.uniform(*speed)
        self.vx = math.cos(angle) * spd
        self.vy = math.sin(angle) * spd
        self.life = random.uniform(*life)
        self.age = 0.0
        self.color = color
        self.size = random.uniform(*size)

    def update(self, dt: float) -> None:
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.93
        self.vy *= 0.93

    @property
    def alive(self) -> bool:
        return self.age < self.life

    def draw(self, surface: pygame.Surface) -> None:
        t = 1 - (self.age / self.life)
        size = max(1, int(self.size * t))
        color = tuple(clamp(int(c * t + 30 * t), 0, 255) for c in self.color)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), size)


class Shockwave:
    def __init__(self, x: float, y: float, color: Color, max_radius: float = 40, life: float = 0.4) -> None:
        self.x, self.y = x, y
        self.color = color
        self.max_radius = max_radius
        self.life = life
        self.age = 0.0

    def update(self, dt: float) -> None:
        self.age += dt

    @property
    def alive(self) -> bool:
        return self.age < self.life

    def draw(self, surface: pygame.Surface) -> None:
        t = self.age / self.life
        radius = int(self.max_radius * t**0.5)
        if radius < 2:
            return
        fade = 1 - t
        blit_glow(surface, self.x, self.y, self.max_radius * 0.8, self.color, strength=fade * 0.8)
        color = tuple(int(c * fade) for c in self.color)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius, max(1, int(4 * fade)))


class FloatText:
    def __init__(self, x: float, y: float, text: str, color: Color, life: float = 1.0) -> None:
        self.x, self.y = x, y
        self.surf = get_font(16, bold=True).render(text, True, color)
        self.life = life
        self.age = 0.0

    def update(self, dt: float) -> None:
        self.age += dt
        self.y -= 40 * dt

    @property
    def alive(self) -> bool:
        return self.age < self.life

    def draw(self, surface: pygame.Surface) -> None:
        self.surf.set_alpha(int(255 * clamp(1 - self.age / self.life, 0, 1)))
        surface.blit(self.surf, self.surf.get_rect(center=(int(self.x), int(self.y))))
