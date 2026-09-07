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


def load_favorites() -> list[tuple[str, str]]:
    """Returns (sport, abbreviation) pairs, sport one of "MLB"/"NCAAF".
    Favorites files written before NCAAF existed stored bare MLB
    abbreviations (e.g. "ATL") — those are read back as ("MLB", "ATL").
    """
    if not FAVORITES_FILE.exists():
        return []
    try:
        data = json.loads(FAVORITES_FILE.read_text())
        raw = data.get("teams", data.get("abbreviations", []))
    except (json.JSONDecodeError, OSError):
        return []

    result = []
    for entry in raw:
        entry = str(entry)
        if ":" in entry:
            sport, abbr = entry.split(":", 1)
        else:
            sport, abbr = "MLB", entry
        result.append((sport, abbr))
    return result


def save_favorites(entries: list[tuple[str, str]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    raw = [f"{sport}:{abbr}" for sport, abbr in entries]
    FAVORITES_FILE.write_text(json.dumps({"teams": raw}, indent=2))


def toggle_favorite(sport: str, abbreviation: str) -> tuple[list[tuple[str, str]], bool]:
    """Returns (updated list, applied). Fails (applied=False) if adding
    would exceed MAX_FAVORITES.
    """
    current = load_favorites()
    key = (sport, abbreviation)
    if key in current:
        current.remove(key)
        save_favorites(current)
        return current, True
    if len(current) >= MAX_FAVORITES:
        return current, False
    current.append(key)
    save_favorites(current)
    return current, True
