"""Static NBA team data — ids/abbreviations match ESPN's basketball/nba
API. Conferences and divisions are the well-known, stable NBA alignment.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NbaTeamInfo:
    city: str
    name: str
    abbreviation: str
    conference: str  # "Eastern" | "Western"
    division: str
    espn_id: int

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}"


CONFERENCES = ["Eastern", "Western"]
DIVISIONS = {
    "Eastern": ["Atlantic", "Central", "Southeast"],
    "Western": ["Northwest", "Pacific", "Southwest"],
}

TEAMS: list[NbaTeamInfo] = [
    NbaTeamInfo("Boston", "Celtics", "BOS", "Eastern", "Atlantic", 2),
    NbaTeamInfo("Brooklyn", "Nets", "BKN", "Eastern", "Atlantic", 17),
    NbaTeamInfo("New York", "Knicks", "NY", "Eastern", "Atlantic", 18),
    NbaTeamInfo("Philadelphia", "76ers", "PHI", "Eastern", "Atlantic", 20),
    NbaTeamInfo("Toronto", "Raptors", "TOR", "Eastern", "Atlantic", 28),
    NbaTeamInfo("Chicago", "Bulls", "CHI", "Eastern", "Central", 4),
    NbaTeamInfo("Cleveland", "Cavaliers", "CLE", "Eastern", "Central", 5),
    NbaTeamInfo("Detroit", "Pistons", "DET", "Eastern", "Central", 8),
    NbaTeamInfo("Indiana", "Pacers", "IND", "Eastern", "Central", 11),
    NbaTeamInfo("Milwaukee", "Bucks", "MIL", "Eastern", "Central", 15),
    NbaTeamInfo("Atlanta", "Hawks", "ATL", "Eastern", "Southeast", 1),
    NbaTeamInfo("Charlotte", "Hornets", "CHA", "Eastern", "Southeast", 30),
    NbaTeamInfo("Miami", "Heat", "MIA", "Eastern", "Southeast", 14),
    NbaTeamInfo("Orlando", "Magic", "ORL", "Eastern", "Southeast", 19),
    NbaTeamInfo("Washington", "Wizards", "WSH", "Eastern", "Southeast", 27),
    NbaTeamInfo("Denver", "Nuggets", "DEN", "Western", "Northwest", 7),
    NbaTeamInfo("Minnesota", "Timberwolves", "MIN", "Western", "Northwest", 16),
    NbaTeamInfo("Oklahoma City", "Thunder", "OKC", "Western", "Northwest", 25),
    NbaTeamInfo("Portland", "Trail Blazers", "POR", "Western", "Northwest", 22),
    NbaTeamInfo("Utah", "Jazz", "UTAH", "Western", "Northwest", 26),
    NbaTeamInfo("Golden State", "Warriors", "GS", "Western", "Pacific", 9),
    NbaTeamInfo("LA", "Clippers", "LAC", "Western", "Pacific", 12),
    NbaTeamInfo("Los Angeles", "Lakers", "LAL", "Western", "Pacific", 13),
    NbaTeamInfo("Phoenix", "Suns", "PHX", "Western", "Pacific", 21),
    NbaTeamInfo("Sacramento", "Kings", "SAC", "Western", "Pacific", 23),
    NbaTeamInfo("Dallas", "Mavericks", "DAL", "Western", "Southwest", 6),
    NbaTeamInfo("Houston", "Rockets", "HOU", "Western", "Southwest", 10),
    NbaTeamInfo("Memphis", "Grizzlies", "MEM", "Western", "Southwest", 29),
    NbaTeamInfo("New Orleans", "Pelicans", "NO", "Western", "Southwest", 3),
    NbaTeamInfo("San Antonio", "Spurs", "SA", "Western", "Southwest", 24),
]

_BY_ESPN_ID = {t.espn_id: t for t in TEAMS}
_BY_ABBR = {t.abbreviation: t for t in TEAMS}


def team_by_espn_id(espn_id: int) -> NbaTeamInfo | None:
    return _BY_ESPN_ID.get(espn_id)


def team_by_abbreviation(abbreviation: str) -> NbaTeamInfo | None:
    return _BY_ABBR.get(abbreviation)


def teams_in_division(conference: str, division: str) -> list[NbaTeamInfo]:
    return sorted(
        (t for t in TEAMS if t.conference == conference and t.division == division),
        key=lambda t: t.name,
    )
