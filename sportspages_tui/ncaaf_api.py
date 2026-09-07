"""Live NCAAF (FBS) data from ESPN's public college football API — no
API key required. Ports the same logic as the sibling Flutter app's
NcaafStatsService/NcaafNewsService, so behavior stays consistent across
both clients.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from . import ncaaf_teams
from .models import GameStatus, Headline, NextGameInfo
from .ncaaf_models import NcaafBoxScore, NcaafGameLeader, NcaafStandingEntry, NcaafTeamSide

NCAAF_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"


class NcaafStatsError(Exception):
    pass


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _leader_label(stat_name: str) -> str:
    return {"passingYards": "QB", "rushingYards": "RB", "receivingYards": "WR"}.get(stat_name, stat_name)


def _map_status(status_name: str) -> GameStatus:
    if status_name == "STATUS_FINAL":
        return GameStatus.FINAL
    if status_name in ("STATUS_POSTPONED", "STATUS_CANCELED"):
        return GameStatus.POSTPONED
    if status_name in ("STATUS_DELAYED", "STATUS_RAIN_DELAY"):
        return GameStatus.DELAYED
    if status_name == "STATUS_SCHEDULED":
        return GameStatus.SCHEDULED
    return GameStatus.LIVE


class NcaafStatsService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=12.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get_json(self, url: str) -> dict:
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as e:
            raise NcaafStatsError(f"Could not reach {url}: {e}") from e
        if response.status_code != 200:
            raise NcaafStatsError(f"{url} returned {response.status_code}")
        return response.json()

    async def fetch_game_for_team(self, team: ncaaf_teams.NcaafTeamInfo) -> NcaafBoxScore:
        """Football is weekly, not daily, so "the current game" is
        whichever scheduled event is nearest right now in either
        direction — the just-played or about-to-be-played game.
        """
        schedule = await self._get_json(f"{NCAAF_BASE}/teams/{team.espn_id}/schedule")
        events = schedule.get("events") or []
        if not events:
            return self._no_schedule(team)

        now = datetime.now(timezone.utc)
        nearest = None
        best_diff = None
        for event in events:
            date_str = event.get("date")
            if not date_str:
                continue
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            diff = abs(dt - now)
            if best_diff is None or diff < best_diff:
                best_diff, nearest = diff, event
        if nearest is None:
            return self._no_schedule(team)

        event_id = nearest["id"]
        rankings = await self._fetch_ap_rankings()
        summary = await self._get_json(f"{NCAAF_BASE}/summary?event={event_id}")
        return self._parse_summary(summary, followed_team=team, rankings=rankings, schedule_events=events)

    def _parse_summary(
        self,
        data: dict,
        *,
        followed_team: ncaaf_teams.NcaafTeamInfo,
        rankings: dict[int, int],
        schedule_events: list[dict],
    ) -> NcaafBoxScore:
        header = data["header"]
        competition = header["competitions"][0]
        competitors = competition["competitors"]
        away_c = next(c for c in competitors if c["homeAway"] == "away")
        home_c = next(c for c in competitors if c["homeAway"] == "home")

        status_type = competition["status"]["type"]
        status = _map_status(status_type.get("name", ""))
        status_detail = status_type.get("shortDetail", "")

        def build_side(c: dict) -> NcaafTeamSide:
            team_data = c["team"]
            espn_id = _parse_int(team_data.get("id"))
            records = c.get("record") or []
            overall = next((r for r in records if r.get("type") == "total"), None)
            return NcaafTeamSide(
                city=team_data.get("location", ""),
                name=team_data.get("name", ""),
                abbreviation=team_data.get("abbreviation", ""),
                score=_safe_int(c.get("score")),
                record=(overall or {}).get("displayValue", ""),
                ap_rank=rankings.get(espn_id) if espn_id is not None else None,
            )

        def build_quarters(c: dict) -> list[str | None]:
            return [q.get("displayValue") for q in (c.get("linescores") or [])]

        away = build_side(away_c)
        home = build_side(home_c)

        game_info = data.get("gameInfo") or {}
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

        scheduled_start = None
        if status == GameStatus.SCHEDULED:
            date_str = competition.get("date")
            if date_str:
                scheduled_start = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

        followed_is_home = _parse_int((home_c["team"] or {}).get("id")) == followed_team.espn_id
        followed_team_record = home.record if followed_is_home else away.record

        leaders_by_team_id: dict[int, list[NcaafGameLeader]] = {}
        for entry in data.get("leaders") or []:
            team_id = _parse_int((entry.get("team") or {}).get("id"))
            if team_id is None:
                continue
            leaders = []
            for cat in entry.get("leaders") or []:
                name = cat.get("name")
                if name not in ("passingYards", "rushingYards", "receivingYards"):
                    continue
                cat_leaders = cat.get("leaders") or []
                if not cat_leaders:
                    continue
                top = cat_leaders[0]
                athlete = top.get("athlete") or {}
                leaders.append(NcaafGameLeader(
                    category=_leader_label(name),
                    player_name=athlete.get("displayName", "Unknown"),
                    position=(athlete.get("position") or {}).get("abbreviation", ""),
                    stat_line=top.get("displayValue", ""),
                ))
            leaders_by_team_id[team_id] = leaders
        away_id = _parse_int((away_c["team"] or {}).get("id"))
        home_id = _parse_int((home_c["team"] or {}).get("id"))

        standings: list[NcaafStandingEntry] = []
        standings_data = data.get("standings") or {}
        groups = standings_data.get("groups") or []
        if groups:
            # Cross-conference matchups (e.g. an FBS team hosting an FCS
            # opponent) return one standings group per side — pick
            # whichever one actually contains the followed team, rather
            # than assuming the first group is theirs.
            followed_group = next(
                (
                    g for g in groups
                    if any(
                        e.get("id") == str(followed_team.espn_id)
                        for e in ((g.get("standings") or {}).get("entries") or [])
                    )
                ),
                groups[0],
            )
            entries = (followed_group.get("standings") or {}).get("entries") or []
            for entry in entries:
                stats = entry.get("stats") or []
                overall = next((s for s in stats if s.get("type") == "total"), None)
                conf = next((s for s in stats if s.get("type") == "vsconf"), None)
                standings.append(NcaafStandingEntry(
                    team_name=entry.get("team", ""),
                    overall_record=(overall or {}).get("displayValue", ""),
                    conference_record=(conf or {}).get("displayValue", ""),
                ))
            standings.sort(key=lambda e: (-e.conference_wins, e.conference_losses))

        next_game = None
        if status == GameStatus.FINAL:
            current_date_str = competition.get("date")
            if current_date_str:
                current_date = datetime.fromisoformat(current_date_str.replace("Z", "+00:00"))
                next_event = None
                next_event_date = None
                for event in schedule_events:
                    date_str = event.get("date")
                    if not date_str:
                        continue
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if dt > current_date and (next_event_date is None or dt < next_event_date):
                        next_event, next_event_date = event, dt
                if next_event:
                    comps = next_event["competitions"][0]
                    next_competitors = comps["competitors"]
                    opponent = next(
                        (c for c in next_competitors if _parse_int((c["team"] or {}).get("id")) != followed_team.espn_id),
                        next_competitors[0],
                    )
                    opponent_team = opponent["team"]
                    next_game = NextGameInfo(
                        opponent=opponent_team.get("location", "TBD"),
                        venue="",
                        start=datetime.fromisoformat(next_event["date"].replace("Z", "+00:00")),
                        is_away=opponent.get("homeAway") == "home",
                    )

        money_line = self._followed_money_line(data.get("pickcenter") or [], followed_is_home=followed_is_home)

        return NcaafBoxScore(
            home=home, away=away,
            away_quarters=build_quarters(away_c), home_quarters=build_quarters(home_c),
            status=status, status_detail=status_detail,
            venue=venue, weather=weather, scheduled_start=scheduled_start,
            next_game=next_game, followed_team_record=followed_team_record,
            away_leaders=leaders_by_team_id.get(away_id, []) if away_id is not None else [],
            home_leaders=leaders_by_team_id.get(home_id, []) if home_id is not None else [],
            division_standings=standings, money_line=money_line,
        )

    def _followed_money_line(self, pickcenter: list, *, followed_is_home: bool) -> str:
        """Straight from the same summary response already fetched for
        leaders/standings/quarters — no extra call needed, unlike MLB
        (whose stats API and ESPN don't share event ids).
        """
        if not pickcenter:
            return ""
        odds = pickcenter[0]
        side = odds.get("homeTeamOdds" if followed_is_home else "awayTeamOdds") or {}
        money_line = side.get("moneyLine")
        if money_line is None:
            return ""
        return f"+{money_line}" if isinstance(money_line, (int, float)) and money_line > 0 else str(money_line)

    async def _fetch_ap_rankings(self) -> dict[int, int]:
        try:
            data = await self._get_json(f"{NCAAF_BASE}/rankings")
            rankings_list = data.get("rankings") or []
            if not rankings_list:
                return {}
            ap_poll = next((r for r in rankings_list if r.get("type") == "ap"), rankings_list[0])
            result = {}
            for r in ap_poll.get("ranks") or []:
                current = r.get("current")
                team_id = _parse_int((r.get("team") or {}).get("id"))
                if current is not None and team_id is not None:
                    result[team_id] = current
            return result
        except Exception:
            return {}

    def _no_schedule(self, team: ncaaf_teams.NcaafTeamInfo) -> NcaafBoxScore:
        return NcaafBoxScore(
            away=NcaafTeamSide(city=team.city, name=team.name, abbreviation=team.abbreviation, score=0),
            home=NcaafTeamSide(city="", name="TBD", abbreviation="", score=0),
            away_quarters=[], home_quarters=[],
            status=GameStatus.SCHEDULED, status_detail="No schedule found",
            venue="", weather="",
        )


class NcaafNewsService:
    """College football headlines from ESPN's public (unofficial) news
    endpoint — the same feed style already used for MLB.
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=12.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_headlines(self) -> list[Headline]:
        try:
            response = await self._client.get(f"{NCAAF_BASE}/news?limit=12")
        except httpx.HTTPError as e:
            raise NcaafStatsError(f"Could not reach news source: {e}") from e
        if response.status_code != 200:
            raise NcaafStatsError(f"News source returned {response.status_code}")

        data = response.json()
        headlines = []
        for article in data.get("articles", []):
            published = article.get("published")
            published_at = (
                datetime.fromisoformat(published.replace("Z", "+00:00"))
                if published
                else datetime.now(timezone.utc)
            )
            web_link = (article.get("links") or {}).get("web", {})
            headlines.append(Headline(
                title=article.get("headline", "Untitled"),
                byline=article.get("byline") or "ESPN",
                time_ago=_time_ago(published_at),
                url=web_link.get("href", ""),
                published_at=published_at,
            ))
        return headlines


def _time_ago(published_at: datetime) -> str:
    diff = datetime.now(timezone.utc) - published_at.astimezone(timezone.utc)
    minutes = int(diff.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} mins ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hrs ago"
    return f"{hours // 24} days ago"
