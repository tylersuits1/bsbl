"""Static MLB team data — ids, abbreviations, league, and division match
the live MLB Stats API (statsapi.mlb.com) as of 2026-08-29. Mirrors the
same table used in the Flutter sibling app (the-sports-pages) so the two
stay consistent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TeamInfo:
    city: str
    name: str
    abbreviation: str
    league: str
    division: str
    stats_api_id: int

    @property
    def full_name(self) -> str:
        return self.name if not self.city else f"{self.city} {self.name}"


LEAGUES = ["American League", "National League"]

TEAMS: list[TeamInfo] = [
    TeamInfo("Los Angeles", "Angels", "LAA", "American League", "West", 108),
    TeamInfo("Houston", "Astros", "HOU", "American League", "West", 117),
    TeamInfo("", "Athletics", "ATH", "American League", "West", 133),
    TeamInfo("Toronto", "Blue Jays", "TOR", "American League", "East", 141),
    TeamInfo("Atlanta", "Braves", "ATL", "National League", "East", 144),
    TeamInfo("Milwaukee", "Brewers", "MIL", "National League", "Central", 158),
    TeamInfo("St. Louis", "Cardinals", "STL", "National League", "Central", 138),
    TeamInfo("Chicago", "Cubs", "CHC", "National League", "Central", 112),
    TeamInfo("Arizona", "Diamondbacks", "AZ", "National League", "West", 109),
    TeamInfo("Los Angeles", "Dodgers", "LAD", "National League", "West", 119),
    TeamInfo("San Francisco", "Giants", "SF", "National League", "West", 137),
    TeamInfo("Cleveland", "Guardians", "CLE", "American League", "Central", 114),
    TeamInfo("Seattle", "Mariners", "SEA", "American League", "West", 136),
    TeamInfo("Miami", "Marlins", "MIA", "National League", "East", 146),
    TeamInfo("New York", "Mets", "NYM", "National League", "East", 121),
    TeamInfo("Washington", "Nationals", "WSH", "National League", "East", 120),
    TeamInfo("Baltimore", "Orioles", "BAL", "American League", "East", 110),
    TeamInfo("San Diego", "Padres", "SD", "National League", "West", 135),
    TeamInfo("Philadelphia", "Phillies", "PHI", "National League", "East", 143),
    TeamInfo("Pittsburgh", "Pirates", "PIT", "National League", "Central", 134),
    TeamInfo("Texas", "Rangers", "TEX", "American League", "West", 140),
    TeamInfo("Tampa Bay", "Rays", "TB", "American League", "East", 139),
    TeamInfo("Cincinnati", "Reds", "CIN", "National League", "Central", 113),
    TeamInfo("Boston", "Red Sox", "BOS", "American League", "East", 111),
    TeamInfo("Colorado", "Rockies", "COL", "National League", "West", 115),
    TeamInfo("Kansas City", "Royals", "KC", "American League", "Central", 118),
    TeamInfo("Detroit", "Tigers", "DET", "American League", "Central", 116),
    TeamInfo("Minnesota", "Twins", "MIN", "American League", "Central", 142),
    TeamInfo("Chicago", "White Sox", "CWS", "American League", "Central", 145),
    TeamInfo("New York", "Yankees", "NYY", "American League", "East", 147),
]

_BY_ID = {t.stats_api_id: t for t in TEAMS}
_BY_ABBR = {t.abbreviation: t for t in TEAMS}


def team_by_id(stats_api_id: int) -> TeamInfo | None:
    return _BY_ID.get(stats_api_id)


def team_by_abbreviation(abbreviation: str) -> TeamInfo | None:
    return _BY_ABBR.get(abbreviation)


def teams_in_league(league: str) -> list[TeamInfo]:
    return sorted((t for t in TEAMS if t.league == league), key=lambda t: t.name)


def teams_in_division(league: str, division: str) -> list[TeamInfo]:
    return sorted(
        (t for t in TEAMS if t.league == league and t.division == division),
        key=lambda t: t.name,
    )
