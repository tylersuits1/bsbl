"""Favorite-team (and followed-player) persistence. Unlike the Flutter
app (favorites are in-memory only, lost on restart), the TUI writes to a
small JSON file so what you're following survives between sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "bsbl"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

MAX_FAVORITES = 8
MAX_PLAYERS = 15


def _read_data() -> dict:
    if not FAVORITES_FILE.exists():
        return {}
    try:
        return json.loads(FAVORITES_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_data(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FAVORITES_FILE.write_text(json.dumps(data, indent=2))


def load_favorites() -> list[tuple[str, str]]:
    """Returns (sport, abbreviation) pairs — sport is always "MLB" going
    forward, but the tag is kept on disk (and non-MLB entries from an
    older version are silently ignored on load) so an existing
    favorites.json doesn't need migrating.
    """
    data = _read_data()
    raw = data.get("teams", data.get("abbreviations", []))
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
    data = _read_data()
    data["teams"] = [f"{sport}:{abbr}" for sport, abbr in entries]
    data.pop("abbreviations", None)  # legacy key, superseded by "teams"
    _write_data(data)


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


def load_players() -> list[dict]:
    """Each entry: {"player_id": int, "name": str, "position": str,
    "team_abbr": str}.
    """
    return _read_data().get("players", [])


def save_players(players: list[dict]) -> None:
    data = _read_data()
    data["players"] = players
    _write_data(data)


def toggle_player(player: dict) -> tuple[list[dict], bool]:
    """`player` must include "player_id". Returns (updated list,
    applied) — applied=False if adding would exceed MAX_PLAYERS.
    """
    current = load_players()
    existing_index = next((i for i, p in enumerate(current) if p.get("player_id") == player.get("player_id")), None)
    if existing_index is not None:
        current.pop(existing_index)
        save_players(current)
        return current, True
    if len(current) >= MAX_PLAYERS:
        return current, False
    current.append(player)
    save_players(current)
    return current, True
