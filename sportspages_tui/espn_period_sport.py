"""Shared parsing helpers for ESPN's `site.api.espn.com/apis/site/v2/sports/<sport>`
family of endpoints, which NCAAF, NFL, and NBA all share the same shape
of (schedule -> nearest event -> summary, with competitors/linescores/
leaders/standings/pickcenter sections that only differ in field names
and category labels). Each sport's *_api.py module is a thin wrapper
that supplies those sport-specific bits and calls these functions.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .models import GameStatus, Headline, NextGameInfo
from .period_models import GameLeader, PeriodTeamSide, StandingEntry


class PeriodStatsError(Exception):
    """Base class for the per-sport stats/news error types (NCAAF, NFL,
    NBA), so app.py can catch fetch failures across all of them with one
    except clause.
    """


async def get_json(client: httpx.AsyncClient, url: str, error_cls: type[Exception]) -> dict:
    try:
        response = await client.get(url)
    except httpx.HTTPError as e:
        raise error_cls(f"Could not reach {url}: {e}") from e
    if response.status_code != 200:
        raise error_cls(f"{url} returned {response.status_code}")
    return response.json()


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def map_status(status_name: str) -> GameStatus:
    if status_name == "STATUS_FINAL":
        return GameStatus.FINAL
    if status_name in ("STATUS_POSTPONED", "STATUS_CANCELED"):
        return GameStatus.POSTPONED
    if status_name in ("STATUS_DELAYED", "STATUS_RAIN_DELAY"):
        return GameStatus.DELAYED
    if status_name == "STATUS_SCHEDULED":
        return GameStatus.SCHEDULED
    return GameStatus.LIVE


def nearest_event(events: list[dict]) -> dict | None:
    """These sports play weekly (or a handful of times a week), not
    daily, so "the current game" is whichever scheduled event is
    nearest right now in either direction — the just-played or
    about-to-be-played game.
    """
    now = datetime.now(timezone.utc)
    nearest, best_diff = None, None
    for event in events:
        date_str = event.get("date")
        if not date_str:
            continue
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        diff = abs(dt - now)
        if best_diff is None or diff < best_diff:
            best_diff, nearest = diff, event
    return nearest


def build_side(c: dict, *, rank_lookup: dict[int, int] | None = None) -> PeriodTeamSide:
    team_data = c["team"]
    espn_id = parse_int(team_data.get("id"))
    records = c.get("record") or []
    overall = next((r for r in records if r.get("type") == "total"), None)
    return PeriodTeamSide(
        city=team_data.get("location", ""),
        name=team_data.get("name", ""),
        abbreviation=team_data.get("abbreviation", ""),
        score=safe_int(c.get("score")),
        record=(overall or {}).get("displayValue", ""),
        rank=(rank_lookup or {}).get(espn_id) if espn_id is not None else None,
    )


def build_periods(c: dict) -> list[str | None]:
    return [q.get("displayValue") for q in (c.get("linescores") or [])]


def parse_venue_weather(game_info: dict) -> tuple[str, str]:
    venue = (game_info.get("venue") or {}).get("fullName", "")
    weather_data = game_info.get("weather")
    weather = ""
    if weather_data:
        parts = []
        if weather_data.get("conditionId") is not None:
            parts.append(weather_data.get("displayValue", ""))
        if weather_data.get("temperature") is not None:
            parts.append(f"{weather_data['temperature']}°F")
        weather = ", ".join(p for p in parts if p)
    return venue, weather


def parse_leaders(data: dict, category_labels: dict[str, str]) -> dict[int, list[GameLeader]]:
    leaders_by_team_id: dict[int, list[GameLeader]] = {}
    for entry in data.get("leaders") or []:
        team_id = parse_int((entry.get("team") or {}).get("id"))
        if team_id is None:
            continue
        leaders = []
        for cat in entry.get("leaders") or []:
            name = cat.get("name")
            if name not in category_labels:
                continue
            cat_leaders = cat.get("leaders") or []
            if not cat_leaders:
                continue
            top = cat_leaders[0]
            athlete = top.get("athlete") or {}
            leaders.append(GameLeader(
                category=category_labels[name],
                player_name=athlete.get("displayName", "Unknown"),
                position=(athlete.get("position") or {}).get("abbreviation", ""),
                stat_line=top.get("displayValue", ""),
            ))
        leaders_by_team_id[team_id] = leaders
    return leaders_by_team_id


def _select_group(groups: list[dict], followed_espn_id: int) -> dict:
    """Cross-conference/division matchups return one standings group per
    side — pick whichever one actually contains the followed team,
    rather than assuming the first group is theirs.
    """
    return next(
        (
            g for g in groups
            if any(
                e.get("id") == str(followed_espn_id)
                for e in ((g.get("standings") or {}).get("entries") or [])
            )
        ),
        groups[0],
    )


def _record_wins_losses(record: str) -> tuple[int, int]:
    parts = record.split("-")
    if len(parts) < 2:
        return (0, 0)
    wins = int(parts[0]) if parts[0].isdigit() else 0
    losses = int(parts[1]) if parts[1].isdigit() else 0
    return wins, losses


def parse_standings_from_total_record(
    data: dict, *, followed_espn_id: int, secondary_stat_type: str = "vsconf"
) -> list[StandingEntry]:
    """NCAAF/NFL shape: each entry already carries a pre-formatted
    'total' (and often a secondary, e.g. 'vsconf') record string. Sorts
    best-secondary-record-first when the secondary record is present.
    """
    groups = (data.get("standings") or {}).get("groups") or []
    if not groups:
        return []
    entries = (_select_group(groups, followed_espn_id).get("standings") or {}).get("entries") or []
    standings = []
    for entry in entries:
        stats = entry.get("stats") or []
        overall = next((s for s in stats if s.get("type") == "total"), None)
        secondary = next((s for s in stats if s.get("type") == secondary_stat_type), None)
        standings.append(StandingEntry(
            team_name=entry.get("team", ""),
            overall_record=(overall or {}).get("displayValue", ""),
            secondary_record=(secondary or {}).get("displayValue", ""),
        ))
    if any(s.secondary_record for s in standings):
        def sort_key(s: StandingEntry) -> tuple[int, int]:
            wins, losses = _record_wins_losses(s.secondary_record)
            return -wins, losses
        standings.sort(key=sort_key)
    return standings


def parse_standings_from_wins_losses(data: dict, *, followed_espn_id: int) -> list[StandingEntry]:
    """NBA shape: wins/losses/gamesbehind are separate numeric stats
    rather than a pre-formatted record string. Preserves the API's own
    order, which already comes back rank-sorted within a group.
    """
    groups = (data.get("standings") or {}).get("groups") or []
    if not groups:
        return []
    entries = (_select_group(groups, followed_espn_id).get("standings") or {}).get("entries") or []
    standings = []
    for entry in entries:
        stats = {s.get("type"): s for s in (entry.get("stats") or [])}
        wins = (stats.get("wins") or {}).get("displayValue", "0")
        losses = (stats.get("losses") or {}).get("displayValue", "0")
        gb = (stats.get("gamesbehind") or {}).get("displayValue", "")
        standings.append(StandingEntry(
            team_name=entry.get("team", ""),
            overall_record=f"{wins}-{losses}",
            secondary_record=gb,
        ))
    return standings


def parse_next_game(schedule_events: list[dict], *, current_date: datetime, followed_espn_id: int) -> NextGameInfo | None:
    next_event, next_event_date = None, None
    for event in schedule_events:
        date_str = event.get("date")
        if not date_str:
            continue
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt > current_date and (next_event_date is None or dt < next_event_date):
            next_event, next_event_date = event, dt
    if not next_event:
        return None
    comps = next_event["competitions"][0]
    next_competitors = comps["competitors"]
    opponent = next(
        (c for c in next_competitors if parse_int((c["team"] or {}).get("id")) != followed_espn_id),
        next_competitors[0],
    )
    opponent_team = opponent["team"]
    return NextGameInfo(
        opponent=opponent_team.get("location", "TBD"),
        venue="",
        start=datetime.fromisoformat(next_event["date"].replace("Z", "+00:00")),
        is_away=opponent.get("homeAway") == "home",
    )


def followed_money_line(pickcenter: list, *, followed_is_home: bool) -> str:
    """Straight from the same summary response already fetched for
    leaders/standings/periods — no extra call needed, unlike MLB (whose
    stats API and ESPN don't share event ids).
    """
    if not pickcenter:
        return ""
    odds = pickcenter[0]
    side = odds.get("homeTeamOdds" if followed_is_home else "awayTeamOdds") or {}
    money_line = side.get("moneyLine")
    if money_line is None:
        return ""
    return f"+{money_line}" if isinstance(money_line, (int, float)) and money_line > 0 else str(money_line)


def time_ago(published_at: datetime) -> str:
    diff = datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
    minutes = int(diff.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} mins ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hrs ago"
    return f"{hours // 24} days ago"


async def fetch_espn_headlines(client: httpx.AsyncClient, news_url: str, error_cls: type[Exception]) -> list[Headline]:
    data = await get_json(client, news_url, error_cls)
    headlines = []
    for article in data.get("articles", []):
        published = article.get("published")
        published_at = (
            datetime.fromisoformat(published.replace("Z", "+00:00")) if published else datetime.now(timezone.utc)
        )
        web_link = (article.get("links") or {}).get("web", {})
        headlines.append(Headline(
            title=article.get("headline", "Untitled"),
            byline=article.get("byline") or "ESPN",
            time_ago=time_ago(published_at),
            url=web_link.get("href", ""),
            published_at=published_at,
        ))
    return headlines
