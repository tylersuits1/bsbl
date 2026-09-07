"""Favorite-team (and fantasy-player) persistence. Unlike the Flutter
app (favorites are in-memory only, lost on restart), the TUI writes to a
small JSON file so what you're following survives between sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "sportspages-tui"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"

MAX_FAVORITES = 8
MAX_FANTASY_PLAYERS = 15


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
    """Returns (sport, abbreviation) pairs, sport one of
    "MLB"/"NCAAF"/"NFL"/"NBA". Favorites files written before NCAAF
    existed stored bare MLB abbreviations (e.g. "ATL") — those are read
    back as ("MLB", "ATL").
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


def load_fantasy_players() -> list[dict]:
    """Each entry: {"espn_id": int, "name": str, "position": str,
    "team_abbr": str, "team_name": str}.
    """
    return _read_data().get("fantasy_players", [])


def save_fantasy_players(players: list[dict]) -> None:
    data = _read_data()
    data["fantasy_players"] = players
    _write_data(data)


def is_fantasy_player_followed(espn_id: int) -> bool:
    return any(p.get("espn_id") == espn_id for p in load_fantasy_players())


def toggle_fantasy_player(player: dict) -> tuple[list[dict], bool]:
    """`player` must include "espn_id". Returns (updated list, applied)
    — applied=False if adding would exceed MAX_FANTASY_PLAYERS.
    """
    current = load_fantasy_players()
    existing_index = next((i for i, p in enumerate(current) if p.get("espn_id") == player.get("espn_id")), None)
    if existing_index is not None:
        current.pop(existing_index)
        save_fantasy_players(current)
        return current, True
    if len(current) >= MAX_FANTASY_PLAYERS:
        return current, False
    current.append(player)
    save_fantasy_players(current)
    return current, True
