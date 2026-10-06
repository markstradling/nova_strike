"""Regular enemy ships and how they are chosen to spawn."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .ai import Plan
from .config import BASE_WIDTH, ENEMY_TYPES, GREEN, HEIGHT, MAGENTA, ORANGE, RED, YELLOW
from .gfx import blit_glow, clamp, lerp_color
from .sprites import SPRITES
from .weapons import Bullet

if TYPE_CHECKING:
    from .config import Point


def max_heavies(level: int) -> int:
    return 0 if level < 3 else min(3, 1 + (level - 3) // 4)


def pick_enemy_kind(level: int, enemies: Sequence[Enemy]) -> str:
    # Heavies are slow and tough, so too many at once pile up into a wall that soaks every shot.
    # Their share levels off, and only a few may be on screen together.
    weights = {"scout": 5, "fighter": min(10, 2 + level), "heavy": min(3.0, max(0, level - 2) * 0.8)}
    if sum(1 for e in enemies if e.kind == "heavy") >= max_heavies(level) * max(1, round(cfg.WIDTH / BASE_WIDTH)):
        weights["heavy"] = 0
    kinds = list(weights)
    return random.choices(kinds, weights=[weights[k] for k in kinds])[0]


class Enemy:
    def __init__(self, kind: str, level: int) -> None:
        spec = ENEMY_TYPES[kind]
        self.kind = kind
        self.w, self.h = spec["size"]
        self.x = random.uniform(self.w / 2 + 6, cfg.WIDTH - self.w / 2 - 6)
        self.y: float = -self.h
        self.speed = random.uniform(*spec["speed"]) + level * 4
        self.health: float = spec["hp"] + level // (6 if kind == "heavy" else 4)
        self.max_health = self.health
        self.fire_range = spec["fire"]
        self.fire_cooldown = random.uniform(*self.fire_range) * 0.6
        self.sway = spec["sway"] * random.choice((-1, 1))
        self.freq = spec["freq"]
        self.phase = random.uniform(0, math.tau)
        self.score_value = spec["score"]
        self.shot_damage = spec["shot_damage"]
        self.ram_damage = spec["ram_damage"]
        self.agility = spec["agility"]
        self.flash = 0.0
        self.invuln = 0.0  # brief protection after crashing into an obstacle, as for the player
        self.alive = True

    def hitbox(self) -> pygame.Rect:
        w, h = self.w * 0.8, self.h * 0.8
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), int(w), int(h))

    def update(self, dt: float, t: float, plan: Plan | None = None) -> None:
        """Fly down, weaving from side to side, unless `plan` says to steer around an obstacle."""
        if plan is None:
            plan = Plan()
        self.y += self.speed * plan.speed_scale * dt
        if plan.target_x is None:
            self.x += math.cos(t * self.freq + self.phase) * self.sway * dt
        else:
            step = self.agility * dt
            self.x += clamp(plan.target_x - self.x, -step, step)
        self.x = clamp(self.x, self.w / 2, cfg.WIDTH - self.w / 2)
        self.fire_cooldown -= dt
        self.flash = max(0.0, self.flash - dt)
        self.invuln = max(0.0, self.invuln - dt)
        if self.y > HEIGHT + self.h:
            self.alive = False

    def try_fire(self, target: Point | None) -> list[Bullet]:
        if self.fire_cooldown > 0 or self.y < 10:
            return []
        self.fire_cooldown = random.uniform(*self.fire_range)
        muzzle_y = self.y + self.h / 2
        if self.kind == "scout":
            return [
                Bullet(self.x, muzzle_y, vy=340, enemy=True, color=(255, 200, 80), radius=3, damage=self.shot_damage)
            ]
        if self.kind == "fighter":
            tx, ty = target if target else (self.x, HEIGHT)
            angle = math.atan2(ty - muzzle_y, tx - self.x)
            return [
                Bullet(
                    self.x + ox,
                    muzzle_y - 6,
                    vx=math.cos(angle) * 260,
                    vy=math.sin(angle) * 260,
                    enemy=True,
                    color=(255, 110, 60),
                    radius=4,
                    damage=self.shot_damage,
                )
                for ox in (-15, 15)
            ]
        shots = []
        for deg in (-30, -15, 0, 15, 30):
            a = math.radians(90 + deg)
            shots.append(
                Bullet(
                    self.x,
                    muzzle_y,
                    vx=math.cos(a) * 210,
                    vy=math.sin(a) * 210,
                    enemy=True,
                    color=MAGENTA,
                    radius=5,
                    damage=self.shot_damage,
                )
            )
        return shots

    def hit(self, dmg: float) -> bool:
        self.health -= dmg
        self.flash = 0.08
        if self.health <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface: pygame.Surface, t: float) -> None:
        x, y = int(self.x), int(self.y)
        if self.kind == "heavy":
            for ex in (-18, 18):
                blit_glow(surface, x + ex, y - self.h / 2 + 2, 10, ORANGE, strength=0.8)
        else:
            blit_glow(surface, x, y - self.h / 2 + 2, 8, (255, 90, 120), strength=0.7)

        sprite = SPRITES[self.kind + "_flash"] if self.flash > 0 else SPRITES[self.kind]
        surface.blit(sprite, sprite.get_rect(center=(x, y)))

        if self.kind == "heavy":
            blit_glow(surface, x, y - 2, 14, (255, 90, 40), strength=0.6 + 0.4 * math.sin(t * 6 + self.phase))
        elif self.kind == "scout":
            blit_glow(surface, x, y + 2, 6, YELLOW, strength=0.7)

        if self.max_health > 1 and self.health < self.max_health:
            ratio = self.health / self.max_health
            bar_y = y - self.h / 2 - 7
            pygame.draw.rect(surface, (40, 40, 50), (x - self.w / 2, bar_y, self.w, 3))
            pygame.draw.rect(surface, lerp_color(RED, GREEN, ratio), (x - self.w / 2, bar_y, self.w * ratio, 3))
