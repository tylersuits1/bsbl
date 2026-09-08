"""Live MLB data from the public MLB Stats API (statsapi.mlb.com) — no
API key required. Ports the same logic (and the same "baseball day" 3am
PST rollover) as the sibling Flutter app's MlbStatsService, so behavior
stays consistent across both clients. Deliberately has no dependency on
ESPN's site — see news_sources.py for headlines instead, which are
plain public RSS feeds rather than an undocumented internal API.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

from . import mlb_teams
from .models import (
    BoxScore,
    GameStatus,
    Headline,
    LineScore,
    NextGameInfo,
    PlayerStat,
    TeamSide,
)

STATS_BASE = "https://statsapi.mlb.com/api/v1"
STATS_LIVE_BASE = "https://statsapi.mlb.com/api/v1.1"


class MlbStatsError(Exception):
    pass


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def current_baseball_date() -> date:
    """Stays on the previous calendar day until 3am PST, so today's game
    (and its final score) doesn't flip to a new day's game right after
    midnight — mirrors the Flutter app's identical rule. Uses a fixed
    UTC-8 offset (not DST-aware — close enough for a 3am cutoff).
    """
    pst = datetime.now(timezone.utc) - timedelta(hours=8)
    effective = pst - timedelta(days=1) if pst.hour < 3 else pst
    return effective.date()


def _map_status(detailed_state: str) -> GameStatus:
    s = detailed_state.lower()
    if "final" in s or "game over" in s:
        return GameStatus.FINAL
    if "postponed" in s or "cancel" in s:
        return GameStatus.POSTPONED
    if "delay" in s:
        return GameStatus.DELAYED
    if "warmup" in s or "pre-game" in s:
        return GameStatus.WARMUP
    if "scheduled" in s or "preview" in s:
        return GameStatus.SCHEDULED
    return GameStatus.LIVE


def _record_string(league_record: dict | None) -> str:
    if not league_record:
        return ""
    wins, losses = league_record.get("wins"), league_record.get("losses")
    if wins is None or losses is None:
        return ""
    return f"{wins}-{losses}"


def _last_name(full_name: str) -> str:
    parts = [p for p in full_name.strip().split(" ") if p]
    return parts[-1] if parts else full_name


class MlbStatsService:
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
            raise MlbStatsError(f"Could not reach {url}: {e}") from e
        if response.status_code != 200:
            raise MlbStatsError(f"{url} returned {response.status_code}")
        return response.json()

    async def fetch_game_for_team(self, team: mlb_teams.TeamInfo) -> BoxScore:
        today_json = await self._get_json(
            f"{STATS_BASE}/schedule?sportId=1&teamId={team.stats_api_id}"
            f"&date={_fmt_date(current_baseball_date())}"
        )
        games = self._games_from_schedule(today_json)
        if not games:
            return await self._build_no_game_today(team)

        game = games[0]
        game_pk = game["gamePk"]
        detailed_state = game.get("status", {}).get("detailedState", "")
        status = _map_status(detailed_state)
        series_game_number = game.get("seriesGameNumber")
        schedule_teams = game["teams"]
        away_record = _record_string(schedule_teams["away"].get("leagueRecord"))
        home_record = _record_string(schedule_teams["home"].get("leagueRecord"))

        live_json = await self._get_json(f"{STATS_LIVE_BASE}/game/{game_pk}/feed/live")
        return await self._parse_live_feed(
            live_json,
            followed_team=team,
            status=status,
            series_game_number=series_game_number,
            away_record=away_record,
            home_record=home_record,
        )

    async def fetch_player_stats(self, team: mlb_teams.TeamInfo) -> list[PlayerStat]:
        """Season batting (AVG/HR/RBI) or pitching (W-L/ERA/IP) for every
        player on the active roster.
        """
        url = (
            f"{STATS_BASE}/teams/{team.stats_api_id}/roster"
            "?rosterType=active&hydrate=person(stats(type=season,group=[hitting,pitching]))"
        )
        data = await self._get_json(url)
        roster = data.get("roster", [])

        stats: list[PlayerStat] = []
        for entry in roster:
            person = entry["person"]
            name = person.get("fullName", "Unknown")
            position = (person.get("primaryPosition") or {}).get("abbreviation", "")
            is_pitcher = position == "P"
            person_stats = person.get("stats", [])

            pitching_stat = hitting_stat = None
            for s in person_stats:
                group = (s.get("group") or {}).get("displayName")
                splits = s.get("splits", [])
                if not splits:
                    continue
                stat = splits[0].get("stat", {})
                if group == "pitching":
                    pitching_stat = stat
                elif group == "hitting":
                    hitting_stat = stat

            # Pitchers occasionally carry a placeholder hitting line (NL
            # pitchers batting) alongside real pitching stats — prefer
            # whichever matches the player's primary position.
            stat = (pitching_stat or hitting_stat) if is_pitcher else (hitting_stat or pitching_stat)
            stat_is_pitching = pitching_stat is not None if is_pitcher else (hitting_stat is None and pitching_stat is not None)

            if stat is None:
                stats.append(PlayerStat(name=name, position=position, is_pitcher=is_pitcher, has_stats=False))
            elif stat_is_pitching:
                stats.append(PlayerStat(
                    name=name, position=position, is_pitcher=True,
                    wins_losses=f"{stat.get('wins', 0)}-{stat.get('losses', 0)}",
                    era=stat.get("era", "-.--"),
                    innings_pitched=stat.get("inningsPitched", "0.0"),
                ))
            else:
                stats.append(PlayerStat(
                    name=name, position=position, is_pitcher=False,
                    avg=stat.get("avg", ".---"),
                    home_runs=stat.get("homeRuns", 0),
                    rbi=stat.get("rbi", 0),
                ))

        stats.sort(key=lambda p: p.name)
        return stats

    async def _parse_live_feed(
        self,
        live: dict,
        *,
        followed_team: mlb_teams.TeamInfo,
        status: GameStatus,
        series_game_number: int | None,
        away_record: str = "",
        home_record: str = "",
    ) -> BoxScore:
        game_data = live["gameData"]
        live_data = live["liveData"]
        linescore = live_data.get("linescore", {})
        boxscore = live_data.get("boxscore", {})
        box_teams = boxscore.get("teams", {})
        box_away = box_teams.get("away", {})
        box_home = box_teams.get("home", {})

        ls_teams = linescore.get("teams", {})
        away_line = self._line_score_from(ls_teams.get("away"))
        home_line = self._line_score_from(ls_teams.get("home"))

        away_innings: list[int | None] = []
        home_innings: list[int | None] = []
        for inning in linescore.get("innings", []):
            away_innings.append((inning.get("away") or {}).get("runs"))
            home_innings.append((inning.get("home") or {}).get("runs"))

        teams_data = game_data["teams"]
        away = self._build_team(teams_data["away"], box_away, away_line.runs, away_record)
        home = self._build_team(teams_data["home"], box_home, home_line.runs, home_record)

        venue_data = game_data.get("venue") or {}
        venue = venue_data.get("name", "")
        weather_data = game_data.get("weather") or {}
        weather_condition = weather_data.get("condition")
        weather = f"{weather_condition}, {weather_data.get('temp', '')}°F" if weather_condition else ""

        if status in (GameStatus.SCHEDULED, GameStatus.WARMUP):
            probable = game_data.get("probablePitchers", {})
            away_pitcher = (probable.get("away") or {}).get("fullName", "TBD")
            home_pitcher = (probable.get("home") or {}).get("fullName", "TBD")
            away_pitcher_ip = home_pitcher_ip = ""
        else:
            away_name, away_pitcher_ip = self._last_pitcher_line(box_away)
            home_name, home_pitcher_ip = self._last_pitcher_line(box_home)
            away_pitcher, home_pitcher = away_name, home_name

        scheduled_start = None
        if status in (GameStatus.SCHEDULED, GameStatus.WARMUP):
            dt_str = (game_data.get("datetime") or {}).get("dateTime")
            if dt_str:
                scheduled_start = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if not weather and scheduled_start and venue_data.get("id"):
                weather = await self._fetch_weather_forecast(venue_data["id"], scheduled_start)

        next_game = None
        if status == GameStatus.FINAL:
            next_game = await self._fetch_next_game(followed_team)

        away_id = teams_data["away"]["id"]
        followed_is_home = away_id != followed_team.stats_api_id
        followed_team_record = home_record if followed_is_home else away_record

        return BoxScore(
            home=home, away=away, home_line=home_line, away_line=away_line,
            away_innings=away_innings, home_innings=home_innings,
            inning_half=linescore.get("inningState", "Top"),
            inning=linescore.get("currentInning", 1),
            venue=venue, weather=weather,
            home_pitcher=home_pitcher, home_pitcher_ip=home_pitcher_ip,
            away_pitcher=away_pitcher, away_pitcher_ip=away_pitcher_ip,
            status=status, scheduled_start=scheduled_start, next_game=next_game,
            followed_team_record=followed_team_record,
        )

    def _line_score_from(self, totals: dict | None) -> LineScore:
        totals = totals or {}
        return LineScore(runs=totals.get("runs", 0), hits=totals.get("hits", 0), errors=totals.get("errors", 0))

    def _build_team(self, team_data: dict, box_team_data: dict, score: int, record: str) -> TeamSide:
        batting_order_ids = box_team_data.get("battingOrder", [])
        players = box_team_data.get("players", {})
        order = []
        for pid in batting_order_ids:
            player = players.get(f"ID{pid}")
            if not player:
                continue
            name = (player.get("person") or {}).get("fullName", "Unknown")
            pos = (player.get("position") or {}).get("abbreviation", "")
            order.append(f"{name} ({pos})" if pos else name)

        return TeamSide(
            name=team_data.get("teamName", ""),
            city=team_data.get("franchiseName") or team_data.get("shortName", ""),
            abbreviation=team_data.get("abbreviation", ""),
            score=score, record=record, batting_order=order,
        )

    def _last_pitcher_line(self, team_box: dict) -> tuple[str, str]:
        pitcher_ids = team_box.get("pitchers", [])
        if not pitcher_ids:
            return "TBD", ""
        players = team_box.get("players", {})
        player = players.get(f"ID{pitcher_ids[-1]}")
        if not player:
            return "TBD", ""
        name = (player.get("person") or {}).get("fullName", "TBD")
        pitching = (player.get("stats") or {}).get("pitching") or {}
        ip = pitching.get("inningsPitched")
        return name, (f"{ip} IP" if ip else "")

    async def _fetch_weather_forecast(self, venue_id: int, game_time: datetime) -> str:
        """MLB's own weather field only fills in close to first pitch, so
        for games further out this pulls a forecast for the venue via
        Open-Meteo (free, no key).
        """
        try:
            venue_json = await self._get_json(f"{STATS_BASE}/venues/{venue_id}?hydrate=location")
            venues = venue_json.get("venues") or []
            if not venues:
                return ""
            location = venues[0].get("location") or {}
            coords = location.get("defaultCoordinates")
            if not coords:
                return ""
            lat, lon = coords["latitude"], coords["longitude"]
            forecast = await self._get_json(
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                "&hourly=temperature_2m,weathercode&temperature_unit=fahrenheit&timezone=UTC&forecast_days=7"
            )
            hourly = forecast.get("hourly") or {}
            times, temps, codes = hourly.get("time"), hourly.get("temperature_2m"), hourly.get("weathercode")
            if not times or not temps or not codes:
                return ""
            target = game_time.astimezone(timezone.utc)
            best_index, best_diff = 0, timedelta(days=999)
            for i, t in enumerate(times):
                dt = datetime.fromisoformat(f"{t}:00+00:00")
                diff = abs(dt - target)
                if diff < best_diff:
                    best_diff, best_index = diff, i
            temp = round(temps[best_index])
            return f"{self._weather_description(codes[best_index])}, {temp}°F"
        except Exception:
            return ""

    def _weather_description(self, code: int) -> str:
        if code == 0:
            return "Clear"
        if code <= 3:
            return "Partly Cloudy"
        if code in (45, 48):
            return "Fog"
        if 51 <= code <= 57:
            return "Drizzle"
        if 61 <= code <= 67:
            return "Rain"
        if 71 <= code <= 77:
            return "Snow"
        if 80 <= code <= 82:
            return "Rain Showers"
        if 85 <= code <= 86:
            return "Snow Showers"
        if code >= 95:
            return "Thunderstorms"
        return "Unknown"

    async def _build_no_game_today(self, team: mlb_teams.TeamInfo) -> BoxScore:
        next_game = await self._fetch_next_game(team)
        return BoxScore(
            away=TeamSide(name=team.name, city=team.city, abbreviation=team.abbreviation, score=0),
            home=TeamSide(name=(next_game.opponent if next_game else "TBD"), city="", abbreviation="", score=0),
            home_line=LineScore(), away_line=LineScore(),
            away_innings=[], home_innings=[],
            inning_half="", inning=0,
            venue=(next_game.venue if next_game else ""), weather="",
            home_pitcher="", home_pitcher_ip="", away_pitcher="", away_pitcher_ip="",
            status=GameStatus.SCHEDULED,
            scheduled_start=(next_game.start if next_game else None),
        )

    async def _fetch_next_game(self, team: mlb_teams.TeamInfo) -> NextGameInfo | None:
        start = date.today() + timedelta(days=1)
        end = date.today() + timedelta(days=21)
        data = await self._get_json(
            f"{STATS_BASE}/schedule?sportId=1&teamId={team.stats_api_id}"
            f"&startDate={_fmt_date(start)}&endDate={_fmt_date(end)}"
        )
        for entry in data.get("dates", []):
            games = entry.get("games", [])
            if not games:
                continue
            game = games[0]
            teams = game["teams"]
            away_id = teams["away"]["team"]["id"]
            home_id = teams["home"]["team"]["id"]
            is_away = away_id == team.stats_api_id
            opponent_id = home_id if is_away else away_id
            opponent = mlb_teams.team_by_id(opponent_id)
            venue = (game.get("venue") or {}).get("name", "")
            return NextGameInfo(
                opponent=opponent.full_name if opponent else "TBD",
                venue=venue,
                start=datetime.fromisoformat(game["gameDate"].replace("Z", "+00:00")),
                is_away=is_away,
            )
        return None

    def _games_from_schedule(self, data: dict) -> list[dict]:
        dates = data.get("dates", [])
        if not dates:
            return []
        return dates[0].get("games", [])


def headlines_for_team(
    headlines: list[Headline],
    *,
    team_city: str,
    team_name: str,
    roster_names: list[str] | None = None,
) -> list[Headline]:
    """Narrows the league-wide feed to what matters for one team: any
    article mentioning the team (city or nickname) or a roster player,
    plus at most one general-league article so the list isn't left too
    short when team-specific news is thin. Ports the same word-boundary
    + "State"/"A&M"/"Tech"/"Southern" disambiguation used in the Flutter
    app, so "Alabama" (a college example, but the same class of bug
    applies to any single-word city) doesn't match "Alabama State".
    """
    import re

    generic_conflicts = ["state", "a&m", "tech", "southern"]
    normalized_city = team_city.lower()
    city_pattern = None
    if normalized_city:
        suffixes = {re.escape(s) for s in generic_conflicts if not normalized_city.endswith(f" {s}")}
        escaped_city = re.escape(normalized_city)
        if suffixes:
            city_pattern = re.compile(rf"\b{escaped_city}\b(?!\s+({'|'.join(suffixes)}))")
        else:
            city_pattern = re.compile(rf"\b{escaped_city}\b")

    other_keywords = {team_name.lower(), *(n.lower() for n in (roster_names or []))}
    other_keywords.discard("")

    def is_relevant(headline: Headline) -> bool:
        text = f"{headline.title} {headline.byline}".lower()
        if city_pattern and city_pattern.search(text):
            return True
        return any(k in text for k in other_keywords)

    result = []
    other_used = False
    for headline in headlines:
        if is_relevant(headline):
            result.append(headline)
        elif not other_used:
            result.append(headline)
            other_used = True
    return result
