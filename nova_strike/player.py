"""The player's ship: movement, weapon inventory and firing."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .config import (
    AMMO_CAP,
    HEIGHT,
    HIT_INVULN,
    MAX_WEAPON,
    ORANGE,
    PLAYER_MAX_HEALTH,
    PLAYER_SIZE,
    TRAY_H,
    WEAPON_AMMO,
    WEAPON_ORDER,
    WEAPONS,
)
from .gfx import blit_glow, clamp
from .sprites import SPRITES
from .weapons import Bullet, Missile

if TYPE_CHECKING:
    from .config import KeyState, WeaponSlot


class Player:
    def __init__(self) -> None:
        self.w, self.h = PLAYER_SIZE
        self.speed = 320
        self.max_health = PLAYER_MAX_HEALTH
        # Weapons you are carrying. The blaster never runs out (ammo None).
        self.arsenal: dict[str, WeaponSlot] = {"blaster": {"level": 1, "ammo": None}}
        self.selected = "blaster"
        self.emptied: str | None = None  # set to a weapon's kind on the frame it runs dry
        self.bank = 0.0
        self.thrust = 0.0
        self.respawn()

    def respawn(self) -> None:
        self.x = cfg.WIDTH / 2
        self.y: float = HEIGHT - TRAY_H - 36
        self.health: float = self.max_health
        self.cooldown = 0.0
        self.missile_cooldown = 0.0
        self.invuln = 2.5  # brief blink after respawning or taking a hit
        self.invincible = 0.0  # timed power-up
        self.alive = True

    @property
    def protected(self) -> bool:
        return self.invuln > 0 or self.invincible > 0

    def hitbox(self) -> pygame.Rect:
        """Body box used for crashing into walls, asteroids and enemy ships."""
        w, h = self.w * 0.6, self.h * 0.75
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), int(w), int(h))

    def core(self) -> pygame.Rect:
        """Smaller box around the cockpit used for bullets, so near misses feel fair."""
        return pygame.Rect(int(self.x - 6), int(self.y - 12), 12, 22)

    def update(self, dt: float, keys: KeyState) -> None:
        dx = dy = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += 1
        if dx or dy:
            length = math.hypot(dx, dy)
            dx, dy = dx / length, dy / length

        self.x = clamp(self.x + dx * self.speed * dt, self.w / 2, cfg.WIDTH - self.w / 2)
        self.y = clamp(self.y + dy * self.speed * dt, self.h / 2, HEIGHT - TRAY_H - self.h / 2)

        ease = min(1.0, dt * 10)
        self.bank += (dx - self.bank) * ease
        self.thrust += ((1.0 if dy < 0 else 0.5 if dy > 0 else 0.75) - self.thrust) * ease
        self.cooldown = max(0.0, self.cooldown - dt)
        self.missile_cooldown = max(0.0, self.missile_cooldown - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.invincible = max(0.0, self.invincible - dt)

    @property
    def weapon_type(self) -> str:
        return self.selected

    @property
    def weapon_level(self) -> int:
        return self.arsenal[self.selected]["level"]

    def collect_weapon(self, kind: str) -> None:
        """A new weapon is added and selected; one you already carry gets a level and more ammo.
        Nukes just stack (up to AMMO_CAP) and are never auto-selected, so one can't be fired by accident."""
        if kind == "nuke":
            w = self.arsenal.setdefault("nuke", {"level": 1, "ammo": 0})
            w["ammo"] = min(WEAPON_AMMO["nuke"] * AMMO_CAP, (w["ammo"] or 0) + 1)
            return
        if kind in self.arsenal:
            w = self.arsenal[kind]
            w["level"] = min(MAX_WEAPON, w["level"] + 1)
            if w["ammo"] is not None:
                w["ammo"] = min(WEAPON_AMMO[kind] * AMMO_CAP, w["ammo"] + WEAPON_AMMO[kind])
        else:
            self.arsenal[kind] = {"level": 1, "ammo": WEAPON_AMMO[kind]}
            self.selected = kind

    def select(self, kind: str) -> None:
        if kind in self.arsenal:
            self.selected = kind

    def cycle(self, step: int) -> None:
        owned = [k for k in WEAPON_ORDER if k in self.arsenal]
        self.selected = owned[(owned.index(self.selected) + step) % len(owned)]

    def use_ammo(self, amount: float) -> None:
        w = self.arsenal[self.selected]
        if w["ammo"] is None:
            return
        w["ammo"] -= amount
        if w["ammo"] <= 0:
            del self.arsenal[self.selected]
            self.emptied = self.selected
            self.selected = "blaster"

    def blaster_shots(self, level: int) -> list[Bullet]:
        top = self.y - self.h / 2 + 6
        shots = [Bullet(self.x - 8, top), Bullet(self.x + 8, top)]
        if level >= 2:
            shots += [
                Bullet(self.x - 19, self.y, vx=-140, vy=-620, color=(120, 255, 200)),
                Bullet(self.x + 19, self.y, vx=140, vy=-620, color=(120, 255, 200)),
            ]
        if level >= 3:
            shots += [
                Bullet(self.x, top - 4, vy=-720, color=(255, 230, 120), damage=2),
                Bullet(self.x - 19, self.y, vx=-280, vy=-580, color=(120, 255, 200)),
                Bullet(self.x + 19, self.y, vx=280, vy=-580, color=(120, 255, 200)),
            ]
        return shots

    def fire(self) -> list[Bullet]:
        """Called every frame fire is held; returns new projectiles. The laser is handled by Game."""
        kind, level = self.weapon_type, self.weapon_level
        shots = []
        if kind == "blaster" and self.cooldown <= 0:
            self.cooldown = 0.15
            shots += self.blaster_shots(level)
        elif kind == "spread" and self.cooldown <= 0:
            self.cooldown = 0.2
            n = 1 + 2 * level
            self.use_ammo(1)
            for i in range(n):
                a = math.radians(-90 + (i - (n - 1) / 2) * 11)
                shots.append(
                    Bullet(
                        self.x,
                        self.y - self.h / 2 + 6,
                        vx=math.cos(a) * 600,
                        vy=math.sin(a) * 600,
                        color=WEAPONS["spread"]["color"],
                    )
                )
        elif kind == "missile":
            if level >= 2 and self.cooldown <= 0:
                self.cooldown = 0.15
                shots += self.blaster_shots(1)
            if self.missile_cooldown <= 0:
                self.missile_cooldown = 0.45
                angles = (50, 25) if level >= 3 else (45,)
                self.use_ammo(2 * len(angles))
                for side in (-1, 1):
                    for spread in angles:
                        shots.append(Missile(self.x + side * 16, self.y, math.radians(-90 + side * spread)))
        return shots

    def hit(self, amount: float) -> bool:
        if self.protected:
            return False
        self.health = max(0, self.health - amount)
        self.invuln = HIT_INVULN
        return True

    def draw(self, surface: pygame.Surface) -> None:
        if self.invuln > 0 and self.invincible <= 0 and int(self.invuln * 20) % 2 == 0:
            return
        x, y = self.x, self.y
        t = pygame.time.get_ticks() / 1000

        if self.invincible > 0 and (self.invincible > 1.5 or int(t * 10) % 2 == 0):
            aura = pygame.Color(0)
            aura.hsva = ((t * 240) % 360, 70, 100, 100)
            blit_glow(surface, x, y, 46, (aura.r, aura.g, aura.b), strength=0.55)
            pygame.draw.circle(surface, (aura.r, aura.g, aura.b), (int(x), int(y)), 30, 2)

        for ex in (-5, 5):
            fx, fy = x + ex, y + self.h / 2 - 2
            flen = random.uniform(9, 16) * (0.6 + self.thrust)
            blit_glow(surface, fx, fy + 4, 12, ORANGE)
            pygame.draw.polygon(surface, (255, 150, 50), [(fx - 3, fy), (fx + 3, fy), (fx, fy + flen)])
            pygame.draw.polygon(surface, (255, 250, 210), [(fx - 1.5, fy), (fx + 1.5, fy), (fx, fy + flen * 0.55)])

        sprite = SPRITES["player"]
        squash = 1 - 0.18 * abs(self.bank)
        if squash < 0.99:
            sprite = pygame.transform.smoothscale(sprite, (max(1, int(self.w * squash)), self.h))
        surface.blit(sprite, sprite.get_rect(center=(int(x), int(y))))
        blit_glow(surface, x - 19, y + 4, 6, (60, 160, 255), strength=0.6)
        blit_glow(surface, x + 19, y + 4, 6, (60, 160, 255), strength=0.6)
