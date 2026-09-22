from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from rich.console import Console

from bsbl.models import GameStatus, NextGameInfo, PlayerStat, ScoringPlay, ScoringPlaysResult
from bsbl.rendering import (
    bases_line,
    batting_order_columns,
    inning_table,
    last_name,
    last_pitch_line,
    live_at_bat_section,
    location_weather_line,
    masthead,
    matchup_line,
    pitching_lines,
    player_stats_table,
    refresh_status_line,
    scoring_plays_lines,
    status_line,
    status_text,
)


def render(renderable) -> str:
    """Flatten any Rich renderable to plain text for substring assertions."""
    console = Console(width=200, record=True)
    console.print(renderable)
    return console.export_text().rstrip("\n")


# -- last_name --------------------------------------------------------

@pytest.mark.parametrize(
    "full_name, expected",
    [
        ("Ronald Acuña Jr.", "Acuña"),
        ("Vladimir Guerrero Jr.", "Guerrero"),
        ("Chris Sale", "Sale"),
        ("Ken Griffey III", "Griffey"),
        ("Robinson Cano Sr.", "Cano"),
        ("Ichiro", "Ichiro"),  # single-word name, no suffix to strip
        ("", ""),
        ("  Multiple   Spaces  Guy  ", "Guy"),
    ],
)
def test_last_name_strips_generational_suffixes(full_name, expected):
    assert last_name(full_name) == expected


# -- matchup_line / status_line ----------------------------------------

def test_matchup_line_shows_scores_when_game_started(box_score):
    box = box_score(status=GameStatus.LIVE)
    assert render(matchup_line(box)) == "Phillies 3 | Braves 1"


def test_matchup_line_shows_at_symbol_before_first_pitch(box_score):
    box = box_score(status=GameStatus.SCHEDULED, away_innings=[], home_innings=[])
    assert render(matchup_line(box)) == "Phillies @ Braves"


def test_status_text_styles_by_status():
    assert status_text(GameStatus.LIVE).style == "bold red"
    assert status_text(GameStatus.FINAL).style == "bold"


def test_status_line_scheduled_shows_start_time(box_score):
    # Naive — format_short_datetime/format_clock_time call .astimezone(),
    # which for a naive input is a system-local no-op, keeping this
    # assertion true regardless of the machine's actual timezone.
    start = datetime(2026, 8, 29, 19, 20)
    box = box_score(status=GameStatus.SCHEDULED, scheduled_start=start)
    text = render(status_line(box))
    assert "SCHEDULED" in text
    assert "7:20 PM" in text


def test_status_line_live_shows_inning(box_score):
    box = box_score(status=GameStatus.LIVE, inning=4, inning_half="Top")
    assert render(status_line(box)) == "LIVE  TOP OF THE FOURTH INNING"


def test_status_line_final_has_no_extra_text(box_score):
    box = box_score(status=GameStatus.FINAL)
    assert render(status_line(box)) == "FINAL"


# -- location_weather_line -----------------------------------------------

def test_location_weather_line_both_present(box_score):
    box = box_score(venue="Truist Park", weather="Cloudy, 74°F")
    assert location_weather_line(box) == "Truist Park  |  Cloudy, 74°F"


def test_location_weather_line_venue_only(box_score):
    box = box_score(venue="Truist Park", weather="")
    assert location_weather_line(box) == "Truist Park"


def test_location_weather_line_none_when_both_blank(box_score):
    box = box_score(venue="", weather="")
    assert location_weather_line(box) is None


# -- pitching_lines --------------------------------------------------------

def test_pitching_lines_shows_probable_pitchers_when_scheduled(box_score):
    box = box_score(
        status=GameStatus.SCHEDULED,
        away_pitcher="Aaron Nola", home_pitcher="Chris Sale",
    )
    lines = pitching_lines(box)
    assert lines == ["Probable Pitchers: Nola vs Sale"]


def test_pitching_lines_shows_actual_pitching_line_when_live(box_score):
    box = box_score(status=GameStatus.LIVE, away_pitcher_ip="3.0 IP", home_pitcher_ip="3.1 IP")
    lines = pitching_lines(box)
    assert lines == ["Pitching: Nola (PHI) 3.0 IP  |  Sale (ATL) 3.1 IP"]


def test_pitching_lines_appends_up_next_when_final_with_next_game(box_score):
    next_game = NextGameInfo(
        opponent="New York Mets", venue="Citi Field",
        start=datetime(2026, 9, 1, 19, 10, tzinfo=timezone.utc), is_away=True,
    )
    box = box_score(status=GameStatus.FINAL, next_game=next_game)
    lines = pitching_lines(box)
    assert lines[0].startswith("Pitching:")
    assert lines[1] == ""
    assert lines[2].startswith("UP NEXT: @New York Mets")


def test_pitching_lines_no_up_next_without_next_game(box_score):
    box = box_score(status=GameStatus.FINAL, next_game=None)
    lines = pitching_lines(box)
    assert all("UP NEXT" not in line for line in lines)


