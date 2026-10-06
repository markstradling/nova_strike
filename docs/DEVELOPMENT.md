# Development guide

## Setting up

```bash
python -m venv venv
venv/bin/pip install -r requirements-dev.txt
```

| File | Contents |
|---|---|
| `requirements.txt` | What the game needs to run: pygame. |
| `requirements-web.txt` | Adds what the browser build needs: pygbag, certifi and playwright. |
| `requirements-dev.txt` | Adds everything above plus ruff, mypy and pytest. |

## Running the checks

```bash
venv/bin/ruff check .                         # lint
venv/bin/ruff format .                        # format (use --check to only report)
venv/bin/mypy nova_strike tests main.py scripts   # type-check (strict mode)
venv/bin/pytest                               # unit tests
```

All four should pass before a change is finished. Their settings are in `pyproject.toml`.

## Tests

The tests live in `tests/` and run headless, using SDL's dummy video and audio drivers, in a few seconds.

| File | Covers |
|---|---|
| `test_gfx.py` | Drawing and geometry helpers |
| `test_sound.py` | Sound synthesis and playback rules |
| `test_scores.py` | Saving, loading and ranking high scores |
| `test_cli.py` | Command-line options |
| `test_weapons.py` | Bullets, homing missiles, power-ups and pickup rarity |
| `test_player.py` | Movement, the weapon inventory, ammo and firing |
| `test_enemies.py` | Enemy firing, health and how they're chosen |
| `test_obstacles.py` | Walls, laser gates, mines, spinners and asteroids |
| `test_enemy_obstacles.py` | Enemies taking barrier damage under the player's rules |
| `test_ai.py` | Enemy obstacle avoidance |
| `test_boss.py` | The mothership fight |
| `test_game.py` | Whole-game behaviour: levels, lives, pickups, slow-mo, the nuke, controls, high scores, resizing |

Fixtures in `tests/conftest.py`:

- `game`: a game in progress with all spawning switched off, so a test controls exactly what's on screen.
- `step(game, frames, keys)`: advance the game, optionally with keys held (use `Keys({pygame.K_SPACE: True})`).
- Every test automatically uses a temporary high score file, so tests can never touch your real scores.
- The playfield width is reset after each test.

## Changing the game

Most tuning values are in `nova_strike/config.py`:

| To change | Edit |
|---|---|
| Lives, extra lives, points per level | `DEFAULT_LIVES`, `MAX_LIVES`, `EXTRA_LIFE_EVERY`, `POINTS_PER_LEVEL` |
| Enemy speed, health, points, fire rate, damage, agility | `ENEMY_TYPES` |
| Weapon ammo and capacity | `WEAPON_AMMO`, `AMMO_CAP` |
| How often each power-up appears | `PICKUP_WEIGHTS` |
| Invincibility and slow-motion | `INVINCIBLE_TIME`, `SLOWMO_TIME`, `SLOWMO_FACTOR`, `MAX_SLOWMO` |
| Player health and post-hit protection | `PLAYER_MAX_HEALTH`, `HIT_INVULN` (they apply to enemies too) |
| When the boss appears | `BOSS_LEVEL` |

Other values live with the code they affect:

| To change | Where |
|---|---|
| Barrier damage | `damage` on `LaserGate`, `Mine`, `Spinner` in `obstacles.py`; `WALL_DAMAGE` in `config.py` |
| How often each barrier type appears | `Game.spawn_barrier` in `game.py` |
| Enemy spawn rate, scroll speed | `Game.update` and `Game.scroll_speed` in `game.py` |
| Weapon fire patterns | `Player.fire` and `Player.blaster_shots` in `player.py`; the laser in `Game.update_laser` |
| Boss strength and fire rate | `Boss.__init__` and `Boss.update` in `boss.py` |
| How far ahead enemies look | `LOOKAHEAD`, `PLAN_HORIZON`, `MARGIN` in `ai.py` |
| Sounds | `build_sound_samples` in `sound.py` |

### Adding a new enemy type

1. Add an entry to `ENEMY_TYPES` in `config.py`.
2. Draw its sprite: add a `draw_<kind>_sprite` function in `sprites.py` and register it in `load_sprites`.
3. Give it a fire pattern in `Enemy.try_fire` (`enemies.py`).
4. Add it to the weights in `pick_enemy_kind`, and to the explosion size, colour and drop chance in
   `Game.destroy_enemy`.
5. Add tests to `tests/test_enemies.py`.

### Adding a new barrier

Barriers other than walls are "hazards". A hazard class needs:

- `update(dt, game)` and `draw(surface)`
- `touches(rect)`: does it hurt something with this hitbox?
- `blocks(rect)`: does it stop a shot?
- `laser_stop(x, half_width, top)`: where it stops a laser beam, or `None`
- `alive`, `y`, `speed` and `damage` attributes

Then add it to the `Hazard` type in `obstacles.py`, spawn it in `Game.spawn_barrier`, and teach enemies to avoid
it in `ai.py` (see `_dodge_target`).

### Adding a sound

Add an entry to `build_sound_samples` in `sound.py`, built from `tone`, `noise`, `silence`, `mix`, `concat` and
`notes`, with a volume. Play it with `game.sfx.play("name")`.

## Conventions

- Every function has type hints; the code passes `mypy --strict`.
- Read the playfield width as `config.WIDTH`, never `from .config import WIDTH`: the width changes when the
  window is resized, and an imported copy would go stale.
- Don't use `Game` at runtime from entity modules: import it only for type hints, under `TYPE_CHECKING`, to keep
  imports free of cycles.
- Code that only matters in the browser checks `config.IS_WEB`. Run `scripts/check_web.py` after changing
  anything in startup, input, sound or file handling.
