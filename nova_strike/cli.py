"""Command-line entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .config import BOSS_LEVEL, DEFAULT_LIVES, MAX_LIVES
from .game import Game


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nova Strike - vertical space shooter")
    parser.add_argument(
        "--lives", type=int, default=DEFAULT_LIVES, help=f"starting lives (1-{MAX_LIVES}, default {DEFAULT_LIVES})"
    )
    parser.add_argument("--mute", action="store_true", help="start with sound effects off (toggle in game with N)")
    parser.add_argument("--level", type=int, default=1, help="level to start on (e.g. 20 to go straight to the boss)")
    parser.add_argument(
        "--boss-level",
        type=int,
        default=BOSS_LEVEL,
        help=f"level of the first boss, which then returns every that many levels (default {BOSS_LEVEL})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    Game(lives=args.lives, sound=not args.mute, start_level=args.level, boss_level=args.boss_level).run()


async def main_async() -> None:
    """Browser entry point (pygbag): the page has no command line, so defaults are used."""
    await Game().run_async()
