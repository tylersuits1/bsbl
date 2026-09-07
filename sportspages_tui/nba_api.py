"""Live NBA data from ESPN's public basketball/nba API — no API key
required. Thin sport-specific layer over espn_period_sport's shared
parsing. Two things differ from football: leader categories are
points/rebounds/assists rather than passing/rushing/receiving, and
standings entries carry raw win/loss/games-behind numbers rather than a
pre-formatted record string.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from . import espn_period_sport as common
from . import nba_teams
from .models import GameStatus, Headline
from .period_models import PeriodBoxScore, PeriodTeamSide

NBA_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

_LEADER_LABELS = {"points": "PTS", "rebounds": "REB", "assists": "AST"}


class NbaStatsError(common.PeriodStatsError):
    pass


class NbaStatsService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=12.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_game_for_team(self, team: nba_teams.NbaTeamInfo) -> PeriodBoxScore:
        schedule = await common.get_json(self._client, f"{NBA_BASE}/teams/{team.espn_id}/schedule", NbaStatsError)
        events = schedule.get("events") or []
        nearest = common.nearest_event(events)
        if nearest is None:
            return self._no_schedule(team)

        summary = await common.get_json(self._client, f"{NBA_BASE}/summary?event={nearest['id']}", NbaStatsError)
        return self._parse_summary(summary, followed_team=team, schedule_events=events)

    def _parse_summary(self, data: dict, *, followed_team: nba_teams.NbaTeamInfo, schedule_events: list[dict]) -> PeriodBoxScore:
        header = data["header"]
        competition = header["competitions"][0]
        competitors = competition["competitors"]
        away_c = next(c for c in competitors if c["homeAway"] == "away")
        home_c = next(c for c in competitors if c["homeAway"] == "home")

        status_type = competition["status"]["type"]
        status = common.map_status(status_type.get("name", ""))
        status_detail = status_type.get("shortDetail", "")

        away = common.build_side(away_c)
        home = common.build_side(home_c)

        # No 'weather' key in NBA's gameInfo (indoor sport) — venue only.
        venue, weather = common.parse_venue_weather(data.get("gameInfo") or {})

        scheduled_start = None
        if status == GameStatus.SCHEDULED:
            date_str = competition.get("date")
            if date_str:
                scheduled_start = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

        followed_is_home = common.parse_int((home_c["team"] or {}).get("id")) == followed_team.espn_id
        followed_team_record = home.record if followed_is_home else away.record

        leaders_by_team_id = common.parse_leaders(data, _LEADER_LABELS)
        away_id = common.parse_int((away_c["team"] or {}).get("id"))
        home_id = common.parse_int((home_c["team"] or {}).get("id"))

        standings = common.parse_standings_from_wins_losses(data, followed_espn_id=followed_team.espn_id)

        next_game = None
        if status == GameStatus.FINAL:
            current_date_str = competition.get("date")
            if current_date_str:
                current_date = datetime.fromisoformat(current_date_str.replace("Z", "+00:00"))
                next_game = common.parse_next_game(schedule_events, current_date=current_date, followed_espn_id=followed_team.espn_id)

        money_line = common.followed_money_line(data.get("pickcenter") or [], followed_is_home=followed_is_home)

        return PeriodBoxScore(
            home=home, away=away,
            away_periods=common.build_periods(away_c), home_periods=common.build_periods(home_c),
            status=status, status_detail=status_detail,
            venue=venue, weather=weather, scheduled_start=scheduled_start,
            next_game=next_game, followed_team_record=followed_team_record,
            away_leaders=leaders_by_team_id.get(away_id, []) if away_id is not None else [],
            home_leaders=leaders_by_team_id.get(home_id, []) if home_id is not None else [],
            standings=standings, money_line=money_line,
        )

    def _no_schedule(self, team: nba_teams.NbaTeamInfo) -> PeriodBoxScore:
        return PeriodBoxScore(
            away=PeriodTeamSide(city=team.city, name=team.name, abbreviation=team.abbreviation, score=0),
            home=PeriodTeamSide(city="", name="TBD", abbreviation="", score=0),
            away_periods=[], home_periods=[],
            status=GameStatus.SCHEDULED, status_detail="No schedule found",
            venue="", weather="",
        )


class NbaNewsService:
    """NBA headlines from ESPN's public (unofficial) news endpoint —
    the same feed style already used for MLB/NCAAF/NFL.
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=12.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_headlines(self) -> list[Headline]:
        return await common.fetch_espn_headlines(self._client, f"{NBA_BASE}/news?limit=12", NbaStatsError)
