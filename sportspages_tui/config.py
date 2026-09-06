"""Favorite-team persistence. Unlike the Flutter app (favorites are
in-memory only, lost on restart), the TUI writes to a small JSON file so
your followed teams survive between sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "sportspages-tui"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

MAX_FAVORITES = 8


def load_favorites() -> list[str]:
    if not FAVORITES_FILE.exists():
        return []
    try:
        data = json.loads(FAVORITES_FILE.read_text())
        return [str(a) for a in data.get("abbreviations", [])]
    except (json.JSONDecodeError, OSError):
        return []


def save_favorites(abbreviations: list[str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FAVORITES_FILE.write_text(json.dumps({"abbreviations": abbreviations}, indent=2))


def toggle_favorite(abbreviation: str) -> tuple[list[str], bool]:
    """Returns (updated list, applied). Fails (applied=False) if adding
    would exceed MAX_FAVORITES.
    """
    current = load_favorites()
    if abbreviation in current:
        current.remove(abbreviation)
        save_favorites(current)
        return current, True
    if len(current) >= MAX_FAVORITES:
        return current, False
    current.append(abbreviation)
    save_favorites(current)
    return current, True
