"""Pure rendering functions — build Rich renderables from a BoxScore /
headline list. Kept separate from the Textual app so the newspaper-style
layout can be read (and tested) without spinning up a screen.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .date_format import format_clock_time, format_short_datetime, ordinal_inning
from .models import BoxScore, GameStatus, PlayerStat

_STATUS_STYLE = {
    GameStatus.LIVE: "bold red",
    GameStatus.DELAYED: "bold yellow",
    GameStatus.POSTPONED: "bold red",
    GameStatus.WARMUP: "bold blue",
    GameStatus.SCHEDULED: "dim bold",
    GameStatus.FINAL: "bold",
}


def status_text(status: GameStatus) -> Text:
    return Text(status.value, style=_STATUS_STYLE.get(status, "bold"))


_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def last_name(full_name: str) -> str:
    """The last "real" name token — skips generational suffixes like
    "Jr." or "III" so e.g. "Ronald Acuña Jr." shows as "Acuña", not "Jr.".
    """
    parts = [p for p in full_name.strip().split(" ") if p]
    while len(parts) > 1 and parts[-1].lower().rstrip(".") in _NAME_SUFFIXES:
        parts.pop()
    return parts[-1] if parts else full_name


def matchup_line(box: BoxScore) -> Text:
    away, home = box.away, box.home
    if box.status in (GameStatus.SCHEDULED, GameStatus.WARMUP) and not box.away_innings and not box.home_innings:
        return Text(f"{away.name} @ {home.name}", style="bold")
    return Text(f"{away.name} {away.score} | {home.name} {home.score}", style="bold")


def status_line(box: BoxScore) -> Text:
    line = Text()
    line.append_text(status_text(box.status))
    if box.status == GameStatus.SCHEDULED and box.scheduled_start:
        line.append(f"  {format_short_datetime(box.scheduled_start)}")
    elif box.status in (GameStatus.LIVE, GameStatus.DELAYED):
        line.append(f"  {box.inning_half} of the {ordinal_inning(box.inning)} inning".upper())
    return line


def location_weather_line(box: BoxScore) -> str | None:
    parts = []
    if box.venue:
        parts.append(box.venue)
    if box.weather:
        parts.append(box.weather)
    return "  |  ".join(parts) if parts else None


def pitching_lines(box: BoxScore) -> list[str]:
    """The season/box-score pitching line — shown under the box score,
    not alongside the live at-bat state (see live_at_bat_section).
    """
    lines = []
    if box.status in (GameStatus.SCHEDULED, GameStatus.WARMUP):
        if box.away_pitcher and box.home_pitcher:
            lines.append(f"Probable Pitchers: {last_name(box.away_pitcher)} vs {last_name(box.home_pitcher)}")
    else:
        lines.append(
            f"Pitching: {last_name(box.away_pitcher)} ({box.away.abbreviation}) {box.away_pitcher_ip}  |  "
            f"{last_name(box.home_pitcher)} ({box.home.abbreviation}) {box.home_pitcher_ip}"
        )

    if box.status == GameStatus.FINAL and box.next_game:
        ng = box.next_game
        prefix = "@" if ng.is_away else "vs "
        lines.append("")
        lines.append(f"UP NEXT: {prefix}{ng.opponent} · {format_short_datetime(ng.start)}")

    return lines


def bases_line(box: BoxScore) -> str:
    """'Bases empty', 'Bases loaded', or 'Ozzie on first, Acuña on
    second' listing whoever's actually on base.
    """
    if box.on_first and box.on_second and box.on_third:
        return "Bases loaded"
    parts = []
    if box.on_first:
        parts.append(f"{last_name(box.on_first)} on first")
    if box.on_second:
        parts.append(f"{last_name(box.on_second)} on second")
    if box.on_third:
        parts.append(f"{last_name(box.on_third)} on third")
    return ", ".join(parts) if parts else "Bases empty"


def live_at_bat_section(box: BoxScore) -> Group | None:
    """Current batter/pitcher, ball-strike count and outs, and who's on
    base — only shown while a game is actually in progress.
    """
    if box.status not in (GameStatus.LIVE, GameStatus.DELAYED):
        return None

    matchup = Text()
    if box.at_bat_batter:
        matchup.append("AT BAT ", style="bold")
        matchup.append(last_name(box.at_bat_batter))
    if box.at_bat_pitcher:
        if box.at_bat_batter:
            matchup.append("   ")
        matchup.append("PITCHING ", style="bold")
        matchup.append(last_name(box.at_bat_pitcher))

    count = Text()
    count.append(f"{box.balls}-{box.strikes}", style="bold")
    count.append(" COUNT   ", style="dim")
    count.append(str(box.outs), style="bold")
    count.append(" OUT" if box.outs == 1 else " OUTS", style="dim")

    parts = []
    if matchup.plain:
        parts.append(matchup)
    parts.append(count)
    parts.append(bases_line(box))
    return Group(*parts)


def inning_table(box: BoxScore) -> Table:
    inning_count = max(len(box.away_innings), len(box.home_innings), 9)
    table = Table(show_header=True, header_style="bold", box=_box_style(), pad_edge=False)
    table.add_column("", width=5)
    for i in range(1, inning_count + 1):
        table.add_column(str(i), justify="center", width=3)
    for label in ("R", "H", "E"):
        table.add_column(label, justify="center", width=3, style="bold")

    def row(label: str, innings: list, line) -> list[str]:
        cells = [label]
        for i in range(inning_count):
            value = innings[i] if i < len(innings) else None
            cells.append("–" if value is None else str(value))
        cells += [str(line.runs), str(line.hits), str(line.errors)]
        return cells

    table.add_row(*row(box.away.abbreviation or "AWAY", box.away_innings, box.away_line))
    table.add_row(*row(box.home.abbreviation or "HOME", box.home_innings, box.home_line))
    return table


def _box_style():
    from rich import box as rich_box
    return rich_box.SQUARE


def batting_order_columns(box: BoxScore) -> Table:
    table = Table.grid(padding=(0, 3))
    table.add_column()
    table.add_column()
    away_col = _order_column(box.away.city.upper() or box.away.abbreviation, box.away.batting_order)
    home_col = _order_column(box.home.city.upper() or box.home.abbreviation, box.home.batting_order)
    table.add_row(away_col, home_col)
    return table


def _order_column(title: str, order: list[str]) -> Group:
    lines = [Text(title, style="bold")]
    if not order:
        lines.append(Text("Not yet announced", style="italic dim"))
    else:
        for i, player in enumerate(order, start=1):
            lines.append(Text(f"{i}. {player}"))
    return Group(*lines)


def player_stats_table(stats: list[PlayerStat], *, pitchers: bool) -> Table:
    rows = [s for s in stats if s.is_pitcher == pitchers]
    table = Table(show_header=True, header_style="bold", box=_box_style(), pad_edge=False, expand=True)
    if pitchers:
        table.add_column("PITCHERS", ratio=3)
        table.add_column("W-L", justify="center", ratio=1)
        table.add_column("ERA", justify="center", ratio=1)
        table.add_column("IP", justify="center", ratio=1)
        for p in rows:
            table.add_row(
                f"{p.name} ({p.position})",
                p.wins_losses if p.has_stats else "—",
                p.era if p.has_stats else "—",
                p.innings_pitched if p.has_stats else "—",
            )
    else:
        table.add_column("HITTERS", ratio=3)
        table.add_column("AVG", justify="center", ratio=1)
        table.add_column("HR", justify="center", ratio=1)
        table.add_column("RBI", justify="center", ratio=1)
        for p in rows:
            table.add_row(
                f"{p.name} ({p.position})",
                p.avg if p.has_stats else "—",
                str(p.home_runs) if p.has_stats else "—",
                str(p.rbi) if p.has_stats else "—",
            )
    return table


def refresh_status_line(last_updated, paused: bool) -> Text:
    """'⏸ LIVE UPDATES PAUSED  ·  Last updated 3:45:12 PM' — always shows
    when data was last fetched; prepends a paused indicator whenever
    live auto-refresh is off, so it's clear stale data isn't about to
    silently update.
    """
    line = Text()
    if paused:
        line.append("⏸ PAUSED", style="bold yellow")
        line.append("  ·  ", style="dim")
    if last_updated is not None:
        line.append(f"Last updated {format_clock_time(last_updated)}", style="dim italic")
    else:
        line.append("Not yet updated", style="dim italic")
    return line


def masthead(team_name: str, record: str, today: str, *, page: int, total_pages: int, version: str = "") -> Group:
    bsbl_label = f"BSBL v{version}" if version else "BSBL"
    date_line = Align.center(Text(f"{bsbl_label} · {today}", style="dim"))
    name_line = Align.center(Text(team_name.upper(), style="bold"))
    page_text = f"Page {page}/{total_pages}"
    below_name = Text.assemble((record, "dim")) if record else Text()
    if record:
        below_name.append("   ·   ", style="dim")
    below_name.append(page_text, style="dim")
    below_name_line = Align.center(below_name)
    rule = Rule(style="bold", characters="═")
    return Group(date_line, name_line, below_name_line, rule)
