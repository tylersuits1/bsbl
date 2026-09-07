"""Shared data holders for "period" sports — NCAAF, NFL, NBA — whose game
shape (quarters instead of innings, a ranking table instead of a batting
order, top-performer leaders instead of a season stat line) is otherwise
identical, unlike baseball's inning/box-score shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import GameStatus, NextGameInfo


@dataclass
class PeriodTeamSide:
    name: str
    city: str
    abbreviation: str
    score: int = 0
    record: str = ""

    # AP Top 25 rank (NCAAF only) — always None for NFL/NBA, which have
    # no equivalent national poll.
    rank: int | None = None

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}".strip()


@dataclass
class GameLeader:
    category: str
    player_name: str
    position: str
    stat_line: str


@dataclass
class StandingEntry:
    team_name: str
    overall_record: str

    # A second record column meaning whatever's most useful per sport:
    # conference record for NCAAF/NFL, games-behind for NBA. Blank when
    # the source feed doesn't carry it (e.g. early NFL season).
    secondary_record: str = ""

    @property
    def overall_wins(self) -> int:
        parts = self.overall_record.split("-")
        return int(parts[0]) if parts and parts[0].isdigit() else 0

    @property
    def overall_losses(self) -> int:
        parts = self.overall_record.split("-")
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0


@dataclass
class PeriodBoxScore:
    home: PeriodTeamSide
    away: PeriodTeamSide
    away_periods: list[str | None]
    home_periods: list[str | None]
    status: GameStatus

    # ESPN's own status text (e.g. "3rd Quarter", "Halftime", "Final") —
    # clock/period state doesn't map cleanly onto baseball's
    # inning-half/inning-number pair, so this is shown as-is.
    status_detail: str

    venue: str
    weather: str
    scheduled_start: datetime | None = None
    next_game: NextGameInfo | None = None
    followed_team_record: str = ""
    away_leaders: list[GameLeader] = field(default_factory=list)
    home_leaders: list[GameLeader] = field(default_factory=list)
    standings: list[StandingEntry] = field(default_factory=list)
    money_line: str = ""
