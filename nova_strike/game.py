"""The game: state machine, spawning, collisions, rendering and input."""

from __future__ import annotations

import asyncio
import math
import random
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from . import config as cfg
from .ai import plan_route
from .boss import Boss, EnemyMissile
from .config import (
    AMMO_CAP,
    ASTEROID_RADII,
    BASE_WIDTH,
    BOSS_LEVEL,
    CYAN,
    DEFAULT_LIVES,
    ENEMY_TYPES,
    EXTRA_LIFE_EVERY,
    FPS,
    GRAY,
    GREEN,
    HEIGHT,
    HIT_INVULN,
    INVINCIBLE_TIME,
    IS_MAC,
    IS_WEB,
    MAX_LIVES,
    MAX_SLOWMO,
    MAX_WEAPON,
    MAX_WIDTH,
    NAME_CHARS,
    NEXT_WEAPON_KEYS,
    ORANGE,
    PICKUPS,
    PLAYER_MAX_HEALTH,
    POINTS_PER_LEVEL,
    PREV_WEAPON_KEYS,
    RED,
    SCOREBOARD_SIZE,
    SLOWMO_FACTOR,
    SLOWMO_KEYS,
    SLOWMO_TIME,
    TITLE_PAGE_TIME,
    TRAY_H,
    WALL_DAMAGE,
    WEAPON_AMMO,
    WEAPON_ORDER,
    WEAPONS,
    WHITE,
    YELLOW,
)
from .effects import FloatText, Particle, Shockwave, Star
from .enemies import Enemy, pick_enemy_kind
from .gfx import blit_glow, clamp, get_font, lerp_color
from .obstacles import Asteroid, LaserGate, Mine, SlidingWall, Spinner, Wall
from .player import Player
from .scores import RANK_COLORS, load_scores, ordinal, qualifies, save_scores
from .sound import SoundFX
from .sprites import SPRITES, build_nebula, load_sprites
from .weapons import Missile, PowerUp, random_pickup_kind

if TYPE_CHECKING:
    from .boss import BossPart
    from .config import Color, HasY, KeyState, Point
    from .obstacles import Hazard
    from .weapons import Bullet


try:
    from pygame._sdl2.video import Window as SDLWindow
except ImportError:  # very old pygame: fall back to set_mode for fullscreen
    SDLWindow = None  # type: ignore[assignment,misc]


@dataclass
class Banner:
    title: str
    subtitle: str
    time: float
    duration: float
    color: Color


