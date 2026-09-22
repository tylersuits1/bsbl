from __future__ import annotations

from bsbl import mlb_teams


def test_team_by_abbreviation_found():
    team = mlb_teams.team_by_abbreviation("ATL")
    assert team is not None
    assert team.name == "Braves"
    assert team.full_name == "Atlanta Braves"


def test_team_by_abbreviation_not_found():
    assert mlb_teams.team_by_abbreviation("XXX") is None


def test_team_by_id_found():
    team = mlb_teams.team_by_id(144)
    assert team is not None
    assert team.abbreviation == "ATL"


def test_team_by_id_not_found():
    assert mlb_teams.team_by_id(999999) is None


def test_full_name_with_no_city():
    # "Athletics" is the one team with no city in the table.
    team = mlb_teams.team_by_abbreviation("ATH")
    assert team.city == ""
    assert team.full_name == "Athletics"


def test_teams_in_division_sorted_by_name():
    teams = mlb_teams.teams_in_division("American League", "East")
    names = [t.name for t in teams]
    assert names == sorted(names)
    assert all(t.league == "American League" and t.division == "East" for t in teams)


def test_teams_in_division_empty_for_unknown_division():
    assert mlb_teams.teams_in_division("American League", "Not A Division") == []


def test_teams_in_league_covers_all_three_divisions():
    al_teams = mlb_teams.teams_in_league("American League")
    divisions = {t.division for t in al_teams}
    assert divisions == {"East", "Central", "West"}


def test_all_30_teams_present_and_unique():
    assert len(mlb_teams.TEAMS) == 30
    assert len({t.abbreviation for t in mlb_teams.TEAMS}) == 30
    assert len({t.stats_api_id for t in mlb_teams.TEAMS}) == 30
