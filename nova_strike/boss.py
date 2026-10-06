"""The mothership boss: missile turrets around a shielded core."""

from __future__ import annotations

import math
import random
from functools import partial
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .config import BOSS_CORE_OFFSET, BOSS_SIZE, BOSS_TURRETS, GREEN, ORANGE, RED, WHITE
from .effects import Particle
from .gfx import blit_glow, circle_hits_rect, clamp, lerp_color, rotated
from .sprites import SPRITES
from .weapons import Bullet

if TYPE_CHECKING:
    from .config import Point
    from .game import Game


class EnemyMissile(Bullet):
    """Boss missile: homes in for a few seconds, then flies straight. It can be shot down."""

    def __init__(
        self, x: float, y: float, angle: float, *, speed: float = 170, damage: float = 20, turn_rate: float = 2.2
    ) -> None:
        super().__init__(x, y, enemy=True, color=(255, 90, 60), radius=5, damage=damage)
        self.angle = angle
        self.speed = speed
        self.turn_rate = turn_rate
        self.age = 0.0
        self.set_velocity()

    def set_velocity(self) -> None:
        self.vx = math.cos(self.angle) * self.speed
        self.vy = math.sin(self.angle) * self.speed

    def steer(self, dt: float, target: Point | None) -> None:
        if target and self.age < 3.0:
            desired = math.atan2(target[1] - self.y, target[0] - self.x)
            diff = (desired - self.angle + math.pi) % math.tau - math.pi
            self.angle += clamp(diff, -self.turn_rate * dt, self.turn_rate * dt)
        self.speed = min(self.speed + 50 * dt, 320)
        self.set_velocity()

    def update(self, dt: float) -> None:
        self.age += dt
        super().update(dt)
        if self.age > 7.0:
            self.alive = False

    def draw(self, surface: pygame.Surface) -> None:
        pt = partial(rotated, self.x, self.y, self.angle)
        blit_glow(surface, *pt(-9, 0), 12, (255, 120, 40))
        pygame.draw.polygon(surface, (70, 70, 80), [pt(-8, -5), pt(-4, 0), pt(-8, 5)])
        pygame.draw.polygon(surface, (90, 30, 35), [pt(9, 0), pt(4, -3), pt(-8, -3), pt(-8, 3), pt(4, 3)])
        pygame.draw.polygon(surface, (255, 70, 60), [pt(9, 0), pt(4, -3), pt(4, 3)])
        pygame.draw.line(surface, (255, 200, 120), pt(-8, 0), pt(-11 - random.uniform(0, 4), 0), 2)


class BossPart:
    """A damageable point on the boss (a turret or the core)."""

    def __init__(self, ox: float, oy: float, radius: float, health: float) -> None:
        self.ox, self.oy = ox, oy
        self.x = self.y = 0.0
        self.radius = radius
        self.health: float = health
        self.max_health = health
        self.flash = 0.0
        self.alive = True

    def hit(self, dmg: float) -> bool:
        self.health -= dmg
        self.flash = 0.06
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return True
        return False

    def hits_rect(self, rect: pygame.Rect, extra: float = 0) -> bool:
        return circle_hits_rect(self.x, self.y, self.radius + extra, rect)


class BossTurret(BossPart):
    def __init__(self, ox: float, oy: float, health: float, first_shot: float) -> None:
        super().__init__(ox, oy, 15, health)
        self.angle = math.pi / 2
        self.cooldown = first_shot
        self.recoil = 0.0


