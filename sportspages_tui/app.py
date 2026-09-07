"""SportsPages TUI — a newspaper-styled terminal client for following
MLB, NCAAF, NFL, and NBA games, in the spirit of Newsboat: launch into a
scrollable page for your followed teams, arrow left/right between them,
arrow up/down through the news, single-letter hotkeys for everything
else.
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

from . import config, mlb_teams, nba_teams, ncaaf_teams, nfl_teams
from . import espn_period_sport as common
from .date_format import format_full_date
from .mlb_api import MlbNewsService, MlbStatsError, MlbStatsService, headlines_for_team
from .models import BoxScore, Headline, PlayerStat
from .nba_api import NbaNewsService, NbaStatsService
from .ncaaf_api import NcaafNewsService, NcaafStatsService
from .nfl_api import NflNewsService, NflStatsService
from .news_sources import fetch_bing_news, fetch_google_news, merge_headlines
from .period_models import PeriodBoxScore
from .rendering import (
    batting_order_columns,
    detail_lines,
    inning_table,
    leaders_group,
    masthead,
    matchup_line,
    period_detail_lines,
    period_matchup_line,
    period_status_line,
    player_stats_table,
    quarter_table,
    refresh_status_line,
    standings_table,
    status_line,
)
from .screens.help import HelpScreen
from .screens.team_picker import TeamPickerScreen

LIVE_REFRESH_SECONDS = 20

# Team-lookup module per sport — every one exposes team_by_abbreviation().
_TEAM_MODULES = {
    "MLB": mlb_teams,
    "NCAAF": ncaaf_teams,
    "NFL": nfl_teams,
    "NBA": nba_teams,
}

# "Period" sports share one PeriodBoxScore shape (quarters, standings,
# game leaders) via espn_period_sport, unlike MLB's innings/box-score
# shape. Each entry: (stats service class, news service class, query
# suffix for web headline search, standings' secondary-column label).
_PERIOD_SPORTS = {
    "NCAAF": (NcaafStatsService, NcaafNewsService, "college football", "CONF"),
    "NFL": (NflStatsService, NflNewsService, "NFL", "CONF"),
    "NBA": (NbaStatsService, NbaNewsService, "NBA", "GB"),
}


@dataclass
class FollowedTeam:
    """One entry in the followed-teams list — an MLB, NCAAF, NFL, or NBA
    team, normalized behind the same interface so the app can treat the
    list as sport-agnostic wherever it doesn't need to branch.
    """

    sport: str  # "MLB" | "NCAAF" | "NFL" | "NBA"
    info: Union[mlb_teams.TeamInfo, ncaaf_teams.NcaafTeamInfo, nfl_teams.NflTeamInfo, nba_teams.NbaTeamInfo]

    @property
    def abbreviation(self) -> str:
        return self.info.abbreviation

    @property
    def full_name(self) -> str:
        return self.info.full_name


class HeadlineItem(ListItem):
    def __init__(self, headline: Headline) -> None:
        body = Group(
            f"[bold]{headline.title}[/bold]",
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
        self.show_stats = False       # MLB: player stats (s)
        self.show_batting = False     # MLB: batting order (b)
        self.show_standings = False   # NCAAF/NFL/NBA: standings (s)
        self.show_leaders = False     # NCAAF/NFL/NBA: game leaders (l)

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

    def render_period_team(
        self,
        team,
        box: PeriodBoxScore,
        headlines: list[Headline],
        *,
        last_updated: datetime | None,
        paused: bool,
        page: int,
        total_pages: int,
        standings_secondary_label: str = "CONF",
    ) -> None:
        """Shared renderer for NCAAF/NFL/NBA — identical box-score shape
        (quarters, standings, game leaders) regardless of which of the
        three it is; only the standings table's secondary column
        (conference record vs. games-behind) differs.
        """
        today = format_full_date(datetime.now())
        self.query_one("#masthead", Static).update(
            masthead(team.full_name, box.followed_team_record, today, page=page, total_pages=total_pages)
        )

        lines = [
            period_matchup_line(box), period_status_line(box), *period_detail_lines(box),
            "", refresh_status_line(last_updated, paused),
        ]
        self.query_one("#summary", Static).update(Group(*lines))

        self.query_one("#innings", Static).update(quarter_table(box))

        standings_widget = self.query_one("#batting-section", Static)
        if self.show_standings:
            if box.standings:
                standings_widget.update(Group(
                    "[bold]STANDINGS (-s)[/bold]", "",
                    standings_table(box.standings, secondary_label=standings_secondary_label),
                ))
            else:
                standings_widget.update("[bold]STANDINGS (-s)[/bold]\n\n[italic]No standings available.[/italic]")
        else:
            standings_widget.update("[bold]STANDINGS (+s)[/bold]")

        leaders_widget = self.query_one("#stats-section", Static)
        if self.show_leaders:
            if box.away_leaders or box.home_leaders:
                leaders_widget.update(Group(
                    "[bold]LEADERS (-l)[/bold]", "",
                    leaders_group(
                        box.away_leaders, box.home_leaders,
                        box.away.abbreviation or "AWAY", box.home.abbreviation or "HOME",
                    ),
                ))
            else:
                leaders_widget.update("[bold]LEADERS (-l)[/bold]\n\n[italic]No leaders reported.[/italic]")
        else:
            leaders_widget.update("[bold]LEADERS (+l)[/bold]")

        self._render_headlines(headlines)

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
        ("l", "toggle_leaders", "Leaders"),
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
        self.news_service = MlbNewsService(self._http)
        # sport -> (stats service, news service) for the three period
        # sports, all sharing the same fetch/render shape.
        self.period_services = {
            sport: (stats_cls(self._http), news_cls(self._http))
            for sport, (stats_cls, news_cls, _, _) in _PERIOD_SPORTS.items()
        }
        self.current_index = 0
        self.teams: list[FollowedTeam] = []
        self.league_headlines: list[Headline] = []
        self.period_headlines: dict[str, list[Headline]] = {sport: [] for sport in _PERIOD_SPORTS}
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
        self._refresh_headlines()

    def _load_teams(self) -> None:
        entries = config.load_favorites()
        teams: list[FollowedTeam] = []
        for sport, abbr in entries:
            module = _TEAM_MODULES.get(sport)
            if not module:
                continue
            t = module.team_by_abbreviation(abbr)
            if t:
                teams.append(FollowedTeam(sport, t))
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
        self._refresh_headlines()

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
        if followed.sport == "MLB":
            await self._load_mlb_team(followed.info)
        else:
            await self._load_period_team(followed.sport, followed.info)

    async def _load_mlb_team(self, team: mlb_teams.TeamInfo) -> None:
        try:
            box = await self.stats_service.fetch_game_for_team(team)
            stats = await self.stats_service.fetch_player_stats(team) if self._body.show_stats else []
        except MlbStatsError as e:
            self.notify(f"Could not load {team.full_name}: {e}", severity="error")
            return

        web_headlines = await self._fetch_web_headlines(f"{team.full_name} MLB")
        merged = merge_headlines([self.league_headlines, web_headlines])
        relevant = headlines_for_team(merged, team_city=team.city, team_name=team.name)

        self.last_updated = datetime.now().astimezone()
        self._body.render_team(
            team, box, relevant, stats,
            last_updated=self.last_updated, paused=self.live_paused,
            page=self.current_index + 1, total_pages=len(self.teams),
        )
        if box.status.value == "FINAL" and self._live_timer:
            self._live_timer.pause()

    async def _load_period_team(self, sport: str, team) -> None:
        stats_service, _ = self.period_services[sport]
        _, _, query_suffix, standings_label = _PERIOD_SPORTS[sport]
        try:
            box = await stats_service.fetch_game_for_team(team)
        except common.PeriodStatsError as e:
            self.notify(f"Could not load {team.full_name}: {e}", severity="error")
            return

        web_headlines = await self._fetch_web_headlines(f"{team.full_name} {query_suffix}")
        merged = merge_headlines([self.period_headlines[sport], web_headlines])
        relevant = headlines_for_team(merged, team_city=team.city, team_name=team.name)

        self.last_updated = datetime.now().astimezone()
        self._body.render_period_team(
            team, box, relevant,
            last_updated=self.last_updated, paused=self.live_paused,
            page=self.current_index + 1, total_pages=len(self.teams),
            standings_secondary_label=standings_label,
        )
        if box.status.value == "FINAL" and self._live_timer:
            self._live_timer.pause()

    async def _fetch_web_headlines(self, query: str) -> list[Headline]:
        """Google News + Bing News, scoped to this team, as extra sources
        alongside ESPN's general feed — without these, a team with no
        stories in ESPN's top-12 general feed shows almost nothing.
        """
        try:
            google, bing = await fetch_google_news(self._http, query), await fetch_bing_news(self._http, query)
            return [*google, *bing]
        except Exception:
            return []

    @work(exclusive=True, group="headlines")
    async def _refresh_headlines(self) -> None:
        try:
            self.league_headlines = await self.news_service.fetch_headlines()
        except MlbStatsError:
            self.league_headlines = []
        for sport, (_, news_service) in self.period_services.items():
            try:
                self.period_headlines[sport] = await news_service.fetch_headlines()
            except common.PeriodStatsError:
                self.period_headlines[sport] = []
        self.load_current_team()

    def _auto_refresh(self) -> None:
        if not self.live_paused:
            self.load_current_team()

    def _update_hints(self) -> None:
        # Only the hotkeys someone reaches for constantly. Stats (s),
        # Batting (b), Leaders (l), Follow (a), Theme (d) and Pause Live
        # (p) still work exactly as before — they're documented in the
        # '?' help screen instead of taking up space here every time.
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
        followed = self.current_team
        if followed and followed.sport in _PERIOD_SPORTS:
            self._body.show_standings = not self._body.show_standings
        else:
            self._body.show_stats = not self._body.show_stats
        self.load_current_team()

    def action_toggle_batting(self) -> None:
        if not self._body:
            return
        self._body.show_batting = not self._body.show_batting
        self.load_current_team()

    def action_toggle_leaders(self) -> None:
        if not self._body:
            return
        self._body.show_leaders = not self._body.show_leaders
        self.load_current_team()

    def action_refresh_now(self) -> None:
        self._refresh_headlines()

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
