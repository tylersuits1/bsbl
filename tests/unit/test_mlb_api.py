"""mlb_api.py parsing logic — all offline. Fixture dicts below mirror the
real shapes recorded against live MLB Stats API responses during
development (see the SportsPages-TUI dev log), not invented schemas.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from bsbl import mlb_api, mlb_teams
from bsbl.mlb_api import (
    MlbStatsError,
    MlbStatsService,
    _fmt_date,
    _map_status,
    _player_stat_from_person,
    _record_string,
    current_baseball_date,
    headlines_for_team,
)
from bsbl.models import GameStatus, Headline


# -- _fmt_date / current_baseball_date -----------------------------------

def test_fmt_date():
    assert _fmt_date(date(2026, 9, 1)) == "2026-09-01"


class _FixedDatetime(datetime):
    """Stand-in for datetime.now() so current_baseball_date's 3am PST
    rollover can be tested deterministically.
    """
    _fixed: datetime

    @classmethod
    def now(cls, tz=None):
        return cls._fixed.astimezone(tz) if tz else cls._fixed


def _freeze(monkeypatch, utc_dt: datetime) -> None:
    frozen = type("_Frozen", (_FixedDatetime,), {"_fixed": utc_dt})
    monkeypatch.setattr(mlb_api, "datetime", frozen)


def test_current_baseball_date_stays_on_previous_day_before_3am_pst(monkeypatch):
    # 2026-09-02 02:00 UTC = 2026-09-01 18:00 PST (previous evening) —
    # well before the 3am cutoff, should read as 09-01.
    _freeze(monkeypatch, datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc))
    assert current_baseball_date() == date(2026, 9, 1)


def test_current_baseball_date_rolls_over_after_3am_pst(monkeypatch):
    # 2026-09-02 12:00 UTC = 2026-09-02 04:00 PST — past the 3am cutoff.
    _freeze(monkeypatch, datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc))
    assert current_baseball_date() == date(2026, 9, 2)


def test_current_baseball_date_just_before_cutoff(monkeypatch):
    # 2026-09-02 10:59 UTC = 2026-09-02 02:59 PST — one minute shy of 3am.
    _freeze(monkeypatch, datetime(2026, 9, 2, 10, 59, tzinfo=timezone.utc))
    assert current_baseball_date() == date(2026, 9, 1)


# -- _map_status -----------------------------------------------------------

@pytest.mark.parametrize(
    "detailed_state, expected",
    [
        ("Final", GameStatus.FINAL),
        ("Game Over", GameStatus.FINAL),
        ("Postponed", GameStatus.POSTPONED),
        ("Cancelled", GameStatus.POSTPONED),
        ("Delayed Start", GameStatus.DELAYED),
        ("Delayed: Rain", GameStatus.DELAYED),
        ("Warmup", GameStatus.WARMUP),
        ("Pre-Game", GameStatus.WARMUP),
        ("Scheduled", GameStatus.SCHEDULED),
        ("Preview", GameStatus.SCHEDULED),
        ("In Progress", GameStatus.LIVE),
        ("Something Unrecognized", GameStatus.LIVE),  # falls back to LIVE
    ],
)
def test_map_status(detailed_state, expected):
    assert _map_status(detailed_state) == expected


# -- _record_string ----------------------------------------------------

def test_record_string_normal():
    assert _record_string({"wins": 86, "losses": 61}) == "86-61"


def test_record_string_none():
    assert _record_string(None) == ""


def test_record_string_missing_fields():
    assert _record_string({"wins": 86}) == ""


# -- _player_stat_from_person ---------------------------------------------

def test_player_stat_from_person_hitter():
    person = {
        "fullName": "Matt Olson",
        "primaryPosition": {"abbreviation": "1B"},
        "stats": [
            {"group": {"displayName": "hitting"}, "splits": [{"stat": {"avg": ".280", "homeRuns": 30, "rbi": 90}}]},
        ],
    }
    stat = _player_stat_from_person(person)
    assert stat.name == "Matt Olson"
    assert stat.is_pitcher is False
    assert stat.avg == ".280"
    assert stat.home_runs == 30
    assert stat.has_stats is True


def test_player_stat_from_person_pitcher():
    person = {
        "fullName": "Chris Sale",
        "primaryPosition": {"abbreviation": "P"},
        "stats": [
            {"group": {"displayName": "pitching"}, "splits": [{"stat": {"wins": 10, "losses": 5, "era": "2.50", "inningsPitched": "150.0"}}]},
        ],
    }
    stat = _player_stat_from_person(person)
    assert stat.is_pitcher is True
    assert stat.wins_losses == "10-5"
    assert stat.era == "2.50"


def test_player_stat_from_person_no_stats():
    person = {"fullName": "Rookie Call-Up", "primaryPosition": {"abbreviation": "OF"}, "stats": []}
    stat = _player_stat_from_person(person)
    assert stat.has_stats is False
    assert stat.is_pitcher is False


def test_player_stat_from_person_pitcher_prefers_pitching_over_placeholder_hitting_line():
    # NL pitchers sometimes carry a placeholder hitting split alongside
    # real pitching stats — pitching should win for an is_pitcher=True person.
    person = {
        "fullName": "NL Pitcher",
        "primaryPosition": {"abbreviation": "P"},
        "stats": [
            {"group": {"displayName": "hitting"}, "splits": [{"stat": {"avg": ".100"}}]},
            {"group": {"displayName": "pitching"}, "splits": [{"stat": {"wins": 5, "losses": 3, "era": "3.10", "inningsPitched": "80.0"}}]},
        ],
    }
    stat = _player_stat_from_person(person)
    assert stat.is_pitcher is True
    assert stat.era == "3.10"


def test_player_stat_from_person_name_and_position_override():
    person = {"fullName": "Ignored", "primaryPosition": {"abbreviation": "P"}, "stats": []}
    stat = _player_stat_from_person(person, name="Override Name", position="SS")
    assert stat.name == "Override Name"
    assert stat.position == "SS"
    assert stat.is_pitcher is False  # position override changes is_pitcher too


# -- headlines_for_team -------------------------------------------------

def _headline(title: str, byline: str = "") -> Headline:
    return Headline(title=title, byline=byline, time_ago="", url="https://x", published_at=datetime.now(timezone.utc))


def test_headlines_for_team_matches_city():
    headlines = [_headline("Atlanta wins big"), _headline("Unrelated football story")]
    result = headlines_for_team(headlines, team_city="Atlanta", team_name="Braves")
    assert len(result) == 2  # the match, plus one general fallback article
    assert result[0].title == "Atlanta wins big"


def test_headlines_for_team_matches_name():
    headlines = [_headline("Braves clinch playoff spot")]
    result = headlines_for_team(headlines, team_city="Atlanta", team_name="Braves")
    assert result[0].title == "Braves clinch playoff spot"


def test_headlines_for_team_matches_roster_player():
    headlines = [_headline("Acuña homers twice")]
    result = headlines_for_team(
        headlines, team_city="Atlanta", team_name="Braves", roster_names=["Ronald Acuña Jr."],
    )
    assert result[0].title == "Acuña homers twice"


def test_headlines_for_team_avoids_state_school_false_positive():
    # "Alabama" as a city shouldn't match "Alabama State" articles.
    headlines = [_headline("Alabama State wins tournament")]
    result = headlines_for_team(headlines, team_city="Alabama", team_name="Crimson Tide")
    # Not relevant, but still included once as the one general fallback article.
    assert len(result) == 1


def test_headlines_for_team_only_one_fallback_article():
    headlines = [_headline("Unrelated one"), _headline("Unrelated two"), _headline("Unrelated three")]
    result = headlines_for_team(headlines, team_city="Atlanta", team_name="Braves")
    assert len(result) == 1


def test_headlines_for_team_empty_city_no_crash():
    headlines = [_headline("Braves win")]
    result = headlines_for_team(headlines, team_city="", team_name="Braves")
    assert result[0].title == "Braves win"


# -- MlbStatsService parsing methods (no network) -----------------------

@pytest.fixture
def service():
    return MlbStatsService(client=httpx.AsyncClient())  # never actually used for I/O below


def _minimal_live_feed(*, status_extra: dict | None = None) -> dict:
    """A trimmed-down but structurally real /feed/live shape, enough to
    exercise _parse_live_feed for a LIVE game.
    """
    return {
        "gameData": {
            "teams": {
                "away": {"id": 143, "teamName": "Phillies", "franchiseName": "Philadelphia", "abbreviation": "PHI"},
                "home": {"id": 144, "teamName": "Braves", "franchiseName": "Atlanta", "abbreviation": "ATL"},
            },
            "venue": {"name": "Truist Park", "id": 4705},
            "weather": {"condition": "Cloudy", "temp": "74"},
            "probablePitchers": {},
        },
        "liveData": {
            "linescore": {
                "currentInning": 3,
                "inningState": "Bottom",
                "innings": [
                    {"away": {"runs": 0}, "home": {"runs": 1}},
                    {"away": {"runs": 3}, "home": {"runs": 0}},
                ],
                "teams": {"away": {"runs": 3, "hits": 5, "errors": 1}, "home": {"runs": 1, "hits": 2, "errors": 0}},
                "balls": 2, "strikes": 1, "outs": 1,
                "offense": {
                    "batter": {"fullName": "Marcell Ozuna"},
                    "first": {"fullName": "Ozzie Albies"},
                },
                "defense": {"pitcher": {"fullName": "Aaron Nola"}},
            },
            "boxscore": {
                "teams": {
                    "away": {"battingOrder": [], "pitchers": [1], "players": {"ID1": {"person": {"fullName": "Aaron Nola"}, "stats": {"pitching": {"inningsPitched": "2.1"}}}}},
                    "home": {"battingOrder": [], "players": {"ID2": {"person": {"fullName": "Chris Sale"}, "stats": {"pitching": {"inningsPitched": "3.0"}}}}, "pitchers": [2]},
                },
            },
            "plays": {
                "currentPlay": {
                    "playEvents": [
                        {"isPitch": True, "details": {"type": {"description": "Sinker"}, "description": "Ball", "isInPlay": False}},
                    ],
                    "result": {},
                    "runners": [],
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_parse_live_feed_basic_live_game(service):
    live = _minimal_live_feed()
    team = mlb_teams.team_by_abbreviation("ATL")
    box = await service._parse_live_feed(
        live, followed_team=team, status=GameStatus.LIVE, series_game_number=1,
        away_record="86-61", home_record="80-67",
    )
    assert box.away.abbreviation == "PHI"
    assert box.home.abbreviation == "ATL"
    assert box.away.score == 3
    assert box.home.score == 1
    assert box.away_innings == [0, 3]
    assert box.home_innings == [1, 0]
    assert box.inning == 3
    assert box.inning_half == "Bottom"
    assert box.venue == "Truist Park"
    assert box.weather == "Cloudy, 74°F"
    # followed team is home (ATL) -> followed_team_record should be home_record
    assert box.followed_team_record == "80-67"
    # live at-bat state
    assert box.balls == 2 and box.strikes == 1 and box.outs == 1
    assert box.at_bat_batter == "Marcell Ozuna"
    assert box.at_bat_pitcher == "Aaron Nola"
    assert box.on_first == "Ozzie Albies"
    assert box.on_second == ""
    assert box.last_pitch_type == "Sinker"
    assert box.last_pitch_result == "Ball"
    assert box.last_pitch_outcome == ""


@pytest.mark.asyncio
async def test_parse_live_feed_followed_team_away_uses_away_record(service):
    live = _minimal_live_feed()
    team = mlb_teams.team_by_abbreviation("PHI")
    box = await service._parse_live_feed(
        live, followed_team=team, status=GameStatus.LIVE, series_game_number=1,
        away_record="86-61", home_record="80-67",
    )
    assert box.followed_team_record == "86-61"


@pytest.mark.asyncio
async def test_parse_live_feed_scheduled_uses_probable_pitchers(service):
    live = _minimal_live_feed()
    live["gameData"]["probablePitchers"] = {
        "away": {"fullName": "Aaron Nola"}, "home": {"fullName": "Chris Sale"},
    }
    live["gameData"]["weather"] = {"condition": "Clear", "temp": "80"}  # avoid the network weather-forecast path
    live["gameData"]["datetime"] = {"dateTime": "2026-09-11T23:05:00Z"}
    # A real SCHEDULED game's linescore is empty — no count/outs to carry
    # yet, unlike the LIVE fixture this one is based on.
    live["liveData"]["linescore"]["balls"] = 0
    live["liveData"]["linescore"]["strikes"] = 0
    live["liveData"]["linescore"]["outs"] = 0
    team = mlb_teams.team_by_abbreviation("ATL")
    box = await service._parse_live_feed(
        live, followed_team=team, status=GameStatus.SCHEDULED, series_game_number=1,
    )
    assert box.away_pitcher == "Aaron Nola"
    assert box.home_pitcher == "Chris Sale"
    assert box.away_pitcher_ip == ""
    # no live at-bat state while scheduled
    assert box.at_bat_batter == ""
    assert box.balls == 0
    assert box.scheduled_start == datetime(2026, 9, 11, 23, 5, tzinfo=timezone.utc)


# -- _last_pitch / _out_location (real recorded shapes) ------------------

def test_last_pitch_no_pitches_yet(service):
    live_data = {"plays": {"currentPlay": {"playEvents": []}}}
    assert service._last_pitch(live_data) == ("", "", "")


def test_last_pitch_ball_not_in_play(service):
    live_data = {
        "plays": {"currentPlay": {"playEvents": [
            {"isPitch": True, "details": {"type": {"description": "Four-Seam Fastball"}, "description": "Ball", "isInPlay": False}},
        ]}},
    }
    assert service._last_pitch(live_data) == ("Four-Seam Fastball", "Ball", "")


def test_last_pitch_in_play_single_no_out_location(service):
    # Recorded shape: a clean single, no runner thrown out.
    live_data = {
        "plays": {
            "currentPlay": {
                "playEvents": [
                    {"isPitch": True, "details": {"type": {"description": "Sinker"}, "description": "In play, no out", "isInPlay": True}},
                ],
                "result": {"event": "Single", "eventType": "single", "isOut": False},
                "runners": [
                    {"movement": {"start": None, "end": "1B", "outBase": None, "isOut": False}},
                ],
            },
        },
    }
    assert service._last_pitch(live_data) == ("Sinker", "In play, no out", "Single")


def test_last_pitch_in_play_groundout_with_out_location(service):
    # Recorded shape (George Springer groundout, SS to 1B): the
    # batter-runner (movement.start is None) is out at first.
    live_data = {
        "plays": {
            "currentPlay": {
                "playEvents": [
                    {"isPitch": True, "details": {"type": {"description": "Sinker"}, "description": "In play, out(s)", "isInPlay": True}},
                ],
                "result": {"event": "Groundout", "eventType": "field_out", "isOut": True},
                "runners": [
                    {"movement": {"start": None, "end": None, "outBase": "1B", "isOut": True}},
                ],
            },
        },
    }
    assert service._last_pitch(live_data) == ("Sinker", "In play, out(s)", "out at first")


def test_last_pitch_in_play_flyout_no_matching_out_base_falls_back_to_event(service):
    # A flyout has no "out at a base" — the batter is just out; the
    # runners list here has no unstarted (batter) runner at all.
    live_data = {
        "plays": {
            "currentPlay": {
                "playEvents": [
                    {"isPitch": True, "details": {"type": {"description": "Slider"}, "description": "In play, out(s)", "isInPlay": True}},
                ],
                "result": {"event": "Flyout", "eventType": "field_out", "isOut": True},
                "runners": [],
            },
        },
    }
    assert service._last_pitch(live_data) == ("Slider", "In play, out(s)", "Flyout")


def test_out_location_ignores_runners_that_already_started_on_base(service):
    # A fielder's-choice-style play where an existing runner (start="2B")
    # is thrown out, but the batter-runner (start=None) is safe — should
    # not report "out at" for the safe batter.
    current_play = {
        "runners": [
            {"movement": {"start": "2B", "end": None, "outBase": "3B", "isOut": True}},
            {"movement": {"start": None, "end": "1B", "outBase": None, "isOut": False}},
        ],
    }
    assert service._out_location(current_play) == ""


# -- _parse_scoring_plays (real recorded shape) ---------------------------

def test_parse_scoring_plays_solo_home_run(service):
    live = {
        "gameData": {"teams": {"away": {"abbreviation": "PHI"}, "home": {"abbreviation": "ATL"}}},
        "liveData": {
            "plays": {
                "scoringPlays": [0],
                "allPlays": [
                    {
                        "about": {"inning": 1, "isTopInning": False},
                        "result": {"event": "Home Run", "description": "...", "awayScore": 0, "homeScore": 1},
                        "matchup": {"batter": {"fullName": "Ronald Acuña Jr."}},
                        "runners": [
                            {"movement": {"end": "score"}, "details": {"runner": {"fullName": "Ronald Acuña Jr."}}},
                        ],
                    },
                ],
            },
        },
    }
    result = service._parse_scoring_plays(live)
    assert result.away_abbr == "PHI"
    assert result.home_abbr == "ATL"
    assert len(result.plays) == 1
    play = result.plays[0]
    assert play.inning == 1
    assert play.is_top is False
    assert play.batter == "Ronald Acuña Jr."
    assert play.event == "Home Run"
    assert play.scorers == ["Ronald Acuña Jr."]
    assert play.away_score == 0
    assert play.home_score == 1


def test_parse_scoring_plays_multiple_scorers_on_one_play(service):
    # Recorded shape: a fielding error that scored one runner while
    # advancing two others (who did NOT score) — only the "score" mover
    # should end up in `scorers`.
    live = {
        "gameData": {"teams": {"away": {"abbreviation": "COL"}, "home": {"abbreviation": "DET"}}},
        "liveData": {
            "plays": {
                "scoringPlays": [0],
                "allPlays": [
                    {
                        "about": {"inning": 5, "isTopInning": True},
                        "result": {"event": "Field Error", "awayScore": 1, "homeScore": 0},
                        "matchup": {"batter": {"fullName": "Cole Carrigg"}},
                        "runners": [
                            {"movement": {"end": "1B"}, "details": {"runner": {"fullName": "Cole Carrigg"}}},
                            {"movement": {"end": "score"}, "details": {"runner": {"fullName": "Ezequiel Tovar"}}},
                            {"movement": {"end": "3B"}, "details": {"runner": {"fullName": "Jake McCarthy"}}},
                            {"movement": {"end": "2B"}, "details": {"runner": {"fullName": "Connor Norby"}}},
                        ],
                    },
                ],
            },
        },
    }
    result = service._parse_scoring_plays(live)
    assert result.plays[0].scorers == ["Ezequiel Tovar"]


def test_parse_scoring_plays_no_scoring_plays_yet(service):
    live = {
        "gameData": {"teams": {"away": {"abbreviation": "PHI"}, "home": {"abbreviation": "ATL"}}},
        "liveData": {"plays": {"scoringPlays": [], "allPlays": []}},
    }
    result = service._parse_scoring_plays(live)
    assert result.plays == []


def test_parse_scoring_plays_ignores_out_of_range_index(service):
    live = {
        "gameData": {"teams": {"away": {"abbreviation": "PHI"}, "home": {"abbreviation": "ATL"}}},
        "liveData": {"plays": {"scoringPlays": [5], "allPlays": []}},
    }
    result = service._parse_scoring_plays(live)
    assert result.plays == []


# -- _build_team / _line_score_from / _last_pitcher_line -----------------

def test_build_team_with_batting_order(service):
    team_data = {"teamName": "Braves", "franchiseName": "Atlanta", "abbreviation": "ATL"}
    box_team_data = {
        "battingOrder": [1, 2],
        "players": {
            "ID1": {"person": {"fullName": "Ronald Acuña Jr."}, "position": {"abbreviation": "RF"}},
            "ID2": {"person": {"fullName": "Ozzie Albies"}, "position": {"abbreviation": "2B"}},
        },
    }
    team = service._build_team(team_data, box_team_data, score=5, record="86-61")
    assert team.full_name == "Atlanta Braves"
    assert team.score == 5
    assert team.batting_order == ["Ronald Acuña Jr. (RF)", "Ozzie Albies (2B)"]


def test_line_score_from_none_defaults_to_zero(service):
    line = service._line_score_from(None)
    assert (line.runs, line.hits, line.errors) == (0, 0, 0)


def test_last_pitcher_line_no_pitchers(service):
    assert service._last_pitcher_line({}) == ("TBD", "")


def test_last_pitcher_line_uses_most_recent_pitcher(service):
    team_box = {
        "pitchers": [1, 2],
        "players": {
            "ID2": {"person": {"fullName": "Chris Sale"}, "stats": {"pitching": {"inningsPitched": "3.1"}}},
        },
    }
    name, ip = service._last_pitcher_line(team_box)
    assert name == "Chris Sale"
    assert ip == "3.1 IP"


# -- _weather_description ------------------------------------------------

@pytest.mark.parametrize(
    "code, expected",
    [(0, "Clear"), (2, "Partly Cloudy"), (45, "Fog"), (53, "Drizzle"), (63, "Rain"),
     (73, "Snow"), (81, "Rain Showers"), (85, "Snow Showers"), (95, "Thunderstorms"), (999, "Thunderstorms"),
     (20, "Unknown")],  # a code that falls in none of the mapped ranges
)
def test_weather_description(service, code, expected):
    assert service._weather_description(code) == expected


# -- _get_json error handling (mocked transport, no real network) --------

@pytest.mark.asyncio
async def test_get_json_raises_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        svc = MlbStatsService(client)
        with pytest.raises(MlbStatsError):
            await svc._get_json("https://statsapi.mlb.com/api/v1/whatever")


@pytest.mark.asyncio
async def test_get_json_raises_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        svc = MlbStatsService(client)
        with pytest.raises(MlbStatsError):
            await svc._get_json("https://statsapi.mlb.com/api/v1/whatever")


@pytest.mark.asyncio
async def test_get_json_returns_parsed_body_on_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        svc = MlbStatsService(client)
        assert await svc._get_json("https://statsapi.mlb.com/api/v1/whatever") == {"ok": True}


# -- search_players (mocked transport) ------------------------------------

@pytest.mark.asyncio
async def test_search_players_filters_inactive_and_non_players():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"people": [
            {"id": 1, "fullName": "Active MLB Player", "isPlayer": True, "active": True,
             "primaryPosition": {"abbreviation": "RF"}, "currentTeam": {"id": 144}},
            {"id": 2, "fullName": "Retired Player", "isPlayer": True, "active": False,
             "currentTeam": {"id": 144}},
            {"id": 3, "fullName": "Coach Not A Player", "isPlayer": False, "active": True},
            {"id": 4, "fullName": "Minor Leaguer", "isPlayer": True, "active": True,
             "currentTeam": {"id": 999999}},  # not a real MLB team id
        ]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        svc = MlbStatsService(client)
        results = await svc.search_players("query")

    assert len(results) == 1
    assert results[0].name == "Active MLB Player"
    assert results[0].team_abbr == "ATL"