class Game:
    def __init__(
        self,
        lives: int = DEFAULT_LIVES,
        *,
        sound: bool = True,
        start_level: int = 1,
        boss_level: int = BOSS_LEVEL,
        scores_file: str | None = None,
    ) -> None:
        self.scores_file = scores_file or cfg.SCORES_FILE
        self.start_level = max(1, start_level)
        self.boss_level = max(1, boss_level)
        # starting part-way in or with a custom boss level is for testing: scores aren't recorded
        self.practice = self.start_level != 1 or self.boss_level != BOSS_LEVEL
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.sfx = SoundFX(enabled=sound)
        pygame.display.set_caption("Nova Strike")
        self.fullscreen = False
        self.screen = pygame.display.set_mode((BASE_WIDTH, HEIGHT), pygame.RESIZABLE)
        self.canvas = pygame.Surface((cfg.WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_title = get_font(52, bold=True)
        self.font_big = get_font(40, bold=True)
        self.font = get_font(20)
        self.font_small = get_font(14)
        load_sprites()
        self.nebula = build_nebula()
        self.nebula_y = 0.0
        self.stars = [Star() for _ in range(110)]
        self.start_lives = clamp(lives, 1, MAX_LIVES)
        self.scores = load_scores(self.scores_file)
        self.last_initials = "AAA"
        self.name: list[str] = []  # initials being entered on the high score screen
        self.name_pos = 0
        self.title_pickups: list[PowerUp] | None = None  # built lazily, rebuilt when the width changes
        self.slowmo_tint = pygame.Surface((cfg.WIDTH, HEIGHT), pygame.SRCALPHA)
        self.slowmo_tint.fill((70, 40, 160, 75))
        self.t = 0.0
        self.world_t = 0.0
        self.state_time = 0.0
        self.title_started = 0.0
        self.reset()
        self.state = "title"  # title, playing, paused, enter_name, game_over

    @property
    def high_score(self) -> int:
        return self.scores[0][1] if self.scores else 0

    def reset(self) -> None:
        self.player = Player()
        self.slowmo_charges = 1  # start with one so the ability can be tried straight away
        self.nuke_flash = 0.0
        self.slowmo_time = 0.0
        self.slowmo_active = False
        self.new_rank: int | None = None
        self.boss: Boss | None = None
        self.boss_warning = 0.0
        self.boss_count = 0
        # first multiple of boss_level at or after the starting level
        self.next_boss_level = math.ceil(self.start_level / self.boss_level) * self.boss_level
        self.lives = self.start_lives
        self.bullets: list[Bullet] = []
        self.enemy_bullets: list[Bullet] = []
        self.enemies: list[Enemy] = []
        self.particles: list[Particle] = []
        self.effects: list[Shockwave | FloatText] = []
        self.powerups: list[PowerUp] = []
        self.walls: list[Wall] = []
        self.asteroids: list[Asteroid] = []
        self.hazards: list[Hazard] = []
        self.seen_barriers: set[str] = set()
        self.score = 0
        self.next_extend = EXTRA_LIFE_EVERY
        self.spawn_timer = 1.0
        self.barrier_timer = 4.0
        self.rock_timer = 2.5
        self.pickup_timer = random.uniform(5, 8)
        self.laser: tuple[float, float, float, float] | None = None  # (x, stop_y, top_y, half_width)
        self.level = self.start_level
        self.level_discount = 0  # points that don't count towards levelling up (boss fight rewards)
        self.respawn_timer = 0.0
        self.shake = 0.0
        self.banner: Banner | None = None
        self.show_banner(f"LEVEL {self.level}", "Watch for debris!")
        self.state = "playing"

    def show_banner(self, title: str, subtitle: str = "", duration: float = 2.0, color: Color = CYAN) -> None:
        self.banner = Banner(title, subtitle, duration, duration, color)

    # -- effects -----------------------------------------------------------

    def spawn_sparks(self, x: float, y: float, color: Color, count: int = 5) -> None:
        for _ in range(count):
            self.particles.append(Particle(x, y, color, speed=(60, 200), life=(0.1, 0.3), size=(1, 2.5)))

    def explode(self, x: float, y: float, color: Color, size: float = 1.0) -> None:
        for _ in range(int(16 * size)):
            self.particles.append(Particle(x, y, color, speed=(40, 260 * size), size=(2, 3 + size)))
        for _ in range(int(10 * size)):
            self.particles.append(Particle(x, y, (255, 230, 160), speed=(20, 120 * size), life=(0.15, 0.35)))
        self.effects.append(Shockwave(x, y, color, max_radius=int(30 * size + 10), life=0.3 + 0.15 * size))
        self.shake = max(self.shake, 0.08 * size)

    # -- update ------------------------------------------------------------

    def update(self, dt: float, keys: KeyState) -> None:
        # Slow motion: the world runs on wdt while the player's ship, shots and timers keep real time.
        self.slowmo_time = max(0.0, self.slowmo_time - dt) if self.state == "playing" else self.slowmo_time
        if self.slowmo_active and self.slowmo_time <= 0:
            self.slowmo_active = False
            self.sfx.play("slowmo_off")
        wdt = dt * SLOWMO_FACTOR if self.slowmo_active else dt

        self.t += dt
        self.world_t += wdt
        self.state_time += dt
        self.nebula_y = (self.nebula_y + 12 * wdt) % HEIGHT
        for star in self.stars:
            star.update(wdt)
        self.shake = max(0.0, self.shake - dt)
        self.nuke_flash = max(0.0, self.nuke_flash - dt * 1.1)

        if self.state in ("title", "paused", "enter_name"):
            return

        for p in self.particles:
            p.update(wdt)
        for fx in self.effects:
            fx.update(dt if isinstance(fx, FloatText) else wdt)
        self.particles = [p for p in self.particles if p.alive]
        self.effects = [fx for fx in self.effects if fx.alive]

        if self.state != "playing":
            return

        if self.banner:
            self.banner.time -= dt
            if self.banner.time <= 0:
                self.banner = None

        boss_time = self.boss is not None or self.boss_warning > 0
        new_level = self.start_level + (self.score - self.level_discount) // POINTS_PER_LEVEL
        if new_level > self.level and not boss_time:
            self.level = new_level
            self.show_banner(f"LEVEL {self.level}", "Scroll speed increasing")
            self.sfx.play("level_up")

        if self.boss is None:
            if self.boss_warning > 0:
                self.boss_warning -= dt
                if self.boss_warning <= 0:
                    self.boss = Boss(self.boss_count)
                    self.show_banner("DESTROY THE TURRETS", "Its core is shielded until they fall", color=ORANGE)
            elif self.level >= self.next_boss_level:
                self.boss_warning = 3.0
                self.show_banner("WARNING", "Mothership approaching!", duration=3.0, color=RED)
                self.sfx.play("boss_alarm")

        self.laser = None
        if self.player.alive:
            self.player.update(dt, keys)
            if keys[pygame.K_SPACE]:
                if self.player.weapon_type == "laser":
                    self.update_laser(dt)
                else:
                    shots = self.player.fire()
                    if any(isinstance(b, Missile) for b in shots):
                        self.sfx.play("missile")
                    if any(not isinstance(b, Missile) for b in shots):
                        self.sfx.play("spread" if self.player.weapon_type == "spread" else "shoot")
                    self.bullets.extend(shots)
            if self.player.emptied:
                self.sfx.play("empty")
                name = WEAPONS[self.player.emptied]["name"]
                self.effects.append(FloatText(self.player.x, self.player.y - 40, f"{name} EMPTY", RED))
                self.player.emptied = None
        else:
            self.respawn_timer -= dt
            if self.respawn_timer <= 0:
                if self.lives > 0:
                    self.player.respawn()
                    self.enemy_bullets.clear()
                else:
                    self.end_game()

        self.spawn_timer -= wdt
        if self.spawn_timer <= 0 and not boss_time:
            self.spawn_timer = max(0.35, 1.15 - self.level * 0.06) * random.uniform(0.8, 1.2) / self.width_factor
            self.enemies.append(Enemy(pick_enemy_kind(self.level, self.enemies), self.level))
        self.spawn_obstacles(wdt, barriers=not boss_time)

        target = (self.player.x, self.player.y) if self.player.alive else None
        for b in self.bullets:
            if isinstance(b, Missile):
                b.steer(dt, [*self.enemies, *(self.boss.targets() if self.boss else [])])
                if random.random() < 0.6:
                    self.particles.append(
                        Particle(b.x, b.y, (110, 110, 125), speed=(0, 20), life=(0.2, 0.4), size=(1.5, 3))
                    )
            b.update(dt)
        for b in self.enemy_bullets:
            if isinstance(b, EnemyMissile):
                b.steer(wdt, target)
                if random.random() < 0.5:
                    self.particles.append(
                        Particle(b.x, b.y, (120, 100, 100), speed=(0, 20), life=(0.2, 0.5), size=(1.5, 3))
                    )
            b.update(wdt)
        if self.boss:
            self.boss.update(wdt, self)
            if not self.boss.alive:
                self.boss_destroyed(self.boss)
        for e in self.enemies:
            e.update(wdt, self.world_t, plan_route(e, self.walls, self.hazards, self.asteroids))
            shots = e.try_fire(target)
            if shots:
                self.sfx.play("enemy_shot", min_gap=0.08)
                self.enemy_bullets.extend(shots)
        for pickup in self.powerups:
            pickup.update(wdt)
        for w in self.walls:
            w.update(wdt)
        for a in self.asteroids:
            a.update(wdt)
        for h in self.hazards:
            h.update(wdt, self)

        self.handle_collisions()

        self.bullets = [b for b in self.bullets if b.alive]
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]
        self.enemies = [e for e in self.enemies if e.alive]
        self.powerups = [p for p in self.powerups if p.alive]
        self.walls = [w for w in self.walls if w.alive]
        self.asteroids = [a for a in self.asteroids if a.alive]
        self.hazards = [h for h in self.hazards if h.alive]

        if self.score >= self.next_extend:
            self.next_extend += EXTRA_LIFE_EVERY
            if self.lives < MAX_LIVES:
                self.lives += 1
                self.show_banner("EXTRA LIFE!", f"{self.lives} ships remaining", color=GREEN)
                self.sfx.play("extra_life")

    @property
    def scroll_speed(self) -> float:
        return 110 + self.level * 8

    def update_laser(self, dt: float) -> None:
        p = self.player
        half = (3, 5, 8)[p.weapon_level - 1]
        dps = (14, 20, 30)[p.weapon_level - 1]
        top = p.y - p.h / 2 + 4
        column = pygame.Rect(int(p.x - half), 0, half * 2, max(1, int(top)))

        # The beam pierces enemies but stops at the first barrier above the ship.
        stop = 0.0
        blocker: Asteroid | Mine | None = None
        for w in self.walls:
            for r in w.rects():
                if r.colliderect(column) and r.bottom <= top and r.bottom > stop:
                    stop, blocker = r.bottom, None
        for a in self.asteroids:
            if a.alive and a.y < top and abs(a.x - p.x) < a.radius * 0.85 + half:
                end = a.y + a.radius * 0.6
                if end > stop:
                    stop, blocker = end, a
        for h in self.hazards:
            hazard_end = h.laser_stop(p.x, half, top) if h.alive else None
            if hazard_end is not None and hazard_end > stop:
                stop, blocker = hazard_end, (h if isinstance(h, Mine) else None)

        boss_hit: BossPart | None = None
        boss = self.boss
        if boss and boss.state != "dying":
            # the beam passes over the hull and stops at the lowest turret or core in its path
            for part in [*boss.turrets, boss.core]:
                if part.alive and part.y < top and abs(part.x - p.x) < part.radius + half:
                    end = part.y + part.radius * 0.6
                    if end > stop:
                        stop, blocker, boss_hit = end, None, part

        beam = pygame.Rect(int(p.x - half), int(stop), half * 2, max(1, int(top - stop)))
        for m in self.enemy_bullets:
            if isinstance(m, EnemyMissile) and m.alive and beam.colliderect(m.rect()):
                self.shoot_down_missile(m)
        if boss is not None and boss_hit is not None:
            if boss_hit is not boss.core:
                if boss_hit.hit(dps * dt):
                    self.destroy_turret(boss, boss_hit)
            elif boss.shielded:
                if random.random() < 0.3:
                    self.spawn_sparks(p.x, stop, (120, 200, 255), 2)
            elif boss_hit.hit(dps * dt):
                self.kill_boss(boss)
        for e in self.enemies:
            if e.alive and beam.colliderect(e.hitbox()):
                if e.hit(dps * dt):
                    self.destroy_enemy(e)
                elif random.random() < 0.3:
                    self.spawn_sparks(e.x, e.y + e.h / 3, WEAPONS["laser"]["color"], 2)
        if isinstance(blocker, Mine):
            if blocker.hit(dps * dt):
                self.detonate(blocker)
        elif blocker and blocker.hit(dps * dt):
            self.destroy_asteroid(blocker)
        if stop > 0 and random.random() < 0.5:
            self.spawn_sparks(p.x, stop, (255, 200, 240), 2)
        self.laser = (p.x, stop, top, half)
        p.use_ammo(dt)

    def draw_laser(self, surface: pygame.Surface) -> None:
        if not self.laser:
            return
        x, stop, top, half = self.laser
        length = int(top - stop)
        if length <= 0:
            return
        half = half * random.uniform(0.85, 1.1)
        color = WEAPONS["laser"]["color"]
        beam = pygame.Surface((int(half * 6) + 2, length))
        cx = beam.get_width() / 2
        for width, c in (
            (half * 3, tuple(v // 4 for v in color)),
            (half * 2, tuple(v // 2 for v in color)),
            (half, color),
            (max(1, half / 2.5), WHITE),
        ):
            pygame.draw.rect(beam, c, (int(cx - width), 0, max(1, int(width * 2)), length))
        surface.blit(beam, (int(x - cx), int(stop)), special_flags=pygame.BLEND_RGB_ADD)
        blit_glow(surface, x, top, int(half * 4), color)
        if stop > 0:
            blit_glow(surface, x, stop, int(half * 3), color)

    def spawn_obstacles(self, dt: float, *, barriers: bool = True) -> None:
        # Barriers and asteroids are kept apart in time so an asteroid never plugs a gap.
        self.barrier_timer -= dt
        self.rock_timer -= dt
        if not barriers:  # boss fight: hold off barriers and asteroids, but keep pickups coming
            self.barrier_timer = max(self.barrier_timer, 3.0)
            self.rock_timer = max(self.rock_timer, 3.0)
        if self.barrier_timer <= 0:
            self.spawn_barrier()
            self.barrier_timer = random.uniform(5.0, 8.0) - min(2.5, self.level * 0.25)
        if self.rock_timer <= 0:
            size = "large" if random.random() < 0.4 else "small"
            r = ASTEROID_RADII[size]
            self.asteroids.append(
                Asteroid(
                    size,
                    random.uniform(r, cfg.WIDTH - r),
                    -r,
                    random.uniform(-40, 40),
                    self.scroll_speed * random.uniform(1.0, 1.3),
                )
            )
            self.rock_timer = (random.uniform(1.6, 3.2) - min(1.0, self.level * 0.1)) / self.width_factor
            self.barrier_timer = max(self.barrier_timer, 1.2)
        self.pickup_timer -= dt
        if self.pickup_timer <= 0:
            self.pickup_timer = random.uniform(8, 13)
            self.powerups.append(PowerUp(random.uniform(40, cfg.WIDTH - 40), -15, random_pickup_kind()))

    def spawn_barrier(self) -> None:
        level, speed = self.level, self.scroll_speed
        weights = {
            "wall": 3,
            "mines": 2.2,
            "gate": 2,
            "spinner": 1 if level < 2 else 2,
            "slider": 1 if level < 2 else 2,
        }
        kinds = list(weights)
        kind = random.choices(kinds, weights=[weights[k] for k in kinds])[0]
        names = {"mines": Mine.name, "gate": LaserGate.name, "spinner": Spinner.name, "slider": "SLIDING WALLS"}
        if kind in names and kind not in self.seen_barriers:
            self.seen_barriers.add(kind)
            self.effects.append(FloatText(cfg.WIDTH / 2, 110, f"WARNING: {names[kind]}", YELLOW, life=2.5))
            self.sfx.play("warning")

        if kind == "wall":
            self.walls.append(Wall(level, speed))
        elif kind == "slider":
            self.walls.append(SlidingWall(level, speed))
        elif kind == "gate":
            self.hazards.append(LaserGate(level, speed))
        elif kind == "spinner":
            self.hazards.append(Spinner(level, speed))
        else:
            xs = random.sample(
                range(40, cfg.WIDTH - 40, 50),
                min(
                    len(range(40, cfg.WIDTH - 40, 50)),
                    int(random.randint(3, 4 + min(3, level // 2)) * self.width_factor),
                ),
            )
            for i, x in enumerate(xs):
                self.hazards.append(Mine(x + random.uniform(-10, 10), -20 - i * random.uniform(25, 55), speed * 0.9))
        self.rock_timer = max(self.rock_timer, 2.3 if kind == "spinner" else 1.6)

    def detonate(self, mine: Mine, *, scored: bool = True) -> None:
        """Mine explosion: hurts the player, enemies, asteroids and sets off other mines in range."""
        if not mine.alive:
            return
        mine.alive = False
        if scored:
            self.score += mine.score_value
            self.roll_drop(mine.x, mine.y, 0.06)
        self.explode(mine.x, mine.y, (255, 120, 60), 1.6)
        self.sfx.play("explosion")
        self.effects.append(Shockwave(mine.x, mine.y, (255, 200, 120), max_radius=Mine.BLAST, life=0.35))
        reach = Mine.BLAST
        for e in self.enemies:
            if e.alive and math.hypot(e.x - mine.x, e.y - mine.y) < reach + e.w / 2:
                self.damage_enemy(e, mine.damage)
        for a in list(self.asteroids):
            if a.alive and math.hypot(a.x - mine.x, a.y - mine.y) < reach + a.radius and a.hit(4):
                self.destroy_asteroid(a)
        for h in self.hazards:
            if isinstance(h, Mine) and h.alive and math.hypot(h.x - mine.x, h.y - mine.y) < reach + Mine.RADIUS:
                self.detonate(h, scored=scored)
        p = self.player
        if p.alive and math.hypot(p.x - mine.x, p.y - mine.y) < reach + 10:
            self.damage_player(mine.damage, mine.x, mine.y)

    def shoot_down_missile(self, m: EnemyMissile) -> None:
        m.alive = False
        self.score += 10
        self.explode(m.x, m.y, (255, 140, 60), 0.6)
        self.sfx.play("hit")

    def destroy_turret(self, boss: Boss, turret: BossPart) -> None:
        self.score += 300
        self.explode(turret.x, turret.y, ORANGE, 1.6)
        self.effects.append(FloatText(turret.x, turret.y - 20, "+300", ORANGE))
        self.sfx.play("big_explosion")
        self.shake = max(self.shake, 0.3)
        if not boss.shielded:
            self.show_banner("CORE EXPOSED!", "Destroy the reactor", color=ORANGE)
            self.sfx.play("level_up")

    def kill_boss(self, boss: Boss) -> None:
        boss.state = "dying"
        boss.core.alive = False
        self.explode(boss.core.x, boss.core.y, (255, 220, 160), 2.5)
        self.sfx.play("big_explosion")
        self.shake = 0.8
        for m in self.enemy_bullets:
            if isinstance(m, EnemyMissile):
                m.alive = False
                self.explode(m.x, m.y, (255, 140, 60), 0.5)

    def boss_destroyed(self, boss: Boss) -> None:
        bonus = 5000 * (boss.number + 1)
        self.score += bonus
        for _ in range(3):
            self.explode(boss.x + random.uniform(-80, 80), boss.y + random.uniform(-30, 30), ORANGE, 2.5)
        self.effects.append(Shockwave(boss.x, boss.y, (255, 220, 160), max_radius=220, life=0.8))
        self.shake = 1.0
        self.sfx.play("big_explosion", min_gap=0)
        self.sfx.play("extra_life")
        for kind in ("repair", "invincible", random.choice(("spread", "laser", "missile")), "slowmo", "nuke"):
            self.powerups.append(PowerUp(boss.x + random.uniform(-120, 120), boss.y + random.uniform(-20, 40), kind))
        self.show_banner("MOTHERSHIP DESTROYED", f"Bonus +{bonus}", duration=3.0, color=YELLOW)
        self.boss = None
        self.boss_count += 1
        self.next_boss_level += self.boss_level
        # beating the boss advances exactly one level, however many points the fight was worth
        self.level_discount = self.score - (self.level + 1 - self.start_level) * POINTS_PER_LEVEL

    def bullet_hits_boss(self, b: Bullet, br: pygame.Rect) -> bool:
        """Resolve a player shot against the boss. Returns True if the boss absorbed it."""
        boss = self.boss
        if not boss or boss.state == "dying" or boss.y < -40:
            return False
        for turret in boss.turrets:
            if turret.alive and turret.hits_rect(br):
                if turret.hit(b.damage):
                    self.destroy_turret(boss, turret)
                else:
                    self.spawn_sparks(b.x, b.y, YELLOW, 4)
                    self.sfx.play("hit")
                return True
        core = boss.core
        if core.alive and core.hits_rect(br, extra=8 if boss.shielded else 0):
            if boss.shielded:
                self.spawn_sparks(b.x, b.y, (120, 200, 255), 5)
                self.sfx.play("deflect")
            elif core.hit(b.damage):
                self.kill_boss(boss)
            else:
                self.spawn_sparks(b.x, b.y, (255, 160, 80), 4)
                self.sfx.play("hit")
            return True
        return False  # shots pass over the hull itself: only the turrets and core can be hit

    def roll_drop(self, x: float, y: float, chance: float) -> None:
        if random.random() < chance:
            self.powerups.append(PowerUp(x, y, random_pickup_kind()))

    def destroy_enemy(self, e: Enemy, *, scored: bool = True) -> None:
        """Blow up an enemy. Unscored when an obstacle wrecked it rather than the player."""
        e.alive = False
        if scored:
            self.score += e.score_value
            self.roll_drop(e.x, e.y, {"scout": 0.04, "fighter": 0.08, "heavy": 0.4}[e.kind])
        size = {"scout": 0.8, "fighter": 1.0, "heavy": 1.8}[e.kind]
        color = {"scout": (255, 80, 100), "fighter": (190, 90, 255), "heavy": ORANGE}[e.kind]
        self.explode(e.x, e.y, color, size)
        self.sfx.play("big_explosion" if e.kind == "heavy" else "explosion")

    def damage_enemy(self, e: Enemy, amount: float) -> None:
        """Obstacle damage for an enemy, under the player's rules: `amount` is what the player would
        lose out of PLAYER_MAX_HEALTH, so the enemy loses the same share of its own health, and is
        then protected for HIT_INVULN seconds."""
        if not e.alive or e.invuln > 0:
            return
        e.invuln = HIT_INVULN
        if e.hit(amount / PLAYER_MAX_HEALTH * e.max_health):
            self.destroy_enemy(e, scored=False)
        else:
            self.spawn_sparks(e.x, e.y, ORANGE, 8)
            self.sfx.play("hit")

    def enemy_obstacle_collisions(self, wall_rects: list[pygame.Rect]) -> None:
        """Enemies crash into walls, active laser gates, spinners, asteroids and mines just as the player does."""
        for e in self.enemies:
            if not e.alive or e.y < -e.h:
                continue
            box = e.hitbox()
            damage = WALL_DAMAGE if box.collidelist(wall_rects) != -1 else 0
            for h in self.hazards:
                if h.alive and h.touches(box):
                    if isinstance(h, Mine):
                        self.detonate(h, scored=False)  # the blast does the damage
                    else:
                        damage = max(damage, h.damage)
            for a in self.asteroids:
                if a.alive and a.hits_rect(box):
                    self.destroy_asteroid(a, scored=False)
                    damage = max(damage, a.ram_damage)
            if damage:
                self.damage_enemy(e, damage)

    def destroy_asteroid(self, a: Asteroid, *, scored: bool = True) -> None:
        a.alive = False
        self.explode(a.x, a.y, (190, 160, 130), 1.3 if a.size == "large" else 0.7)
        self.sfx.play("rock_break")
        if not scored:
            return
        self.score += a.score_value
        if a.size == "large":
            for sign in (-1, 1):
                self.asteroids.append(
                    Asteroid("small", a.x + sign * 12, a.y, sign * random.uniform(50, 110), a.vy * 1.1)
                )
        self.roll_drop(a.x, a.y, 0.05)

    def kill_player(self) -> None:
        p = self.player
        p.alive = False
        self.lives -= 1
        current = p.arsenal[p.selected]
        current["level"] = max(1, current["level"] - 1)
        self.explode(p.x, p.y, CYAN, 2.2)
        self.explode(p.x, p.y, ORANGE, 1.2)
        self.sfx.play("big_explosion")
        self.shake = 0.5
        self.respawn_timer = 1.8

    def damage_player(self, amount: float, x: float, y: float) -> None:
        if self.player.hit(amount):
            self.sfx.play("hurt")
            self.spawn_sparks(x, y, CYAN, 10)
            self.shake = max(self.shake, 0.1 + amount / 150)

    def collect(self, p: PowerUp) -> None:
        player = self.player
        self.effects.append(Shockwave(p.x, p.y, p.color, max_radius=30, life=0.3))
        label = PICKUPS[p.kind]["name"]
        self.sfx.play({"repair": "heal", "invincible": "invincible", "slowmo": "heal"}.get(p.kind, "pickup"))
        if p.kind in WEAPONS:
            player.collect_weapon(p.kind)
            if p.kind == "nuke":
                label = f"NUKE x{int(player.arsenal['nuke']['ammo'] or 0)}: select (5) & fire!"
            else:
                label = f"{WEAPONS[p.kind]['name']} LV{player.weapon_level}"
        elif p.kind == "repair":
            if player.health >= player.max_health:
                self.score += 50
                label = "+50"
            player.health = min(player.max_health, player.health + 35)
        elif p.kind == "invincible":
            player.invincible = INVINCIBLE_TIME
            label = "INVINCIBLE!"
        elif p.kind == "slowmo":
            if self.slowmo_charges >= MAX_SLOWMO:
                self.score += 50
                label = "+50"
            self.slowmo_charges = min(MAX_SLOWMO, self.slowmo_charges + 1)
        self.effects.append(FloatText(p.x, p.y - 20, label, p.color))

    def fire_nuke(self) -> None:
        """Destroy everything on screen: enemies, asteroids, mines, barriers and enemy fire.
        The boss loses all its turrets and a third of its core's health rather than dying outright."""
        p = self.player
        p.use_ammo(1)
        p.emptied = None  # running out of nukes needs no "EMPTY" warning
        self.nuke_flash = 1.0
        self.shake = 1.2
        self.sfx.play("nuke", min_gap=0)
        self.effects.append(
            Shockwave(p.x, p.y, (255, 245, 200), max_radius=int(max(cfg.WIDTH, HEIGHT) * 1.1), life=1.0)
        )
        self.effects.append(FloatText(p.x, p.y - 50, "NUCLEAR STRIKE!", WEAPONS["nuke"]["color"], life=1.5))

        def on_screen(obj: HasY, margin: float = 30) -> bool:
            return -margin < obj.y < HEIGHT + margin

        for e in self.enemies:
            if e.alive and on_screen(e):
                self.destroy_enemy(e)
        for a in self.asteroids:
            if a.alive and on_screen(a):
                a.alive = False
                self.score += a.score_value
                self.explode(a.x, a.y, (190, 160, 130), 0.9)
        for h in self.hazards:
            if h.alive and on_screen(h, 60):
                h.alive = False
                self.score += getattr(h, "score_value", 25)
                self.explode(h.x if hasattr(h, "x") else cfg.WIDTH / 2, h.y, ORANGE, 1.0)
        for w in self.walls:
            if w.alive and on_screen(w):
                w.alive = False
                for left, right in w.segments:
                    for x in range(left + 20, right, 70):
                        self.explode(x, w.y + w.H / 2, (200, 200, 220), 0.7)
        for shot in self.enemy_bullets:
            shot.alive = False
        boss = self.boss
        if boss and boss.state != "dying" and boss.y > -60:
            for turret in boss.turrets:
                if turret.alive:
                    turret.hit(turret.health)
                    self.destroy_turret(boss, turret)
            if boss.core.hit(boss.core.max_health / 3):
                self.kill_boss(boss)

    def activate_slowmo(self) -> None:
        if self.slowmo_active:
            return
        if self.slowmo_charges <= 0:
            self.sfx.play("empty")
            self.effects.append(FloatText(self.player.x, self.player.y - 40, "NO SLOW-MO: grab an hourglass", GRAY))
            return
        self.slowmo_charges -= 1
        self.slowmo_active = True
        self.slowmo_time = SLOWMO_TIME
        self.sfx.play("slowmo_on")
        self.effects.append(FloatText(self.player.x, self.player.y - 40, "SLOW-MO", PICKUPS["slowmo"]["color"]))

    def end_game(self) -> None:
        self.sfx.play("game_over")
        self.slowmo_active = False
        self.banner = None
        self.state_time = 0.0
        if qualifies(self.scores, self.score) and not self.practice:
            self.state = "enter_name"
            self.name = list(self.last_initials)
            self.name_pos = 0
            pygame.key.set_repeat(300, 70)  # holding up/down scrolls through letters
        else:
            self.state = "game_over"

    def submit_name(self) -> None:
        name = "".join(self.name)
        self.last_initials = name
        rank = sum(1 for _, sc in self.scores if sc >= self.score)
        self.scores.insert(rank, (name, self.score))
        del self.scores[SCOREBOARD_SIZE:]
        save_scores(self.scores, self.scores_file)
        self.new_rank = rank
        self.state = "game_over"
        self.state_time = 0.0
        pygame.key.set_repeat()
        self.sfx.play("extra_life")

    def go_to_title(self) -> None:
        self.state = "title"
        # after setting a new high score, open the title screen on the score table
        self.title_started = self.t - (TITLE_PAGE_TIME if self.new_rank is not None else 0)
        self.sfx.play("menu")

    def handle_collisions(self) -> None:
        wall_rects = [r for w in self.walls for r in w.rects()]

        for b in self.bullets:
            if not b.alive:
                continue
            br = b.sweep_rect()
            for e in self.enemies:
                if e.alive and br.colliderect(e.hitbox()):
                    b.alive = False
                    if e.hit(b.damage):
                        self.destroy_enemy(e)
                    else:
                        self.spawn_sparks(b.x, b.y, YELLOW, 4)
                        self.sfx.play("hit")
                    break
            if not b.alive:
                continue
            for m in self.enemy_bullets:
                if isinstance(m, EnemyMissile) and m.alive and br.colliderect(m.rect()):
                    b.alive = False
                    self.shoot_down_missile(m)
                    break
            if b.alive and self.bullet_hits_boss(b, br):
                b.alive = False
            if not b.alive:
                continue
            for a in self.asteroids:
                if a.alive and a.hits_rect(br):
                    b.alive = False
                    if a.hit(b.damage):
                        self.destroy_asteroid(a)
                    else:
                        self.spawn_sparks(b.x, b.y, (200, 180, 150), 4)
                        self.sfx.play("hit")
                    break
            if b.alive and br.collidelist(wall_rects) != -1:
                b.alive = False
                self.spawn_sparks(b.x, b.y, (200, 200, 220), 4)
            if not b.alive:
                continue
            for h in self.hazards:
                if h.alive and h.blocks(br):
                    b.alive = False
                    if isinstance(h, Mine) and h.hit(b.damage):
                        self.detonate(h)
                    else:
                        self.spawn_sparks(b.x, b.y, (200, 200, 220), 4)
                    break

        for b in self.enemy_bullets:
            if not b.alive:
                continue
            br = b.sweep_rect()
            if (
                br.collidelist(wall_rects) != -1
                or any(a.alive and a.hits_rect(br) for a in self.asteroids)
                or any(h.alive and h.blocks(br) for h in self.hazards)
            ):
                b.alive = False
                self.spawn_sparks(b.x, b.y, b.color, 4)

        for a in self.asteroids:
            if a.alive and any(a.hits_rect(r) for r in wall_rects):
                self.destroy_asteroid(a, scored=False)
                continue
            core_rect = pygame.Rect(
                int(a.x - a.radius * 0.6), int(a.y - a.radius * 0.6), int(a.radius * 1.2), int(a.radius * 1.2)
            )
            for h in self.hazards:
                if a.alive and h.alive and h.touches(core_rect):
                    if isinstance(h, Mine):
                        self.detonate(h, scored=False)
                    else:
                        self.destroy_asteroid(a, scored=False)

        self.enemy_obstacle_collisions(wall_rects)

        if not self.player.alive:
            return
        player = self.player
        body = player.hitbox()
        core = player.core()
        invincible = player.invincible > 0
        for e in self.enemies:
            if e.alive and body.colliderect(e.hitbox()):
                if invincible:
                    self.destroy_enemy(e)
                elif not player.protected:
                    self.destroy_enemy(e)
                    self.damage_player(e.ram_damage, e.x, e.y)
        for b in self.enemy_bullets:
            if b.alive and core.colliderect(b.rect()):
                if invincible:
                    b.alive = False
                    self.spawn_sparks(b.x, b.y, (255, 215, 60), 4)
                    self.sfx.play("deflect")
                elif not player.protected:
                    b.alive = False
                    self.damage_player(b.damage, b.x, b.y)
        for a in self.asteroids:
            if a.alive and a.hits_rect(body):
                if invincible:
                    self.destroy_asteroid(a)
                elif not player.protected:
                    self.destroy_asteroid(a, scored=False)
                    self.damage_player(a.ram_damage, a.x, a.y)
        if not player.protected and body.collidelist(wall_rects) != -1:
            self.damage_player(WALL_DAMAGE, player.x, player.y - 10)
        boss = self.boss
        if boss and boss.state != "dying" and not player.protected and body.collidelist(boss.hull_rects()) != -1:
            self.damage_player(40, player.x, player.y - 10)
        for h in self.hazards:
            if not (h.alive and h.touches(body)):
                continue
            if isinstance(h, Mine):
                if invincible:
                    h.alive = False
                    self.score += h.score_value
                    self.explode(h.x, h.y, (255, 120, 60), 1.2)
                elif not player.protected:
                    self.detonate(h, scored=False)
            elif not player.protected:
                self.damage_player(h.damage, player.x, player.y - 10)
        for p in self.powerups:
            if p.alive and body.colliderect(p.rect()):
                p.alive = False
                self.collect(p)
        if player.health <= 0:
            self.kill_player()

    # -- drawing -----------------------------------------------------------

    def draw_background(self, surface: pygame.Surface) -> None:
        y = int(self.nebula_y)
        surface.blit(self.nebula, (0, y))
        surface.blit(self.nebula, (0, y - HEIGHT))
        for star in self.stars:
            star.draw(surface)

    def draw(self) -> None:
        c = self.canvas
        self.draw_background(c)

        if self.state == "title":
            self.draw_title(c)
        else:
            for w in self.walls:
                w.draw(c)
            for a in self.asteroids:
                a.draw(c)
            for h in self.hazards:
                h.draw(c)
            if self.boss:
                self.boss.draw(c, self.t)
            for p in self.powerups:
                p.draw(c)
            for b in self.bullets:
                b.draw(c)
            for e in self.enemies:
                e.draw(c, self.t)
            self.draw_laser(c)
            if self.player.alive:
                self.player.draw(c)
            for b in self.enemy_bullets:
                b.draw(c)
            for fx in self.effects:
                fx.draw(c)
            for particle in self.particles:
                particle.draw(c)
            if self.nuke_flash > 0:
                flash = pygame.Surface((cfg.WIDTH, HEIGHT))
                flash.fill((255, 250, 235))
                flash.set_alpha(int(255 * self.nuke_flash**1.5))
                c.blit(flash, (0, 0))
            if self.slowmo_active:
                fade = min(1.0, self.slowmo_time / 0.3)
                self.slowmo_tint.set_alpha(int(255 * fade))
                c.blit(self.slowmo_tint, (0, 0))
                border = tuple(int(v * fade * (0.6 + 0.4 * math.sin(self.t * 6))) for v in PICKUPS["slowmo"]["color"])
                pygame.draw.rect(c, border, (0, 64, cfg.WIDTH, HEIGHT - 64 - TRAY_H), 4)
            self.draw_hud(c)
            self.draw_banner(c)

            if self.state == "paused":
                self.draw_center_text(c, "PAUSED", "Press P to resume", CYAN)
            elif self.state == "enter_name":
                self.draw_name_entry(c)
            elif self.state == "game_over":
                self.draw_game_over(c)

        self.present()

    def present(self) -> None:
        """Scale the playfield to the window. Its aspect already matches, so bars only appear
        when the window is narrower than the base shape or wider than MAX_WIDTH allows."""
        sw, sh = self.screen.get_size()
        scale = min(sw / cfg.WIDTH, sh / HEIGHT)
        size = (max(1, int(cfg.WIDTH * scale)), max(1, int(HEIGHT * scale)))
        x, y = (sw - size[0]) // 2, (sh - size[1]) // 2
        if self.shake > 0:
            mag = int(10 * scale * min(1.0, self.shake * 2))
            x += random.randint(-mag, mag)
            y += random.randint(-mag, mag)
        self.screen.fill((0, 0, 0))
        frame = self.canvas if size == self.canvas.get_size() else pygame.transform.smoothscale(self.canvas, size)
        self.screen.blit(frame, (x, y))
        pygame.display.flip()

    @property
    def width_factor(self) -> float:
        return cfg.WIDTH / BASE_WIDTH

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        window = SDLWindow.from_display_module() if SDLWindow is not None else None
        if window:
            # desktop fullscreen keeps the display mode and just resizes the window to the screen
            if self.fullscreen:
                window.set_fullscreen(desktop=True)
            else:
                window.set_windowed()
                window.size = (BASE_WIDTH, HEIGHT)
        elif self.fullscreen:
            pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            pygame.display.set_mode((BASE_WIDTH, HEIGHT), pygame.RESIZABLE)
        self.fit_to_window()

    def fit_to_window(self) -> None:
        self.screen = pygame.display.get_surface()
        w, h = self.screen.get_size()
        new_width = int(clamp(round(HEIGHT * w / max(1, h)), BASE_WIDTH, MAX_WIDTH))
        if new_width != cfg.WIDTH:
            self.set_play_width(new_width)

    def set_play_width(self, new_width: int) -> None:
        """Change the playfield width, shifting everything in flight across proportionally."""
        old_width = cfg.WIDTH
        ratio = new_width / old_width
        cfg.WIDTH = new_width
        self.canvas = pygame.Surface((cfg.WIDTH, HEIGHT))
        self.slowmo_tint = pygame.Surface((cfg.WIDTH, HEIGHT), pygame.SRCALPHA)
        self.slowmo_tint.fill((70, 40, 160, 75))
        self.nebula = build_nebula()
        self.title_pickups = None

        target_stars = int(110 * self.width_factor)
        self.stars = self.stars[:target_stars]
        for star in self.stars:
            star.x *= ratio
        self.stars += [Star() for _ in range(target_stars - len(self.stars))]

        self.player.x *= ratio
        for group in (
            self.bullets,
            self.enemy_bullets,
            self.enemies,
            self.particles,
            self.effects,
            self.powerups,
            self.asteroids,
            self.hazards,
        ):
            for obj in group:
                if isinstance(obj, LaserGate):  # spans the full width; it reads WIDTH when drawn
                    continue
                obj.x *= ratio
                if hasattr(obj, "prev_x"):
                    obj.prev_x *= ratio
        for wall in self.walls:
            wall.rescale(ratio, old_width)
        if self.boss:
            self.boss.x *= ratio
            self.boss.place_parts()

    def draw_score_table(self, surface: pygame.Surface, top: float, highlight: int | None = None) -> None:
        self.draw_text(surface, "HIGH SCORES", self.font_big, YELLOW, (cfg.WIDTH / 2, top))
        font = get_font(20, bold=True)
        for i, (name, score) in enumerate(self.scores):
            y = top + 42 + i * 28
            color = RANK_COLORS[i % len(RANK_COLORS)]
            if i == highlight:
                if int(self.t * 4) % 2 == 0:
                    pygame.draw.rect(surface, (60, 60, 110), (60, y - 13, cfg.WIDTH - 120, 26), border_radius=4)
                color = WHITE
            self.draw_text(surface, f"{ordinal(i + 1):>4}   {name}   {score:>7d}", font, color, (cfg.WIDTH / 2, y))

    def draw_game_over(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((cfg.WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        self.draw_text(surface, "GAME OVER", self.font_big, RED, (cfg.WIDTH / 2, 120))
        self.draw_text(surface, f"SCORE {self.score:07d}", self.font, WHITE, (cfg.WIDTH / 2, 165))
        self.draw_score_table(surface, 220, highlight=self.new_rank)
        ready = self.state_time > 0.8
        hint_color = WHITE if ready else (90, 90, 100)
        self.draw_text(surface, "SPACE / M: menu      R: play again", self.font_small, hint_color, (cfg.WIDTH / 2, 560))

    def draw_name_entry(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((cfg.WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        flash = pygame.Color(0)
        flash.hsva = ((self.t * 200) % 360, 60, 100, 100)
        self.draw_text(surface, "NEW HIGH SCORE!", self.font_big, (flash.r, flash.g, flash.b), (cfg.WIDTH / 2, 170))
        rank = sum(1 for _, sc in self.scores if sc >= self.score) + 1
        self.draw_text(
            surface, f"SCORE {self.score:07d}     RANK {ordinal(rank)}", self.font, WHITE, (cfg.WIDTH / 2, 225)
        )
        self.draw_text(surface, "ENTER YOUR INITIALS", self.font, YELLOW, (cfg.WIDTH / 2, 300))

        for i, ch in enumerate(self.name):
            x = cfg.WIDTH / 2 + (i - 1) * 70
            selected = i == self.name_pos
            color = CYAN if selected else WHITE
            if selected:
                pygame.draw.polygon(surface, CYAN, [(x - 9, 345), (x + 9, 345), (x, 335)])
                pygame.draw.polygon(surface, CYAN, [(x - 9, 425), (x + 9, 425), (x, 435)])
                if int(self.t * 3) % 2 == 0:
                    pygame.draw.rect(surface, CYAN, (x - 22, 412, 44, 4))
            else:
                pygame.draw.rect(surface, (90, 90, 110), (x - 22, 412, 44, 4))
            self.draw_text(surface, ch, self.font_title, color, (x, 382))

        self.draw_text(
            surface, "Up/Down: change letter   Left/Right: move", self.font_small, (200, 200, 215), (cfg.WIDTH / 2, 480)
        )
        self.draw_text(surface, "or just type your initials", self.font_small, (200, 200, 215), (cfg.WIDTH / 2, 502))
        self.draw_text(surface, "SPACE: next letter    ENTER: done", self.font_small, WHITE, (cfg.WIDTH / 2, 535))

    def draw_text(
        self,
        surface: pygame.Surface,
        text: str,
        font: pygame.font.Font,
        color: Color,
        center: Point,
        *,
        shadow: bool = True,
    ) -> None:
        if shadow:
            sh = font.render(text, True, (0, 0, 0))
            surface.blit(sh, sh.get_rect(center=(center[0] + 2, center[1] + 2)))
        surf = font.render(text, True, color)
        surface.blit(surf, surf.get_rect(center=center))

    def draw_hud(self, surface: pygame.Surface) -> None:
        panel = pygame.Surface((cfg.WIDTH, 64), pygame.SRCALPHA)
        panel.fill((5, 8, 25, 150))
        pygame.draw.line(panel, (60, 120, 180, 180), (0, 63), (cfg.WIDTH, 63))
        surface.blit(panel, (0, 0))

        surface.blit(self.font.render(f"{self.score:07d}", True, WHITE), (12, 8))
        hi = self.font_small.render(f"HI {max(self.high_score, self.score):07d}", True, GRAY)
        surface.blit(hi, (cfg.WIDTH / 2 - hi.get_width() / 2, 12))
        lvl = self.font_small.render(f"LEVEL {self.level}", True, CYAN)
        surface.blit(lvl, (cfg.WIDTH - lvl.get_width() - 12, 12))
        small = get_font(11, bold=True)
        if not self.sfx.enabled:
            muted = small.render("SOUND OFF", True, GRAY)
            surface.blit(muted, (cfg.WIDTH / 2 - muted.get_width() / 2, 32))
        if self.practice:
            tag = small.render("PRACTICE - SCORES NOT SAVED", True, ORANGE)
            surface.blit(tag, (cfg.WIDTH / 2 - tag.get_width() / 2, 46))

        player = self.player
        bar_x, bar_y, bar_w, bar_h = 12, 38, 150, 12
        ratio = player.health / player.max_health if player.alive else 0
        pygame.draw.rect(surface, (30, 30, 45), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        color = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
        if ratio > 0:
            pygame.draw.rect(surface, color, (bar_x, bar_y, int(bar_w * ratio), bar_h), border_radius=4)
            pygame.draw.rect(
                surface, lerp_color(color, WHITE, 0.5), (bar_x + 2, bar_y + 2, max(0, int(bar_w * ratio) - 4), 2)
            )
        pygame.draw.rect(surface, (180, 200, 230), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=4)
        if player.invincible > 0:
            gold = PICKUPS["invincible"]["color"]
            pygame.draw.rect(
                surface, gold, (bar_x, bar_y + bar_h + 3, int(bar_w * player.invincible / INVINCIBLE_TIME), 3)
            )
        slow_color = PICKUPS["slowmo"]["color"]
        if self.slowmo_active:
            pygame.draw.rect(
                surface, slow_color, (bar_x, bar_y + bar_h + 8, int(bar_w * self.slowmo_time / SLOWMO_TIME), 3)
            )
        if self.slowmo_charges:
            for i in range(self.slowmo_charges):
                surface.blit(SPRITES["hud_slowmo"], (bar_x + bar_w + 10 + i * 20, bar_y - 3))
            hint = get_font(10, bold=True).render("SHIFT", True, slow_color)
            surface.blit(hint, (bar_x + bar_w + 14 + self.slowmo_charges * 20, bar_y + 1))

        self.draw_weapon_tray(surface)
        if self.boss and self.boss.state != "dying":
            self.draw_boss_bar(surface, self.boss)

    def draw_boss_bar(self, surface: pygame.Surface, boss: Boss) -> None:
        w = min(360, cfg.WIDTH - 60)
        x, y = cfg.WIDTH / 2 - w / 2, 74
        ratio = boss.total_health / boss.max_total
        label = get_font(11, bold=True).render(boss.name, True, (255, 140, 120))
        surface.blit(label, (x, y - 2))
        bar_y = y + 13
        pygame.draw.rect(surface, (35, 20, 25), (x, bar_y, w, 8), border_radius=3)
        pygame.draw.rect(
            surface, (255, 80, 60) if boss.shielded else (255, 170, 60), (x, bar_y, int(w * ratio), 8), border_radius=3
        )
        pygame.draw.rect(surface, (200, 160, 160), (x, bar_y, w, 8), 1, border_radius=3)
        if boss.shielded:
            note = f"TURRETS LEFT: {sum(t.alive for t in boss.turrets)}"
            color = (230, 200, 200)
        else:
            note = "CORE EXPOSED"
            color = YELLOW if int(self.t * 4) % 2 == 0 else ORANGE
        text = get_font(11, bold=True).render(note, True, color)
        surface.blit(text, (x + w - text.get_width(), y - 2))

        icon = SPRITES["life_icon"]
        for i in range(self.lives):
            surface.blit(icon, (cfg.WIDTH - 12 - (i + 1) * (icon.get_width() + 4), 36))

    def draw_weapon_tray(self, surface: pygame.Surface) -> None:
        player = self.player
        top = HEIGHT - TRAY_H
        panel = pygame.Surface((cfg.WIDTH, TRAY_H), pygame.SRCALPHA)
        panel.fill((5, 8, 25, 190))
        pygame.draw.line(panel, (60, 120, 180, 180), (0, 0), (cfg.WIDTH, 0))
        surface.blit(panel, (0, top))

        n_slots = len(WEAPON_ORDER)
        slot_h, gap = 34, 5
        slot_w = int(min(110, (cfg.WIDTH - 16 - gap * (n_slots - 1)) / n_slots))
        x0 = (cfg.WIDTH - (slot_w * n_slots + gap * (n_slots - 1))) / 2
        y = top + (TRAY_H - slot_h) / 2
        tiny = get_font(10, bold=True)
        for i, kind in enumerate(WEAPON_ORDER):
            weapon = WEAPONS[kind]
            owned = player.arsenal.get(kind)
            selected = kind == player.selected
            rect = pygame.Rect(int(x0 + i * (slot_w + gap)), int(y), slot_w, slot_h)
            if selected:
                blit_glow(surface, rect.centerx, rect.centery, 40, weapon["color"], strength=0.35)
            pygame.draw.rect(surface, (20, 24, 40) if owned else (12, 14, 22), rect, border_radius=6)
            border = weapon["color"] if selected else ((90, 95, 115) if owned else (40, 42, 55))
            pygame.draw.rect(surface, border, rect, 2 if selected else 1, border_radius=6)

            icon = SPRITES["tray_" + kind]
            if not owned:
                icon = icon.copy()
                icon.set_alpha(50)
            surface.blit(icon, icon.get_rect(center=(rect.x + 17, rect.centery)))
            key = tiny.render(str(i + 1), True, WHITE if owned else (80, 80, 95))
            surface.blit(key, (rect.x + 4, rect.y + 2))

            text_x = rect.x + 32
            name = tiny.render(weapon["name"], True, weapon["color"] if owned else (70, 72, 90))
            surface.blit(name, (text_x, rect.y + 4))
            if not owned:
                continue
            for lv in range(MAX_WEAPON if kind != "nuke" else 0):
                pygame.draw.rect(
                    surface,
                    weapon["color"] if lv < owned["level"] else (50, 50, 60),
                    (text_x + lv * 8, rect.y + 17, 6, 5),
                    border_radius=1,
                )
            bar_w = slot_w - 32 - 6
            if owned["ammo"] is None:
                ratio, bar_color = 1.0, weapon["color"]
            else:
                ratio = owned["ammo"] / (WEAPON_AMMO[kind] * AMMO_CAP)
                low = owned["ammo"] < WEAPON_AMMO[kind] * 0.25
                bar_color = RED if low and int(self.t * 6) % 2 == 0 else weapon["color"]
            pygame.draw.rect(surface, (40, 42, 55), (text_x, rect.bottom - 8, bar_w, 4))
            pygame.draw.rect(surface, bar_color, (text_x, rect.bottom - 8, max(1, int(bar_w * ratio)), 4))

            ammo = owned["ammo"]
            count = "INF" if ammo is None else f"{math.ceil(ammo)}{'s' if kind == 'laser' else ''}"
            amt = tiny.render(count, True, (200, 200, 215))
            surface.blit(amt, (rect.right - amt.get_width() - 5, rect.y + 14))

    def draw_banner(self, surface: pygame.Surface) -> None:
        if not self.banner:
            return
        b = self.banner
        elapsed = b.duration - b.time
        alpha = clamp(min(elapsed / 0.25, b.time / 0.5), 0, 1)
        title = self.font_big.render(b.title, True, b.color)
        title.set_alpha(int(255 * alpha))
        surface.blit(title, title.get_rect(center=(cfg.WIDTH / 2, HEIGHT * 0.36)))
        if b.subtitle:
            sub = self.font.render(b.subtitle, True, WHITE)
            sub.set_alpha(int(220 * alpha))
            surface.blit(sub, sub.get_rect(center=(cfg.WIDTH / 2, HEIGHT * 0.36 + 40)))

    def draw_center_text(
        self, surface: pygame.Surface, title: str, subtitle: str, color: Color, hint: str | None = None
    ) -> None:
        overlay = pygame.Surface((cfg.WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))
        self.draw_text(surface, title, self.font_big, color, (cfg.WIDTH / 2, HEIGHT / 2 - 40))
        self.draw_text(surface, subtitle, self.font_small, WHITE, (cfg.WIDTH / 2, HEIGHT / 2 + 10))
        if hint:
            self.draw_text(surface, hint, self.font_small, GRAY, (cfg.WIDTH / 2, HEIGHT / 2 + 40))

    def draw_title(self, surface: pygame.Surface) -> None:
        cy = 150 + math.sin(self.t * 2) * 4
        blit_glow(surface, cfg.WIDTH / 2, cy, 140, (30, 70, 140))
        self.draw_text(surface, "NOVA", self.font_title, CYAN, (cfg.WIDTH / 2, cy - 30))
        self.draw_text(surface, "STRIKE", self.font_title, WHITE, (cfg.WIDTH / 2, cy + 25))

        page = int((self.t - self.title_started) / TITLE_PAGE_TIME) % 2
        if page == 1:
            self.draw_score_table(surface, 270)
        else:
            self.draw_title_info(surface)

        arrow_l = "<" if self.start_lives > 1 else " "
        arrow_r = ">" if self.start_lives < MAX_LIVES else " "
        self.draw_text(
            surface, f"{arrow_l}  LIVES: {self.start_lives}  {arrow_r}", self.font, YELLOW, (cfg.WIDTH / 2, 592)
        )
        icon = SPRITES["life_icon"]
        total_w = self.start_lives * (icon.get_width() + 4)
        for i in range(self.start_lives):
            surface.blit(icon, (cfg.WIDTH / 2 - total_w / 2 + i * (icon.get_width() + 4), 607))

        if int(self.t * 2) % 2 == 0:
            self.draw_text(surface, "PRESS SPACE TO LAUNCH", self.font, WHITE, (cfg.WIDTH / 2, 645))
        next_key = "Cmd" if IS_MAC else "Alt"
        self.draw_text(
            surface, "Move: Arrows/WASD   Fire: Space   Slow-mo: Shift", self.font_small, GRAY, (cfg.WIDTH / 2, 668)
        )
        self.draw_text(
            surface, f"Weapon: {next_key} next, Ctrl prev   Pause: P", self.font_small, GRAY, (cfg.WIDTH / 2, 686)
        )
        self.draw_text(
            surface,
            "Sound: N   Pause: Esc" if IS_WEB else "Sound: N   Fullscreen: F / F11   Quit: Esc",
            self.font_small,
            GRAY,
            (cfg.WIDTH / 2, 704),
        )

    def draw_title_info(self, surface: pygame.Surface) -> None:
        y = 260
        for kind in ("scout", "fighter", "heavy"):
            sprite = SPRITES[kind]
            surface.blit(sprite, sprite.get_rect(center=(cfg.WIDTH / 2 - 70, y)))
            label = self.font_small.render(
                f"{kind.upper():<8} {ENEMY_TYPES[kind]['score']:>3} PTS", True, (200, 200, 215)
            )
            surface.blit(label, (cfg.WIDTH / 2 - 30, y - label.get_height() / 2))
            y += 46
        self.draw_text(
            surface,
            "Dodge rocks, walls, laser gates, mines & spinners!",
            self.font_small,
            (255, 200, 120),
            (cfg.WIDTH / 2, 392),
        )
        self.draw_text(
            surface, "Fly into power-ups to collect them:", self.font_small, (200, 200, 215), (cfg.WIDTH / 2, 416)
        )
        if self.title_pickups is None:
            kinds = list(PICKUPS)
            rows = (kinds[:4], kinds[4:])
            self.title_pickups = [
                PowerUp(cfg.WIDTH / 2 + (i - (len(row) - 1) / 2) * 100, 455 + r * 62, kind)
                for r, row in enumerate(rows)
                for i, kind in enumerate(row)
            ]
        for icon in self.title_pickups:
            icon.age = self.t
            icon.draw(surface)

    # -- main loop ---------------------------------------------------------

    def handle_key(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if IS_WEB:  # a web page can't quit: Esc pauses instead
                if self.state == "playing":
                    self.state = "paused"
                return
            if self.fullscreen:
                self.toggle_fullscreen()
                return
            pygame.quit()
            sys.exit()
        if not IS_WEB and (key == pygame.K_F11 or (key == pygame.K_f and self.state != "enter_name")):
            self.toggle_fullscreen()
            return
        if self.state == "enter_name":
            self.handle_name_key(key)
            return
        if key == pygame.K_n:
            self.sfx.toggle()
            self.sfx.play("menu")
            return
        if self.state == "title":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.start_lives = max(1, self.start_lives - 1)
                self.sfx.play("menu")
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.start_lives = min(MAX_LIVES, self.start_lives + 1)
                self.sfx.play("menu")
            elif key in (pygame.K_SPACE, pygame.K_RETURN):
                self.reset()
                self.sfx.play("start")
        elif self.state == "playing":
            if key == pygame.K_p:
                self.state = "paused"
                self.sfx.play("menu")
            elif self.player.alive:
                before = self.player.selected
                number_keys = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)
                if key in NEXT_WEAPON_KEYS:
                    self.player.cycle(1)
                elif key in PREV_WEAPON_KEYS:
                    self.player.cycle(-1)
                elif key in number_keys:
                    self.player.select(WEAPON_ORDER[number_keys.index(key)])
                elif key in SLOWMO_KEYS:
                    self.activate_slowmo()
                elif key == pygame.K_SPACE and self.player.weapon_type == "nuke":
                    self.fire_nuke()  # needs a fresh press: holding fire never launches a nuke
                if self.player.selected != before:
                    self.sfx.play("switch")
        elif self.state == "paused" and key == pygame.K_p:
            self.state = "playing"
            self.sfx.play("menu")
        elif self.state == "game_over" and self.state_time > 0.8:  # brief pause so a held fire key can't skip it
            if key == pygame.K_r:
                self.reset()
                self.sfx.play("start")
            elif key in (pygame.K_SPACE, pygame.K_m, pygame.K_RETURN):
                self.go_to_title()

    def handle_name_key(self, key: int) -> None:
        if self.state_time < 0.6:
            return
        if key in (pygame.K_UP, pygame.K_DOWN):
            step = 1 if key == pygame.K_UP else -1
            ch = self.name[self.name_pos]
            idx = NAME_CHARS.index(ch) if ch in NAME_CHARS else 0
            self.name[self.name_pos] = NAME_CHARS[(idx + step) % len(NAME_CHARS)]
            self.sfx.play("switch", min_gap=0)
        elif key in (pygame.K_LEFT, pygame.K_BACKSPACE):
            self.name_pos = max(0, self.name_pos - 1)
            self.sfx.play("menu", min_gap=0)
        elif key == pygame.K_RIGHT:
            self.name_pos = min(2, self.name_pos + 1)
            self.sfx.play("menu", min_gap=0)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.submit_name()
        elif key == pygame.K_SPACE:
            if self.name_pos < 2:
                self.name_pos += 1
                self.sfx.play("menu", min_gap=0)
            else:
                self.submit_name()
        else:
            ch = pygame.key.name(key).upper()
            if len(ch) == 1 and ch in NAME_CHARS:
                self.name[self.name_pos] = ch
                self.name_pos = min(2, self.name_pos + 1)
                self.sfx.play("switch", min_gap=0)

    def frame(self) -> None:
        """Advance the game by one frame: input, update, draw."""
        dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT and not IS_WEB:  # a web page can't close itself
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
        if (
            self.screen.get_size() != pygame.display.get_surface().get_size()
            or self.screen is not pygame.display.get_surface()
        ):
            self.fit_to_window()

        keys = pygame.key.get_pressed()
        self.update(dt, keys)
        self.sfx.set_loop("laser", on=self.state == "playing" and self.laser is not None)
        self.draw()

    def run(self) -> None:
        """The native main loop."""
        while True:
            self.frame()

    async def run_async(self) -> None:
        """The browser main loop: yields to the page after every frame so it stays responsive."""
        while True:
            self.frame()
            await asyncio.sleep(0)
