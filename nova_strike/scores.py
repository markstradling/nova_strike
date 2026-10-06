"""The persistent high score table."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, cast

from . import config as cfg
from .config import CYAN, DEFAULT_SCORES, SCOREBOARD_SIZE

if TYPE_CHECKING:
    from .config import ScoreEntry


WEB_STORAGE_KEY = "nova_strike.highscores"


class WebStorage(Protocol):
    """The parts of the browser's localStorage the score table uses."""

    def getItem(self, key: str, /) -> str | None: ...  # noqa: N802 - the browser API's names
    def setItem(self, key: str, value: str, /) -> None: ...  # noqa: N802


def browser_storage() -> WebStorage | None:
    """The page's localStorage when running in a browser, else None.

    A web page can't write files that survive a reload, so in the browser the table lives in
    localStorage instead. pygbag replaces the `platform` module with one exposing the page's window.
    """
    if not cfg.IS_WEB:
        return None
    import platform  # noqa: PLC0415 - only meaningful in the browser

    return cast("WebStorage | None", getattr(getattr(platform, "window", None), "localStorage", None))


def load_scores(path: str | None = None) -> list[ScoreEntry]:
    """Load the table from `path` (default: config.SCORES_FILE, or browser storage on the web),
    falling back to the default table if there is none or it can't be read."""
    try:
        storage = browser_storage() if path is None else None
        if storage is not None:
            text = storage.getItem(WEB_STORAGE_KEY)
            if not text:
                return list(DEFAULT_SCORES)
        else:
            with open(path or cfg.SCORES_FILE) as f:
                text = f.read()
        entries = [(str(e["name"])[:3].upper(), int(e["score"])) for e in json.loads(text)]
        return sorted(entries, key=lambda e: -e[1])[:SCOREBOARD_SIZE]
    except (OSError, ValueError, KeyError, TypeError):
        return list(DEFAULT_SCORES)


def save_scores(entries: Sequence[ScoreEntry], path: str | None = None) -> None:
    text = json.dumps([{"name": n, "score": sc} for n, sc in entries], indent=2)
    storage = browser_storage() if path is None else None
    try:
        if storage is not None:
            storage.setItem(WEB_STORAGE_KEY, text)
        else:
            with open(path or cfg.SCORES_FILE, "w") as f:
                f.write(text)
    except OSError:
        pass


def qualifies(entries: Sequence[ScoreEntry], score: int) -> bool:
    return score > 0 and (len(entries) < SCOREBOARD_SIZE or score > entries[-1][1])


def ordinal(n: int) -> str:
    suffix = "TH" if 10 <= n % 100 <= 20 else {1: "ST", 2: "ND", 3: "RD"}.get(n % 10, "TH")
    return f"{n}{suffix}"


RANK_COLORS = [
    (255, 220, 80),
    (230, 230, 240),
    (230, 160, 90),
    CYAN,
    (120, 255, 190),
    (255, 120, 200),
    (170, 140, 255),
    (255, 160, 60),
    (140, 200, 255),
    (200, 200, 215),
]