class Boss:
    name = "MOTHERSHIP"
    STOP_Y = 175

    def __init__(self, number: int) -> None:
        self.number = number  # 0 for the first boss; each return is tougher
        self.x = cfg.WIDTH / 2
        self.y = -BOSS_SIZE[1] / 2 - 10
        self.state = "entering"  # entering -> fighting -> dying
        self.age = 0.0
        self.fight_t = 0.0
        turret_hp = 30 + number * 15
        self.turrets = [BossTurret(ox, oy, turret_hp, 1.0 + i * 0.7) for i, (ox, oy) in enumerate(BOSS_TURRETS)]
        self.core = BossPart(0, BOSS_CORE_OFFSET, 22, 150 + number * 60)
        self.max_total = sum(t.max_health for t in self.turrets) + self.core.max_health
        self.core_cooldown = 1.5
        self.dying_time = 0.0
        self.boom_timer = 0.0
        self.alive = True
        self.place_parts()

    @property
    def shielded(self) -> bool:
        return any(t.alive for t in self.turrets)

    @property
    def total_health(self) -> float:
        return sum(t.health for t in self.turrets) + self.core.health

    def targets(self) -> list[BossPart]:
        """Live parts that player missiles may home in on."""
        if self.state == "dying":
            return []
        return [t for t in self.turrets if t.alive] or ([self.core] if self.core.alive else [])

    def hull_rects(self) -> list[pygame.Rect]:
        x, y = int(self.x), int(self.y)
        return [
            pygame.Rect(x - 155, y - 50, 310, 70),
            pygame.Rect(x - 45, y + 20, 90, 50),
            pygame.Rect(x - 70, y - 75, 140, 25),
        ]

    def place_parts(self) -> None:
        for part in [*self.turrets, self.core]:
            part.x, part.y = self.x + part.ox, self.y + part.oy

    def update(self, dt: float, game: Game) -> None:
        self.age += dt
        for part in [*self.turrets, self.core]:
            part.flash = max(0.0, part.flash - dt)

        if self.state == "entering":
            self.y += 70 * dt
            if self.y >= self.STOP_Y:
                self.y = self.STOP_Y
                self.state = "fighting"
        elif self.state == "fighting":
            self.fight_t += dt
            pace = 1.7 if not self.shielded else 1.0
            amp = max(0.0, cfg.WIDTH / 2 - 170)
            self.x = cfg.WIDTH / 2 + math.sin(self.fight_t * 0.45 * pace) * amp
            self.y = self.STOP_Y + math.sin(self.fight_t * 0.9) * 14
        else:
            self.dying_time += dt
            self.y += 18 * dt
            self.boom_timer -= dt
            if self.boom_timer <= 0:
                self.boom_timer = 0.12
                bx = self.x + random.uniform(-140, 140)
                by = self.y + random.uniform(-45, 45)
                game.explode(bx, by, random.choice((ORANGE, (255, 80, 60), (255, 220, 120))), 1.3)
                game.sfx.play("explosion", min_gap=0.1)
            if self.dying_time > 2.6:
                self.alive = False
        self.place_parts()

        for t in self.turrets:
            if not t.alive:
                if random.random() < 0.25:
                    game.particles.append(
                        Particle(t.x, t.y, (85, 85, 95), speed=(10, 40), life=(0.4, 0.9), size=(2, 4))
                    )
                continue
            t.recoil = max(0.0, t.recoil - dt)
            if self.state != "fighting":
                continue
            p = game.player
            desired = math.atan2(p.y - t.y, p.x - t.x) if p.alive else math.pi / 2
            diff = (desired - t.angle + math.pi) % math.tau - math.pi
            t.angle += clamp(diff, -2.5 * dt, 2.5 * dt)
            t.cooldown -= dt
            if t.cooldown <= 0 and p.alive:
                t.cooldown = random.uniform(2.4, 3.4) * max(0.6, 1 - 0.1 * self.number)
                mx, my = t.x + math.cos(t.angle) * 20, t.y + math.sin(t.angle) * 20
                game.enemy_bullets.append(EnemyMissile(mx, my, t.angle, speed=160 + self.number * 20))
                t.recoil = 0.15
                game.sfx.play("boss_missile", min_gap=0.15)

        if self.state == "fighting" and not self.shielded:
            self.core_cooldown -= dt
            if self.core_cooldown <= 0:
                self.core_cooldown = max(0.9, 1.5 - 0.15 * self.number)
                offset = random.uniform(-7, 7)
                for deg in range(-60, 61, 15):
                    a = math.radians(90 + deg + offset)
                    game.enemy_bullets.append(
                        Bullet(
                            self.core.x,
                            self.core.y + 20,
                            vx=math.cos(a) * 210,
                            vy=math.sin(a) * 210,
                            enemy=True,
                            color=(255, 80, 120),
                            radius=5,
                            damage=14,
                        )
                    )
                game.sfx.play("enemy_shot")

    def draw(self, surface: pygame.Surface, t: float) -> None:
        x, y = int(self.x), int(self.y)
        for ex in (-35, 0, 35):
            blit_glow(surface, x + ex, y - BOSS_SIZE[1] / 2 + 3, 18, ORANGE, strength=0.6 + 0.3 * math.sin(t * 9 + ex))
        sprite = SPRITES["boss"]
        surface.blit(sprite, sprite.get_rect(center=(x, y)))

        core = self.core
        cx, cy = int(core.x), int(core.y)
        if core.alive:
            pulse = 0.5 + 0.5 * math.sin(t * (10 if not self.shielded else 4))
            blit_glow(surface, cx, cy, 34, (255, 80, 40), strength=0.5 + 0.4 * pulse)
            pygame.draw.circle(surface, (255, 110, 60), (cx, cy), 13)
            pygame.draw.circle(surface, (255, 230, 200), (cx, cy), 6)
            if core.flash > 0:
                pygame.draw.circle(surface, WHITE, (cx, cy), 16)
            if self.shielded:
                blit_glow(surface, cx, cy, 40, (40, 120, 255), strength=0.35)
                pygame.draw.circle(surface, (120, 200, 255), (cx, cy), 30, 2)
                for i in range(6):
                    a = t * 1.5 + i * math.tau / 6
                    pygame.draw.circle(
                        surface, (180, 230, 255), (int(cx + math.cos(a) * 30), int(cy + math.sin(a) * 30)), 2
                    )

        for tur in self.turrets:
            tx, ty = int(tur.x), int(tur.y)
            if not tur.alive:
                pygame.draw.circle(surface, (25, 20, 20), (tx, ty), 13)
                blit_glow(surface, tx, ty, 10, ORANGE, strength=0.4 + 0.3 * random.random())
                continue
            length = 24 - tur.recoil * 40
            at = partial(rotated, tur.x, tur.y, tur.angle)
            pod = [at(-4, -6), at(length, -6), at(length, 6), at(-4, 6)]
            pygame.draw.polygon(surface, (140, 40, 48), pod)
            pygame.draw.polygon(surface, (30, 15, 18), pod, 1)
            for side in (-3, 3):
                pygame.draw.circle(surface, (25, 25, 30), [int(v) for v in at(length - 1, side)], 2)
            pygame.draw.circle(surface, (150, 155, 170), (tx, ty), 9)
            pygame.draw.circle(surface, (60, 64, 78), (tx, ty), 9, 2)
            pygame.draw.circle(surface, (255, 70, 60), (tx, ty), 3)
            if tur.flash > 0:
                pygame.draw.circle(surface, WHITE, (tx, ty), 14)
            if tur.health < tur.max_health:
                ratio = tur.health / tur.max_health
                pygame.draw.rect(surface, (40, 40, 50), (tx - 16, ty - 26, 32, 4))
                pygame.draw.rect(surface, lerp_color(RED, GREEN, ratio), (tx - 16, ty - 26, int(32 * ratio), 4))
