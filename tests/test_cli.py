from __future__ import annotations

from nova_strike import config as cfg
from nova_strike.cli import parse_args


def test_defaults() -> None:
    args = parse_args([])
    assert args.lives == cfg.DEFAULT_LIVES
    assert args.level == 1
    assert args.boss_level == cfg.BOSS_LEVEL
    assert not args.mute


def test_options() -> None:
    args = parse_args(["--lives", "5", "--mute", "--level", "20", "--boss-level", "2"])
    assert (args.lives, args.mute, args.level, args.boss_level) == (5, True, 20, 2)