# -- bases_line ------------------------------------------------------------

def test_bases_line_empty(box_score):
    box = box_score(on_first="", on_second="", on_third="")
    assert bases_line(box) == "Bases empty"


def test_bases_line_loaded(box_score):
    box = box_score(on_first="A", on_second="B", on_third="C")
    assert bases_line(box) == "Bases loaded"


def test_bases_line_one_runner_uses_last_name(box_score):
    box = box_score(on_first="Ozzie Albies", on_second="", on_third="")
    assert bases_line(box) == "Albies on first"


def test_bases_line_two_runners_joined(box_score):
    box = box_score(on_first="Ozzie Albies", on_second="Ronald Acuña Jr.", on_third="")
    assert bases_line(box) == "Albies on first, Acuña on second"


# -- last_pitch_line ---------------------------------------------------

def test_last_pitch_line_none_when_no_pitch_yet(box_score):
    box = box_score(last_pitch_type="")
    assert last_pitch_line(box) is None


def test_last_pitch_line_basic(box_score):
    box = box_score(last_pitch_type="Curveball", last_pitch_result="Called Strike")
    assert render(last_pitch_line(box)) == "Curveball | Strike"


def test_last_pitch_line_swing(box_score):
    box = box_score(last_pitch_type="Sweeper", last_pitch_result="Swinging Strike")
    assert render(last_pitch_line(box)) == "Sweeper | Swing"


def test_last_pitch_line_in_play_with_outcome(box_score):
    box = box_score(
        last_pitch_type="Sinker", last_pitch_result="In play, out(s)", last_pitch_outcome="out at first",
    )
    assert render(last_pitch_line(box)) == "Sinker | In Play - out at first"


def test_last_pitch_line_unknown_result_passed_through(box_score):
    box = box_score(last_pitch_type="Slider", last_pitch_result="Some Unmapped Result")
    assert render(last_pitch_line(box)) == "Slider | Some Unmapped Result"


# -- live_at_bat_section -----------------------------------------------

def test_live_at_bat_section_none_when_not_live(box_score):
    box = box_score(status=GameStatus.SCHEDULED)
    assert live_at_bat_section(box) is None


def test_live_at_bat_section_none_when_final(box_score):
    box = box_score(status=GameStatus.FINAL)
    assert live_at_bat_section(box) is None


def test_live_at_bat_section_contents_when_live(box_score):
    box = box_score(
        status=GameStatus.LIVE,
        at_bat_batter="Marcell Ozuna", at_bat_pitcher="Aaron Nola",
        balls=2, strikes=1, outs=1,
        on_first="Ozzie Albies", on_second="", on_third="",
    )
    text = render(live_at_bat_section(box))
    assert "AT BAT Ozuna | PITCHING Nola" in text
    assert "2-1 COUNT   1 OUT" in text
    assert "Albies on first" in text


def test_live_at_bat_section_shows_delayed_too(box_score):
    box = box_score(status=GameStatus.DELAYED, at_bat_batter="", at_bat_pitcher="")
    assert live_at_bat_section(box) is not None


# -- inning_table ------------------------------------------------------

def test_inning_table_shows_scores_and_dashes(box_score):
    box = box_score(away_innings=[0, 3, 0], home_innings=[1, 0])
    text = render(inning_table(box))
    assert "PHI" in text and "ATL" in text
    # innings 4-9 not played yet -> dash
    assert "–" in text


def test_inning_table_at_least_nine_columns(box_score):
    box = box_score(away_innings=[1], home_innings=[0])
    table = inning_table(box)
    # 1 label column + 9 inning columns (minimum) + R/H/E
    assert table.columns[0].header == ""
    inning_headers = [c.header for c in table.columns[1:-3]]
    assert inning_headers == [str(i) for i in range(1, 10)]


def test_inning_table_extends_past_nine_for_extra_innings(box_score):
    box = box_score(away_innings=[0] * 11, home_innings=[0] * 10)
    table = inning_table(box)
    inning_headers = [c.header for c in table.columns[1:-3]]
    assert inning_headers == [str(i) for i in range(1, 12)]


# -- batting_order_columns / player_stats_table -------------------------

def test_batting_order_columns_shows_not_yet_announced_when_empty(box_score):
    box = box_score()
    box.away.batting_order = []
    text = render(batting_order_columns(box))
    assert "Not yet announced" in text


def test_batting_order_columns_numbers_the_lineup(box_score):
    box = box_score()
    box.away.batting_order = ["Trea Turner (SS)", "Bryce Harper (1B)"]
    text = render(batting_order_columns(box))
    assert "1. Trea Turner (SS)" in text
    assert "2. Bryce Harper (1B)" in text


