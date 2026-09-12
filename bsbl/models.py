"""Plain data holders for one team's game state — mirrors the shape of
the Flutter app's BoxScore/Team/PlayerStat models, adapted for the
terminal client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GameStatus(str, Enum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    POSTPONED = "POSTPONED"
    WARMUP = "WARMUP"
    SCHEDULED = "SCHEDULED"
    FINAL = "FINAL"


@dataclass
class LineScore:
    runs: int = 0
    hits: int = 0
    errors: int = 0


@dataclass
class TeamSide:
    name: str
    city: str
    abbreviation: str
    score: int = 0
    record: str = ""
    batting_order: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.city} {self.name}".strip()


@dataclass
class NextGameInfo:
    opponent: str
    venue: str
    start: datetime
    is_away: bool = False


@dataclass
class PlayerSearchResult:
    person_id: int
    name: str
    position: str
    team_abbr: str


@dataclass
class PlayerStat:
    name: str
    position: str
    is_pitcher: bool
    avg: str = ""
    home_runs: int = 0
    rbi: int = 0
    wins_losses: str = ""
    era: str = ""
    innings_pitched: str = ""
    has_stats: bool = True


@dataclass
class Headline:
    title: str
    byline: str
    time_ago: str
    url: str
    published_at: datetime


@dataclass
class BoxScore:
    home: TeamSide
    away: TeamSide
    home_line: LineScore
    away_line: LineScore
    away_innings: list[int | None]
    home_innings: list[int | None]
    inning_half: str
    inning: int
    venue: str
    weather: str
    home_pitcher: str
    home_pitcher_ip: str
    away_pitcher: str
    away_pitcher_ip: str
    status: GameStatus
    scheduled_start: datetime | None = None
    next_game: NextGameInfo | None = None
    followed_team_record: str = ""

    # Live at-bat state — populated only while status is LIVE/DELAYED.
    balls: int = 0
    strikes: int = 0
    outs: int = 0
    at_bat_batter: str = ""
    at_bat_pitcher: str = ""
    on_first: str = ""
    on_second: str = ""
    on_third: str = ""
    last_pitch_type: str = ""
    last_pitch_result: str = ""
    last_pitch_outcome: str = ""
