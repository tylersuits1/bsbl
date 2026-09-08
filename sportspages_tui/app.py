"""SportsPages TUI — a newspaper-styled terminal client for following
MLB games, in the spirit of Newsboat: launch into a scrollable page for
your followed teams, arrow left/right between them, arrow up/down
through the news, single-letter hotkeys for everything else.
"""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Union

import httpx
from rich.console import Group
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import ListItem, ListView, Static

from . import config, mlb_teams
from .date_format import format_full_date
from .mlb_api import MlbStatsError, MlbStatsService, headlines_for_team
from .models import BoxScore, Headline, PlayerStat
from .news_sources import fetch_bing_news, fetch_google_news, merge_headlines
from .rendering import (
    batting_order_columns,
    detail_lines,
    inning_table,
    masthead,
    matchup_line,
    player_stats_table,
    refresh_status_line,
    status_line,
)
from .screens.help import HelpScreen
from .screens.team_picker import TeamPickerScreen

LIVE_REFRESH_SECONDS = 20


class _PlayersSentinel:
    """Stands in for a "team" for the one aggregate Players page — there's
    no single team behind it, just whichever players you're tracking.
    """

    abbreviation = "PLAYERS"
    full_name = "Players"


_PLAYERS_SENTINEL = _PlayersSentinel()


@dataclass
class FollowedTeam:
    """One entry in the followed-teams list — an MLB team, or the one
    aggregate Players page.
    """

    info: Union[mlb_teams.TeamInfo, _PlayersSentinel]

    @property
    def abbreviation(self) -> str:
        return self.info.abbreviation

    @property
    def full_name(self) -> str:
        return self.info.full_name

    @property
    def is_players_page(self) -> bool:
        return isinstance(self.info, _PlayersSentinel)


class HeadlineItem(ListItem):
    def __init__(self, headline: Headline, *, label: str | None = None) -> None:
        title = f"{label}: {headline.title}" if label else headline.title
        body = Group(
            f"[bold]{title}[/bold]",
            f"[italic dim]{headline.byline} | {headline.time_ago}[/italic dim]",
        )
        super().__init__(Static(body))
        self.url = headline.url


class MainScreen(VerticalScroll):
    """The whole scrollable page for one followed team — masthead down
    through headlines. A plain container (not a Screen) so the App can
    swap its content per team without pushing/popping screens.
    """

    can_focus = True

    def __init__(self) -> None:
        super().__init__(id="body-scroll")
        self.show_stats = False    # player stats (s)
        self.show_batting = False  # batting order (b)

    def compose(self) -> ComposeResult:
        yield Static(id="masthead")
        yield Static(id="summary")
        yield Static(id="innings")
        yield Static(id="batting-section", classes="section")
        yield Static(id="stats-section", classes="section")
        with Vertical(id="headlines-section", classes="section"):
            yield Static("[bold]HEADLINES[/bold]", id="headlines-title")
            yield ListView(id="headlines-list")

    def render_team(
        self,
        team: mlb_teams.TeamInfo,
        box: BoxScore,
        headlines: list[Headline],
        stats: list[PlayerStat],
        *,
        last_updated: datetime | None,
        paused: bool,
        page: int,
        total_pages: int,
    ) -> None:
        self._show_batting_stats_sections()

        today = format_full_date(datetime.now())
        self.query_one("#masthead", Static).update(
            masthead(team.full_name, box.followed_team_record, today, page=page, total_pages=total_pages)
        )

        lines = [matchup_line(box), status_line(box), *detail_lines(box), "", refresh_status_line(last_updated, paused)]
        self.query_one("#summary", Static).update(Group(*lines))

        self.query_one("#innings", Static).update(inning_table(box))

        # Batting/Stats headers are always shown — even collapsed — so the
        # page makes clear these sections exist above the headlines,
        # rather than only appearing once toggled on.
        batting_widget = self.query_one("#batting-section", Static)
        if self.show_batting:
            batting_widget.update(Group("[bold]BATTING (-b)[/bold]", "", batting_order_columns(box)))
        else:
            batting_widget.update("[bold]BATTING (+b)[/bold]")

        stats_widget = self.query_one("#stats-section", Static)
        if self.show_stats:
            if stats:
                stats_widget.update(Group(
                    "[bold]STATS (-s)[/bold]", "",
                    player_stats_table(stats, pitchers=False), "",
                    player_stats_table(stats, pitchers=True),
                ))
            else:
                stats_widget.update("[bold]STATS (-s)[/bold]\n\n[italic]No stats available.[/italic]")
        else:
            stats_widget.update("[bold]STATS (+s)[/bold]")

        self._render_headlines(headlines)

    def render_players_page(
        self,
        stats: list[PlayerStat],
        player_headlines: list[tuple[str, Headline]],
        *,
        last_updated: datetime | None,
        paused: bool,
        page: int,
        total_pages: int,
    ) -> None:
        """The one aggregate page for every tracked player — unlike every
        other page, this isn't one team's box score, so the batting/stats
        sections (not applicable here) are hidden rather than repurposed.
        """
        today = format_full_date(datetime.now())
        self.query_one("#masthead", Static).update(
            masthead("Players", "", today, page=page, total_pages=total_pages)
        )

        count_line = (
            f"Tracking {len(stats)} player{'s' if len(stats) != 1 else ''}"
            if stats else "No players tracked yet — press 'a' then select PLAYERS to search"
        )
        lines = [count_line, "", refresh_status_line(last_updated, paused)]
        self.query_one("#summary", Static).update(Group(*lines))

        hitters = [s for s in stats if not s.is_pitcher]
        pitchers = [s for s in stats if s.is_pitcher]
        parts = []
        if hitters:
            parts += [player_stats_table(stats, pitchers=False), ""]
        if pitchers:
            parts += [player_stats_table(stats, pitchers=True), ""]
        self.query_one("#innings", Static).update(Group(*parts) if parts else "")

        self.query_one("#batting-section", Static).display = False
        self.query_one("#stats-section", Static).display = False

        headline_list = self.query_one("#headlines-list", ListView)
        headline_list.clear()
        if player_headlines:
            for name, headline in player_headlines:
                headline_list.append(HeadlineItem(headline, label=name))
        else:
            headline_list.append(ListItem(Static("[italic dim]No headlines available.[/italic dim]"), disabled=True))
        headline_list.focus()

    def _show_batting_stats_sections(self) -> None:
        """The Players page hides these (not applicable); every other
        page needs them visible again after a visit to Players.
        """
        self.query_one("#batting-section", Static).display = True
        self.query_one("#stats-section", Static).display = True

    def _render_headlines(self, headlines: list[Headline]) -> None:
        headline_list = self.query_one("#headlines-list", ListView)
        headline_list.clear()
        if headlines:
            for h in headlines[:5]:
                headline_list.append(HeadlineItem(h))
        else:
            headline_list.append(ListItem(Static("[italic dim]No headlines available.[/italic dim]"), disabled=True))
        headline_list.focus()


class SportsPagesApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "The Sports Pages"

    BINDINGS = [
        ("left", "prev_team", "Prev Team"),
        ("right", "next_team", "Next Team"),
        ("up", "scroll_up", "Scroll Up"),
        ("down", "scroll_down", "Scroll Down"),
        ("s", "toggle_stats", "Stats"),
        ("b", "toggle_batting", "Batting"),
        ("r", "refresh_now", "Refresh"),
        ("a", "manage_teams", "Follow"),
        ("p", "toggle_live", "Pause Live"),
        ("d", "toggle_dark", "Theme"),
        ("question_mark", "show_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._http = httpx.AsyncClient(timeout=12.0)
        self.stats_service = MlbStatsService(self._http)
        self.current_index = 0
        self.teams: list[FollowedTeam] = []
        self.last_updated: datetime | None = None
        self.live_paused = False
        self._live_timer = None
        self._body: MainScreen | None = None
        self.theme = "ansi-dark"

    def compose(self) -> ComposeResult:
        self._body = MainScreen()
        yield self._body
        yield Static(id="hint-bar")

    async def on_mount(self) -> None:
        self._update_hints()
        self._load_teams()
        if not self.teams:
            await self._open_picker()
        else:
            self._start_live_timer()
            self.load_current_team()

    def _load_teams(self) -> None:
        entries = config.load_favorites()
        teams: list[FollowedTeam] = []
        for sport, abbr in entries:
            if sport != "MLB":
                continue
            t = mlb_teams.team_by_abbreviation(abbr)
            if t:
                teams.append(FollowedTeam(t))
        if config.load_players():
            teams.append(FollowedTeam(_PLAYERS_SENTINEL))
        self.teams = teams
        if self.current_index >= len(self.teams):
            self.current_index = max(0, len(self.teams) - 1)

    async def _open_picker(self) -> None:
        await self.push_screen(TeamPickerScreen(), callback=lambda _: self._on_picker_closed())

    def _on_picker_closed(self) -> None:
        self._load_teams()
        if self.teams:
            self._start_live_timer()
            self.load_current_team()

    def _start_live_timer(self) -> None:
        if self._live_timer:
            self._live_timer.stop()
        self._live_timer = self.set_interval(LIVE_REFRESH_SECONDS, self._auto_refresh)

    @property
    def current_team(self) -> FollowedTeam | None:
        if not self.teams:
            return None
        return self.teams[self.current_index]

    @work(exclusive=True)
    async def load_current_team(self) -> None:
        followed = self.current_team
        if not followed or not self._body:
            return
        if followed.is_players_page:
            await self._load_players_page()
            return
        team = followed.info
        try:
            box = await self.stats_service.fetch_game_for_team(team)
            stats = await self.stats_service.fetch_player_stats(team) if self._body.show_stats else []
        except MlbStatsError as e:
            self.notify(f"Could not load {team.full_name}: {e}", severity="error")
            return

        web_headlines = await self._fetch_web_headlines(f"{team.full_name} MLB")
        merged = merge_headlines([web_headlines])
        relevant = headlines_for_team(merged, team_city=team.city, team_name=team.name)

        self.last_updated = datetime.now().astimezone()
        self._body.render_team(
            team, box, relevant, stats,
            last_updated=self.last_updated, paused=self.live_paused,
            page=self.current_index + 1, total_pages=len(self.teams),
        )
        if box.status.value == "FINAL" and self._live_timer:
            self._live_timer.pause()

    async def _load_players_page(self) -> None:
        players = config.load_players()
        stats: list[PlayerStat] = []
        player_headlines: list[tuple[str, Headline]] = []
        for player in players:
            person_id = player.get("player_id")
            name = player.get("name", "?")
            position = player.get("position", "")
            try:
                stat = await self.stats_service.fetch_player_stat(person_id, name, position)
            except MlbStatsError:
                stat = PlayerStat(name=name, position=position, is_pitcher=position == "P", has_stats=False)
            stats.append(stat)

            headline = await self._fetch_player_headline(name)
            if headline:
                player_headlines.append((name, headline))

        self.last_updated = datetime.now().astimezone()
        self._body.render_players_page(
            stats, player_headlines,
            last_updated=self.last_updated, paused=self.live_paused,
            page=self.current_index + 1, total_pages=len(self.teams),
        )

    async def _fetch_player_headline(self, name: str) -> Headline | None:
        if not name:
            return None
        web_headlines = await self._fetch_web_headlines(f"{name} MLB")
        merged = merge_headlines([web_headlines])
        return merged[0] if merged else None

    async def _fetch_web_headlines(self, query: str) -> list[Headline]:
        """Google News + Bing News RSS, scoped to this team — plain
        public feeds, not an internal/undocumented API.
        """
        try:
            google, bing = await fetch_google_news(self._http, query), await fetch_bing_news(self._http, query)
            return [*google, *bing]
        except Exception:
            return []

    def _auto_refresh(self) -> None:
        if not self.live_paused:
            self.load_current_team()

    def _update_hints(self) -> None:
        # Only the hotkeys someone reaches for constantly. Stats (s),
        # Batting (b), Follow (a), Theme (d) and Pause Live (p) still
        # work exactly as before — they're documented in the '?' help
        # screen instead of taking up space here every time.
        parts = [
            ("←/→", "Teams"),
            ("↑/↓", "Headlines"),
            ("enter", "Open"),
            ("r", "Refresh"),
            ("?", "Help"),
            ("q", "Quit"),
        ]
        text = "   ".join(f"[reverse] {key} [/reverse] {label}" for key, label in parts)
        self.query_one("#hint-bar", Static).update(text)

    @on(ListView.Selected, "#headlines-list")
    def on_headline_selected(self, event: ListView.Selected) -> None:
        url = getattr(event.item, "url", None)
        if url:
            webbrowser.open(url)

    # -- actions -------------------------------------------------------

    def action_prev_team(self) -> None:
        if not self.teams:
            return
        self.current_index = (self.current_index - 1) % len(self.teams)
        self.load_current_team()

    def action_next_team(self) -> None:
        if not self.teams:
            return
        self.current_index = (self.current_index + 1) % len(self.teams)
        self.load_current_team()

    def action_scroll_up(self) -> None:
        if self._body:
            self._body.scroll_up()

    def action_scroll_down(self) -> None:
        if self._body:
            self._body.scroll_down()

    def action_toggle_stats(self) -> None:
        if not self._body:
            return
        self._body.show_stats = not self._body.show_stats
        self.load_current_team()

    def action_toggle_batting(self) -> None:
        if not self._body:
            return
        self._body.show_batting = not self._body.show_batting
        self.load_current_team()

    def action_refresh_now(self) -> None:
        self.load_current_team()

    async def action_manage_teams(self) -> None:
        await self._open_picker()

    def action_toggle_live(self) -> None:
        self.live_paused = not self.live_paused
        self.load_current_team()

    def action_toggle_dark(self) -> None:
        self.theme = "ansi-light" if self.theme == "ansi-dark" else "ansi-dark"

    async def action_show_help(self) -> None:
        await self.push_screen(HelpScreen())

    async def on_unmount(self) -> None:
        await self._http.aclose()
