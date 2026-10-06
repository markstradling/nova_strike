# Nova Strike

A vertical-scrolling space shooter built with [pygame](https://www.pygame.org/). Fly up through waves of enemy
ships, dodge walls, laser gates, mines and spinners, collect weapons and power-ups, and take on a mothership boss
every 20 levels.

All graphics and sound are generated in code, so the game has no image or audio files. It runs as a desktop
game and also in a web browser.

## Quick start

You need Python 3.10 or newer.

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python main.py
```

On Windows, use `venv\Scripts\pip` and `venv\Scripts\python` instead.

To play in a browser instead, see [Playing in a web browser](docs/WEB.md).

## Controls

| Action | Keys |
|---|---|
| Move | Arrow keys or WASD |
| Fire | Space (hold) |
| Next weapon | Cmd (Mac) / Alt (Windows, Linux) |
| Previous weapon | Ctrl |
| Choose a weapon directly | 1 to 5 |
| Slow motion | Shift |
| Pause | P |
| Sound on/off | N |
| Fullscreen | F or F11 (desktop only) |
| Quit | Esc (in the browser, Esc pauses instead) |

The weapon keys sit beside the space bar, so you can switch weapons without letting go of fire.

On the title screen, Left/Right sets how many lives you start with. After a game, Space or M returns to the
menu and R plays again.

## Command-line options

```
python main.py [--lives N] [--mute] [--level N] [--boss-level N]
```

| Option | Effect |
|---|---|
| `--lives N` | Start with N lives (1 to 9, default 3). |
| `--mute` | Start with sound off. N turns it back on. |
| `--level N` | Start on level N. `--level 20` goes straight to the first boss. |
| `--boss-level N` | Meet the boss at level N, then every N levels (default 20). |

`--level` and `--boss-level` are for practice and testing: those runs show "PRACTICE" and are not added to the
high score table.

## Documentation

- [How to play](docs/GAMEPLAY.md): enemies, barriers, weapons, power-ups, the boss and scoring.
- [Playing in a web browser](docs/WEB.md): building, hosting and the differences from the desktop version.
- [Development guide](docs/DEVELOPMENT.md): setting up, running the checks and tests, and changing the game.
- [Architecture](docs/ARCHITECTURE.md): how the code is organised and how its main parts work.

## High scores

The top 10 scores are saved in `highscores.json` next to `main.py`. In the browser they are kept in the page's
local storage instead. Delete the file to reset the table.