def test_player_stats_table_hitters():
    stats = [
        PlayerStat(name="Matt Olson", position="1B", is_pitcher=False, avg=".280", home_runs=30, rbi=90),
        PlayerStat(name="Chris Sale", position="P", is_pitcher=True, wins_losses="10-5", era="2.50", innings_pitched="150.0"),
    ]
    text = render(player_stats_table(stats, pitchers=False))
    assert "Matt Olson" in text
    assert "Chris Sale" not in text
    assert ".280" in text


def test_player_stats_table_no_stats_shows_dash():
    stats = [PlayerStat(name="Rookie", position="OF", is_pitcher=False, has_stats=False)]
    text = render(player_stats_table(stats, pitchers=False))
    assert "Rookie" in text
    assert "—" in text


# -- refresh_status_line -------------------------------------------------

def test_refresh_status_line_not_yet_updated():
    assert render(refresh_status_line(None, False)) == "Not yet updated"


def test_refresh_status_line_shows_time():
    dt = datetime(2026, 8, 29, 16, 10)  # naive — see test_status_line_scheduled_shows_start_time
    assert render(refresh_status_line(dt, False)) == "Last updated 4:10 PM"


def test_refresh_status_line_paused_prefix():
    dt = datetime(2026, 8, 29, 16, 10)  # naive — see test_status_line_scheduled_shows_start_time
    text = render(refresh_status_line(dt, True))
    assert text.startswith("⏸ PAUSED")
    assert "Last updated 4:10 PM" in text


# -- masthead ------------------------------------------------------------

def test_masthead_shows_version_when_given():
    text = render(masthead("Atlanta Braves", "86-61", "Fri, Sep 11, 2026", page=1, total_pages=3, version="0.4.0"))
    assert "BSBL v0.4.0" in text
    assert "ATLANTA BRAVES" in text
    assert "86-61" in text
    assert "Page 1/3" in text


def test_masthead_no_version_string_when_omitted():
    text = render(masthead("Players", "", "Fri, Sep 11, 2026", page=1, total_pages=1))
    assert "BSBL ·" in text
    assert "BSBL v" not in text


def test_masthead_no_record_line_when_blank():
    text = render(masthead("Players", "", "Fri, Sep 11, 2026", page=1, total_pages=1))
    assert "Page 1/1" in text


# -- scoring_plays_lines --------------------------------------------------

def test_scoring_plays_lines_no_plays_yet():
    result = ScoringPlaysResult(away_abbr="PHI", home_abbr="ATL", plays=[])
    assert scoring_plays_lines(result) == ["No scoring plays yet."]


def test_scoring_plays_lines_groups_by_inning_and_formats_solo_homer():
    result = ScoringPlaysResult(
        away_abbr="PHI", home_abbr="ATL",
        plays=[
            ScoringPlay(
                inning=1, is_top=False, batter="Ronald Acuña Jr.", event="Home Run",
                scorers=["Ronald Acuña Jr."], away_score=0, home_score=1,
            ),
        ],
    )
    lines = scoring_plays_lines(result)
    header = render(lines[0])
    assert header == "FIRST INNING"
    assert lines[1] == "Acuña | Home Run - Acuña scored"
    assert lines[2] == "PHI 0 - ATL 1"


def test_scoring_plays_lines_multi_scorer_play_lists_all_names():
    result = ScoringPlaysResult(
        away_abbr="CIN", home_abbr="MIL",
        plays=[
            ScoringPlay(
                inning=5, is_top=True, batter="Christian Yelich", event="Home Run",
                scorers=["Willy Adames", "William Contreras", "Christian Yelich"],
                away_score=0, home_score=17,
            ),
        ],
    )
    lines = scoring_plays_lines(result)
    assert lines[1] == "Yelich | Home Run - Adames, Contreras, Yelich scored"


def test_scoring_plays_lines_second_play_same_inning_no_repeat_header():
    result = ScoringPlaysResult(
        away_abbr="PHI", home_abbr="ATL",
        plays=[
            ScoringPlay(inning=1, is_top=True, batter="A", event="Single", scorers=["B"], away_score=1, home_score=0),
            ScoringPlay(inning=1, is_top=False, batter="C", event="Double", scorers=["D"], away_score=1, home_score=1),
        ],
    )
    lines = scoring_plays_lines(result)
    inning_headers = [line for line in lines if not isinstance(line, str)]
    assert len(inning_headers) == 1  # only one "FIRST INNING" header for both plays


def test_scoring_plays_lines_new_inning_gets_new_header():
    result = ScoringPlaysResult(
        away_abbr="PHI", home_abbr="ATL",
        plays=[
            ScoringPlay(inning=1, is_top=True, batter="A", event="Single", scorers=["A"], away_score=1, home_score=0),
            ScoringPlay(inning=4, is_top=False, batter="B", event="Double", scorers=["B"], away_score=1, home_score=1),
        ],
    )
    lines = scoring_plays_lines(result)
    headers = [render(line) for line in lines if not isinstance(line, str)]
    assert headers == ["FIRST INNING", "FOURTH INNING"]
