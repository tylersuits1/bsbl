"""Individual NFL player tracking for a lightweight fantasy view. This is
NOT tied to a real ESPN Fantasy league — that API
(fantasy.espn.com/apis/v3/games/ffl/...) needs a league id and, for
private leagues, SWID/espn_s2 auth cookies, none of which we have. So
"projected points" here is our own season-average-based estimate, not
ESPN's own projection model — labeled as such in the UI.

Scoring is a standard non-PPR formula (1 pt/10 rush or rec yards, 1
pt/25 pass yards, 6 pts/rush or rec TD, 4 pts/pass TD, -2/INT) computed
from ESPN's public per-player season stats — there's no per-league
scoring config to pull since we're not attached to a real league.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from . import espn_period_sport as common

SEARCH_URL = "https://site.api.espn.com/apis/search/v2"
ATHLETE_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes"

_SCORING = {
    "passingYards": 1 / 25,
    "passingTouchdowns": 4,
    "interceptions": -2,
    "rushingYards": 1 / 10,
    "rushingTouchdowns": 6,
    "receivingYards": 1 / 10,
    "receivingTouchdowns": 6,
}


class FantasyError(Exception):
    pass


@dataclass
class PlayerSearchResult:
    espn_id: int
    name: str
    team_name: str


@dataclass
class FantasyPlayer:
    espn_id: int
    name: str
    position: str
    team_abbr: str
    team_name: str


@dataclass
class FantasyPlayerStats:
    season_label: str = ""
    games_played: int = 0
    fantasy_points_total: float = 0.0
    fantasy_points_per_game: float = 0.0

    # Only meaningful (non-None) for players with real pass attempts /
    # rush carries this season — a receiver's completion_pct or a
    # quarterback's points_per_carry would otherwise show a misleading
    # 0 rather than "not applicable".
    completion_pct: float | None = None
    points_per_carry: float | None = None

    @property
    def projected_points(self) -> float:
        """Our own naive next-game estimate (season average) — NOT
        ESPN's own fantasy projection engine, which isn't reachable
        without a league.
        """
        return self.fantasy_points_per_game


def _safe_float(value) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


async def search_players(client: httpx.AsyncClient, query: str, limit: int = 8) -> list[PlayerSearchResult]:
    if not query.strip():
        return []
    try:
        response = await client.get(SEARCH_URL, params={"query": query, "limit": limit})
    except httpx.HTTPError as e:
        raise FantasyError(f"Could not reach player search: {e}") from e
    if response.status_code != 200:
        raise FantasyError(f"Player search returned {response.status_code}")

    data = response.json()
    results = []
    for group in data.get("results", []):
        if group.get("type") != "player":
            continue
        for item in group.get("contents", []):
            if item.get("defaultLeagueSlug") != "nfl":
                continue
            uid = item.get("uid", "")
            espn_id = common.parse_int(uid.rsplit("a:", 1)[-1]) if "a:" in uid else None
            if espn_id is None:
                continue
            results.append(PlayerSearchResult(
                espn_id=espn_id,
                name=item.get("displayName", "Unknown"),
                team_name=item.get("subtitle", ""),
            ))
    return results


async def fetch_player_profile(client: httpx.AsyncClient, espn_id: int) -> FantasyPlayer:
    data = await common.get_json(client, f"{ATHLETE_BASE}/{espn_id}", FantasyError)
    athlete = data.get("athlete", data)
    position = (athlete.get("position") or {}).get("abbreviation", "")
    team = athlete.get("team") or {}
    return FantasyPlayer(
        espn_id=espn_id,
        name=athlete.get("displayName", "Unknown"),
        position=position,
        team_abbr=team.get("abbreviation", ""),
        team_name=team.get("displayName", ""),
    )


async def fetch_player_stats(client: httpx.AsyncClient, espn_id: int) -> FantasyPlayerStats:
    data = await common.get_json(client, f"{ATHLETE_BASE}/{espn_id}/stats", FantasyError)
    categories = {c.get("name"): c for c in data.get("categories", [])}

    def latest_row(cat_name: str) -> tuple[dict, int, str]:
        cat = categories.get(cat_name)
        if not cat:
            return {}, 0, ""
        names = cat.get("names", [])
        for row in reversed(cat.get("statistics") or []):
            row_map = dict(zip(names, row.get("stats") or []))
            gp = common.safe_int(row_map.get("gamesPlayed", 0))
            if gp > 0:
                return row_map, gp, (row.get("season") or {}).get("displayName", "")
        return {}, 0, ""

    passing, pass_gp, pass_season = latest_row("passing")
    rushing, rush_gp, rush_season = latest_row("rushing")
    receiving, recv_gp, recv_season = latest_row("receiving")

    games_played = max(pass_gp, rush_gp, recv_gp)
    season_label = rush_season or recv_season or pass_season
    total_points = 0.0

    completion_pct = None
    if passing and _safe_float(passing.get("passingAttempts")) > 0:
        total_points += _safe_float(passing.get("passingYards")) * _SCORING["passingYards"]
        total_points += _safe_float(passing.get("passingTouchdowns")) * _SCORING["passingTouchdowns"]
        total_points += _safe_float(passing.get("interceptions")) * _SCORING["interceptions"]
        completion_pct = _safe_float(passing.get("completionPct"))

    points_per_carry = None
    if rushing:
        carries = _safe_float(rushing.get("rushingAttempts"))
        if carries > 0:
            rushing_points = (
                _safe_float(rushing.get("rushingYards")) * _SCORING["rushingYards"]
                + _safe_float(rushing.get("rushingTouchdowns")) * _SCORING["rushingTouchdowns"]
            )
            total_points += rushing_points
            points_per_carry = rushing_points / carries

    if receiving and _safe_float(receiving.get("receivingTargets")) > 0:
        total_points += _safe_float(receiving.get("receivingYards")) * _SCORING["receivingYards"]
        total_points += _safe_float(receiving.get("receivingTouchdowns")) * _SCORING["receivingTouchdowns"]

    points_per_game = total_points / games_played if games_played else 0.0

    return FantasyPlayerStats(
        season_label=season_label,
        games_played=games_played,
        fantasy_points_total=round(total_points, 1),
        fantasy_points_per_game=round(points_per_game, 1),
        completion_pct=completion_pct,
        points_per_carry=round(points_per_carry, 2) if points_per_carry is not None else None,
    )
