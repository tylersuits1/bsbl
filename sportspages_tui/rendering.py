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
from .period_models import GameLeader, PeriodBoxScore, StandingEntry

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


def last_name(full_name: str) -> str:
    parts = [p for p in full_name.strip().split(" ") if p]
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


def detail_lines(box: BoxScore) -> list[str]:
    lines = []
    parts = []
    if box.venue:
        parts.append(box.venue)
    if box.weather:
        parts.append(box.weather)
    if box.money_line:
        parts.append(f"ML {box.money_line}")
    if parts:
        lines.append("  |  ".join(parts))

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


def period_matchup_line(box: PeriodBoxScore) -> Text:
    away, home = box.away, box.home
    away_label = f"#{away.rank} {away.name}" if away.rank else away.name
    home_label = f"#{home.rank} {home.name}" if home.rank else home.name
    if box.status == GameStatus.SCHEDULED and not box.away_periods and not box.home_periods:
        return Text(f"{away_label} @ {home_label}", style="bold")
    return Text(f"{away_label} {away.score} | {home_label} {home.score}", style="bold")


def period_status_line(box: PeriodBoxScore) -> Text:
    line = Text()
    line.append_text(status_text(box.status))
    detail = box.status_detail.strip()
    if detail and detail.lower() != box.status.value.lower():
        line.append(f"  {detail.upper()}")
    return line


def period_detail_lines(box: PeriodBoxScore) -> list[str]:
    lines = []
    parts = []
    if box.venue:
        parts.append(box.venue)
    if box.weather:
        parts.append(box.weather)
    if box.money_line:
        parts.append(f"ML {box.money_line}")
    if parts:
        lines.append("  |  ".join(parts))

    if box.status == GameStatus.FINAL and box.next_game:
        ng = box.next_game
        prefix = "@" if ng.is_away else "vs "
        lines.append("")
        lines.append(f"UP NEXT: {prefix}{ng.opponent} · {format_short_datetime(ng.start)}")

    return lines


def quarter_table(box: PeriodBoxScore) -> Table:
    q_count = max(len(box.away_periods), len(box.home_periods), 4)
    table = Table(show_header=True, header_style="bold", box=_box_style(), pad_edge=False)
    table.add_column("", width=5)
    for i in range(1, q_count + 1):
        label = str(i) if i <= 4 else ("OT" if i == 5 else f"{i - 4}OT")
        table.add_column(label, justify="center", width=4)
    table.add_column("T", justify="center", width=4, style="bold")

    def row(label: str, periods: list, total: int) -> list[str]:
        cells = [label]
        for i in range(q_count):
            value = periods[i] if i < len(periods) else None
            cells.append("–" if value in (None, "") else str(value))
        cells.append(str(total))
        return cells

    table.add_row(*row(box.away.abbreviation or "AWAY", box.away_periods, box.away.score))
    table.add_row(*row(box.home.abbreviation or "HOME", box.home_periods, box.home.score))
    return table


def standings_table(entries: list[StandingEntry], *, secondary_label: str = "CONF") -> Table:
    table = Table(show_header=True, header_style="bold", box=_box_style(), pad_edge=False, expand=True)
    table.add_column("TEAM", ratio=3)
    table.add_column(secondary_label, justify="center", ratio=1)
    table.add_column("OVERALL", justify="center", ratio=1)
    for e in entries:
        table.add_row(e.team_name, e.secondary_record, e.overall_record)
    return table


def leaders_group(
    away_leaders: list[GameLeader], home_leaders: list[GameLeader], away_label: str, home_label: str
) -> Table:
    def block(label: str, leaders: list[GameLeader]) -> Group:
        lines = [Text(label, style="bold")]
        if not leaders:
            lines.append(Text("No leaders reported", style="italic dim"))
        else:
            for leader in leaders:
                lines.append(Text(f"{leader.category}: {leader.player_name} ({leader.position}) — {leader.stat_line}"))
        return Group(*lines)

    table = Table.grid(padding=(0, 3))
    table.add_column()
    table.add_column()
    table.add_row(block(away_label, away_leaders), block(home_label, home_leaders))
    return table


def masthead(team_name: str, record: str, today: str, *, page: int, total_pages: int) -> Group:
    date_line = Align.center(Text(f"THE SPORTS PAGES · {today}", style="dim"))
    name_line = Align.center(Text(team_name.upper(), style="bold"))
    page_text = f"Page {page}/{total_pages}"
    below_name = Text.assemble((record, "dim")) if record else Text()
    if record:
        below_name.append("   ·   ", style="dim")
    below_name.append(page_text, style="dim")
    below_name_line = Align.center(below_name)
    rule = Rule(style="bold", characters="═")
    return Group(date_line, name_line, below_name_line, rule)
