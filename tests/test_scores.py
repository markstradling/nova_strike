from __future__ import annotations

import json
from pathlib import Path

import pytest

from nova_strike import config as cfg
from nova_strike.scores import load_scores, ordinal, qualifies, save_scores


def test_missing_file_gives_default_table(isolated_scores: Path) -> None:
    assert not isolated_scores.exists()
    assert load_scores() == cfg.DEFAULT_SCORES


def test_save_and_load_round_trip(isolated_scores: Path) -> None:
    table = [("AAA", 900), ("BBB", 500)]
    save_scores(table)
    assert json.loads(isolated_scores.read_text())[0] == {"name": "AAA", "score": 900}
    assert load_scores() == table


def test_load_sorts_truncates_and_cleans(tmp_path: Path) -> None:
    path = tmp_path / "scores.json"
    entries = [{"name": f"p{i}xx", "score": i * 10} for i in range(15)]
    path.write_text(json.dumps(entries))
    table = load_scores(str(path))
    assert len(table) == cfg.SCOREBOARD_SIZE
    assert table[0] == ("P14", 140)  # highest first, initials upper-cased and cut to 3
    assert [s for _, s in table] == sorted((s for _, s in table), reverse=True)


@pytest.mark.parametrize("content", ["not json", '{"a": 1}', '[{"name": "X"}]'])
def test_corrupt_file_falls_back_to_defaults(tmp_path: Path, content: str) -> None:
    path = tmp_path / "scores.json"
    path.write_text(content)
    assert load_scores(str(path)) == cfg.DEFAULT_SCORES


def test_qualifies() -> None:
    full = [("X", 100 - i) for i in range(cfg.SCOREBOARD_SIZE)]  # lowest entry is 91
    assert qualifies(full, 92)
    assert not qualifies(full, 91)  # a tie with the lowest doesn't knock it off
    assert qualifies(full[:3], 1)  # a table with room accepts any positive score
    assert not qualifies([], 0)


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1ST"),
        (2, "2ND"),
        (3, "3RD"),
        (4, "4TH"),
        (10, "10TH"),
        (11, "11TH"),
        (12, "12TH"),
        (13, "13TH"),
        (21, "21ST"),
        (22, "22ND"),
        (101, "101ST"),
        (111, "111TH"),
    ],
)
def test_ordinal(n: int, expected: str) -> None:
    assert ordinal(n) == expected
