# How to play

You pilot a ship at the bottom of the screen while the starfield scrolls past. Shoot enemies for points, avoid
their fire and the barriers drifting down towards you, and collect power-ups along the way.

## Health and lives

- Your ship has 100 health, shown by the bar at the top left.
- Every hit takes some health away (see [Damage](#damage)). At zero you lose a life, then respawn with full health
  and 2.5 seconds of protection.
- After any hit you are protected for 0.6 seconds, so one collision can't drain you all at once.
- You start with 3 lives (change this on the title screen or with `--lives`). Lives are shown as ship icons at
  the top right.
- You gain an extra life every 1,000 points, up to 9.

## Levels

You go up a level every 300 points. Each level makes the game harder:

- enemies arrive more often, move faster and have slightly more health;
- the screen scrolls faster;
- barrier gaps get narrower and new barrier types appear more often.

Every 20 levels a [mothership boss](#the-mothership-boss) arrives.

## Enemies

| Enemy | Health | Points | Weapon | Damage per shot | Damage if you ram it |
|---|---|---|---|---|---|
| Scout (red, fast) | 1 | 15 | Single shot straight down | 8 | 20 |
| Fighter (purple) | 3 | 30 | Twin shots aimed at you | 12 | 35 |
| Heavy (orange, armoured) | 9 | 80 | Five-way spread | 18 | 60 |

Enemy health rises slowly with the level. Heavies first appear at level 3, and only a few can be on screen at
once, so they never form an impassable wall.

Enemies also obey the barriers. They try to fly around them: steering for wall gaps, timing laser gates and
sidestepping asteroids, mines and spinners. If they crash into one anyway, they take the same share of damage
you would, and an enemy wrecked by a barrier gives you no points.

## Barriers

Barriers scroll down the screen. They don't stop your ship, but touching them hurts.

| Barrier | How to get past | Damage |
|---|---|---|
| Girder wall | Fly through a gap. Later levels can have two gaps. | 30 |
| Sliding wall | Its single gap slides from side to side. Arrows in the gap show which way. | 30 |
| Laser gate | A beam across the whole screen. The post lights show green (off), yellow (about to fire) and red (on). Cross while it's off. | 25 |
| Mine field | Spiked mines that chase you once you get close. Shoot them from a distance: the blast destroys nearby enemies and sets off other mines. | 35 (blast) |
| Spinner | Rotating arms around a hub. Slip past between sweeps. | 30 |
| Asteroid | Shoot it (large ones split in two) or dodge it. | 20 small, 40 large |

The first time each new barrier type appears, a yellow WARNING message tells you what's coming.

Walls, active laser gates, spinners and asteroids also stop shots, yours and the enemies', so you can use them
as cover.

## Weapons

Weapons live in the tray along the bottom of the screen. The blaster is always available. Other weapons come
from pickups and are kept until their ammo runs out, then you switch back to the blaster.

| Weapon | What it does | Ammo per pickup |
|---|---|---|
| Blaster | Twin cannon. More angled shots at levels 2 and 3. | Unlimited |
| Spread | A fan of 3, 5 or 7 shots. | 60 volleys |
| Laser | A continuous beam that passes through enemies but stops at barriers. Wider and stronger at higher levels. | 6 seconds |
| Missiles | Homing missiles. Level 2 adds the twin blaster; level 3 fires four at a time. | 40 missiles |
| Nuke | Destroys everything on screen. See below. | 1 bomb |

- Collecting a weapon you don't have adds it and selects it.
- Collecting one you already have raises its level (up to 3) and adds ammo, up to three pickups' worth. It
  doesn't switch you to it.
- Losing a life lowers the level of the weapon you were holding by one.
- Each tray slot shows the weapon's key number, level, ammo bar and remaining ammo. The bar flashes red when
  ammo is low.

### The nuke

Nukes are very rare: about 1 pickup in 100, and the boss always drops one. You can hold up to 3.

Collecting a nuke never selects it automatically. Select it with **5** (or the weapon keys), then press Space.
It only fires on a fresh press, so holding fire while switching weapons won't waste one.

A nuke destroys every enemy, asteroid, mine, barrier and enemy shot that is on screen, and you get the points.
Anything that hasn't scrolled into view yet survives. Against the boss it destroys all the turrets and a third
of the core's health.

## Power-ups

Power-ups drift down the screen every 8 to 13 seconds, and destroyed enemies sometimes drop them (heavies most
often). Fly into one to collect it.

| Power-up | Looks like | Effect |
|---|---|---|
| Weapons | Hexagon showing the weapon | See [Weapons](#weapons). |
| Repair | White medkit with a red cross | Restores 35 health, or gives 50 points at full health. |
| Invincibility | Spinning gold star | 8 seconds of invincibility: shots bounce off, ramming destroys enemies and asteroids for full points, and barriers can't hurt you. Your ship flickers when it's about to wear off. |
| Slow-mo | Purple clock with an hourglass | Adds a slow-motion charge (up to 3). |

### Slow motion

You start each game with one slow-motion charge. Press Shift to use one: for 4 seconds everything else moves at
30% speed while your ship and shots stay at full speed. The screen turns purple and a timer bar runs under your
health. Charges are shown as hourglasses next to the health bar.

## The mothership boss

At level 20, and every 20 levels after, normal enemies and barriers stop arriving, a siren sounds and a
mothership enters from the top.

1. **Destroy the four missile turrets.** They track you and fire homing missiles (20 damage each). Missiles home
   for 3 seconds and then fly straight, so you can dodge them, and you can shoot them down for 10 points each.
   Each turret is worth 300 points. The reactor core is shielded while any turret survives.
2. **Destroy the core.** With the turrets gone, the core is exposed, the ship moves faster, and the core fires
   fans of bullets.
3. **Collect the reward:** a bonus of 5,000 points (10,000 for the second boss, and so on), plus repair,
   invincibility, slow-mo, a weapon and a nuke.

Your shots pass over the boss's hull, so only the turrets and core can be hit. Flying into the hull costs 40
health. Each return of the boss is tougher. Beating it advances you exactly one level.

To practise the fight, run `python main.py --level 20`.

## Damage

| Source | Damage |
|---|---|
| Scout / fighter / heavy shot | 8 / 12 / 18 |
| Ramming a scout / fighter / heavy | 20 / 35 / 60 |
| Girder or sliding wall | 30 |
| Laser gate (on) | 25 |
| Spinner | 30 |
| Mine blast | 35 |
| Small / large asteroid | 20 / 40 |
| Boss missile | 20 |
| Boss core bullet | 14 |
| Boss hull | 40 |

## Scoring

| Action | Points |
|---|---|
| Scout / fighter / heavy | 15 / 30 / 80 |
| Small / large asteroid | 10 / 20 |
| Mine | 25 |
| Boss missile shot down | 10 |
| Boss turret | 300 |
| Boss destroyed | 5,000 × boss number |
| Repair or slow-mo collected when already full | 50 |

## High score table

If your final score makes the top 10, you enter your initials arcade-style:

- Up/Down changes the letter, Left/Right moves between letters, or just type them.
- Space moves to the next letter, and confirms on the last one. Enter confirms straight away.

The table appears on the game-over screen with your entry flashing, and alternates with the game information on
the title screen.
