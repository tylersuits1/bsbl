"""Data holders for NCAAF (college football) game state — mirrors the
shape of BoxScore/TeamSide but with quarters instead of innings, an AP
rank instead of a batting order, and conference standings/game leaders
standing in for "batting order" and "player stats" since football has
neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import GameStatus, NextGameInfo


@dataclass
class NcaafTeamSide:
    name: str
    city: str
    abbreviation: str
    score: int = 0
    record: str = ""
    ap_rank: int | None = None

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}".strip()


@dataclass
class NcaafGameLeader:
    category: str
    player_name: str
    position: str
    stat_line: str


@dataclass
class NcaafStandingEntry:
    team_name: str
    overall_record: str
    conference_record: str

    @property
    def conference_wins(self) -> int:
        parts = self.conference_record.split("-")
        return int(parts[0]) if parts and parts[0].isdigit() else 0

    @property
    def conference_losses(self) -> int:
        parts = self.conference_record.split("-")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0


@dataclass
class NcaafBoxScore:
    home: NcaafTeamSide
    away: NcaafTeamSide
    away_quarters: list[str | None]
    home_quarters: list[str | None]
    status: GameStatus

    # ESPN's own status text (e.g. "3rd Quarter", "Halftime", "Final") —
    # football clock/quarter state doesn't map cleanly onto the baseball
    # inning-half/inning-number pair, so this is shown as-is.
    status_detail: str

    venue: str
    weather: str
    scheduled_start: datetime | None = None
    next_game: NextGameInfo | None = None
    followed_team_record: str = ""
    away_leaders: list[NcaafGameLeader] = field(default_factory=list)
    home_leaders: list[NcaafGameLeader] = field(default_factory=list)
    division_standings: list[NcaafStandingEntry] = field(default_factory=list)
    money_line: str = ""
