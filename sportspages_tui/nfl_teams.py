"""Static NFL team data — ids/abbreviations match ESPN's football/nfl
API. Conferences and divisions are the well-known, stable NFL alignment.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NflTeamInfo:
    city: str
    name: str
    abbreviation: str
    conference: str  # "AFC" | "NFC"
    division: str    # "East" | "North" | "South" | "West"
    espn_id: int

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}"


CONFERENCES = ["AFC", "NFC"]
DIVISIONS = ["East", "North", "South", "West"]

TEAMS: list[NflTeamInfo] = [
    NflTeamInfo("Buffalo", "Bills", "BUF", "AFC", "East", 2),
    NflTeamInfo("Miami", "Dolphins", "MIA", "AFC", "East", 15),
    NflTeamInfo("New England", "Patriots", "NE", "AFC", "East", 17),
    NflTeamInfo("New York", "Jets", "NYJ", "AFC", "East", 20),
    NflTeamInfo("Baltimore", "Ravens", "BAL", "AFC", "North", 33),
    NflTeamInfo("Cincinnati", "Bengals", "CIN", "AFC", "North", 4),
    NflTeamInfo("Cleveland", "Browns", "CLE", "AFC", "North", 5),
    NflTeamInfo("Pittsburgh", "Steelers", "PIT", "AFC", "North", 23),
    NflTeamInfo("Houston", "Texans", "HOU", "AFC", "South", 34),
    NflTeamInfo("Indianapolis", "Colts", "IND", "AFC", "South", 11),
    NflTeamInfo("Jacksonville", "Jaguars", "JAX", "AFC", "South", 30),
    NflTeamInfo("Tennessee", "Titans", "TEN", "AFC", "South", 10),
    NflTeamInfo("Denver", "Broncos", "DEN", "AFC", "West", 7),
    NflTeamInfo("Kansas City", "Chiefs", "KC", "AFC", "West", 12),
    NflTeamInfo("Las Vegas", "Raiders", "LV", "AFC", "West", 13),
    NflTeamInfo("Los Angeles", "Chargers", "LAC", "AFC", "West", 24),
    NflTeamInfo("Dallas", "Cowboys", "DAL", "NFC", "East", 6),
    NflTeamInfo("New York", "Giants", "NYG", "NFC", "East", 19),
    NflTeamInfo("Philadelphia", "Eagles", "PHI", "NFC", "East", 21),
    NflTeamInfo("Washington", "Commanders", "WSH", "NFC", "East", 28),
    NflTeamInfo("Chicago", "Bears", "CHI", "NFC", "North", 3),
    NflTeamInfo("Detroit", "Lions", "DET", "NFC", "North", 8),
    NflTeamInfo("Green Bay", "Packers", "GB", "NFC", "North", 9),
    NflTeamInfo("Minnesota", "Vikings", "MIN", "NFC", "North", 16),
    NflTeamInfo("Atlanta", "Falcons", "ATL", "NFC", "South", 1),
    NflTeamInfo("Carolina", "Panthers", "CAR", "NFC", "South", 29),
    NflTeamInfo("New Orleans", "Saints", "NO", "NFC", "South", 18),
    NflTeamInfo("Tampa Bay", "Buccaneers", "TB", "NFC", "South", 27),
    NflTeamInfo("Arizona", "Cardinals", "ARI", "NFC", "West", 22),
    NflTeamInfo("Los Angeles", "Rams", "LAR", "NFC", "West", 14),
    NflTeamInfo("San Francisco", "49ers", "SF", "NFC", "West", 25),
    NflTeamInfo("Seattle", "Seahawks", "SEA", "NFC", "West", 26),
]

_BY_ESPN_ID = {t.espn_id: t for t in TEAMS}
_BY_ABBR = {t.abbreviation: t for t in TEAMS}


def team_by_espn_id(espn_id: int) -> NflTeamInfo | None:
    return _BY_ESPN_ID.get(espn_id)


def team_by_abbreviation(abbreviation: str) -> NflTeamInfo | None:
    return _BY_ABBR.get(abbreviation)


def teams_in_division(conference: str, division: str) -> list[NflTeamInfo]:
    return sorted(
        (t for t in TEAMS if t.conference == conference and t.division == division),
        key=lambda t: t.name,
    )
