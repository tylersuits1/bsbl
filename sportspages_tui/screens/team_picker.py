"""Team picker — one of four sports (MLB/NCAAF/NFL/NBA), browsed by
league/conference > division, with search scoped to whichever sport tab
is active. 'b' jumps to baseball (MLB), 'c' to college football
(NCAAF), 'f' to (NFL) football, 'n' to basketball (NBA), 'p' to a live
NFL player search for fantasy tracking. Reached on first launch (no
favorites yet) or via the 'a' hotkey. Groups start collapsed so
browsing isn't one long scroll; Escape asks for a y/n confirmation
before handing control back to the app.
"""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ListItem, ListView, Static

from .. import config, mlb_teams, nba_teams, ncaaf_teams, nfl_teams
from ..fantasy_api import FantasyError, PlayerSearchResult, fetch_player_profile, search_players

_MLB_DIVISIONS = ("East", "Central", "West")

_TEAM_MODULES = {
    "MLB": mlb_teams,
    "NCAAF": ncaaf_teams,
    "NFL": nfl_teams,
    "NBA": nba_teams,
}

_SPORT_LABELS = {"MLB": "MLB", "NCAAF": "NCAAF", "NFL": "NFL", "NBA": "NBA", "FANTASY": "FANTASY"}

_SEARCH_PLACEHOLDER = "Search teams, or leave blank to browse"
_FANTASY_PLACEHOLDER = "Search NFL players by name"


class TeamPickerScreen(Screen):
    BINDINGS = [
        Binding("escape", "request_exit", "Back"),
        Binding("b", "show_baseball", "Baseball"),
        Binding("c", "show_college_football", "College FB"),
        Binding("f", "show_football", "Football"),
        Binding("p", "show_fantasy", "Fantasy"),
        Binding("y", "confirm_yes", "Confirm"),
        Binding("n", "confirm_no", "Basketball / Cancel"),
        # Shadow the main app's remaining global hotkeys so they don't
        # leak into this screen's footer, or silently mutate the hidden
        # page behind it (e.g. pressing 's' here toggling its stats panel).
        Binding("s", "noop", show=False),
        Binding("l", "noop", show=False),
        Binding("r", "noop", show=False),
        Binding("a", "noop", show=False),
        Binding("d", "noop", show=False),
        Binding("question_mark", "noop", show=False),
    ]

    def action_noop(self) -> None:
        pass

    def __init__(self) -> None:
        super().__init__()
        self._sport = "MLB"
        self._query = ""
        self._confirming = False
        self._fantasy_results: list[PlayerSearchResult] = []
        # Groups start collapsed — makes the initial browse view a short
        # list of headers instead of every team at once.
        self._collapsed: dict[str, set[str]] = {
            sport: {key for key, _, _ in self._groups_for_sport(sport)} for sport in _TEAM_MODULES
        }

    def compose(self) -> ComposeResult:
        yield Static(id="picker-title")
        with Horizontal(id="search-row"):
            yield Input(placeholder=_SEARCH_PLACEHOLDER, id="search")
            yield Button("✕", id="clear-search")
        with VerticalScroll(id="picker-body"):
            yield ListView(id="team-list")
        yield Static(id="confirm-box")
        yield Footer()

    def on_mount(self) -> None:
        self._update_title()
        self._refresh_list()

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value.strip().lower()
        if self._sport == "FANTASY":
            self._search_fantasy_players(event.value.strip())
        else:
            self._refresh_list()

    @on(Button.Pressed, "#clear-search")
    def on_clear_search(self, event: Button.Pressed) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.focus()
        self._query = ""
        if self._sport == "FANTASY":
            self._fantasy_results = []
            self._refresh_list()
        else:
            self._refresh_list()

    def _update_title(self) -> None:
        self.query_one("#picker-title", Static).update(
            f"[bold]FOLLOW A TEAM — {_SPORT_LABELS[self._sport]}[/bold]  "
            "[dim](b baseball · c college · f NFL · n NBA · p fantasy)[/dim]"
        )

    def _groups_for_sport(self, sport: str) -> list[tuple[str, str, list]]:
        """(group key, display label, teams) for every non-empty
        league/conference+division group in the given sport — used both
        to render the browse list and to seed the collapsed-by-default
        state per sport up front.
        """
        if sport == "MLB":
            groups = []
            for league in mlb_teams.LEAGUES:
                for division in _MLB_DIVISIONS:
                    teams = mlb_teams.teams_in_division(league, division)
                    if teams:
                        groups.append((f"{league}/{division}", f"{league} — {division}", teams))
            return groups
        if sport == "NCAAF":
            return [
                (conf, conf, teams)
                for conf in ncaaf_teams.CONFERENCES
                if (teams := ncaaf_teams.teams_in_conference(conf))
            ]
        if sport == "NFL":
            groups = []
            for conf in nfl_teams.CONFERENCES:
                for division in nfl_teams.DIVISIONS:
                    teams = nfl_teams.teams_in_division(conf, division)
                    if teams:
                        groups.append((f"{conf}/{division}", f"{conf} {division}", teams))
            return groups
        if sport == "NBA":
            groups = []
            for conf in nba_teams.CONFERENCES:
                for division in nba_teams.DIVISIONS[conf]:
                    teams = nba_teams.teams_in_division(conf, division)
                    if teams:
                        groups.append((f"{conf}/{division}", f"{conf} {division}", teams))
            return groups
        return []

    def _refresh_list(self) -> None:
        list_view = self.query_one("#team-list", ListView)
        list_view.clear()

        if self._sport == "FANTASY":
            self._render_fantasy_list(list_view)
            return

        favorites = config.load_favorites()

        if self._query:
            for team in self._search_matches():
                list_view.append(self._team_item(team, favorites))
            if len(list_view):
                list_view.index = 0
            return

        for key, label, teams in self._groups_for_sport(self._sport):
            self._append_group(list_view, self._sport, key, label, teams, favorites)

        # ListView needs a highlighted item before Enter/click do
        # anything — without this, a user opening the picker and
        # immediately hitting Enter on the first group sees nothing
        # happen.
        if len(list_view):
            list_view.index = 0

    def _render_fantasy_list(self, list_view: ListView) -> None:
        followed = config.load_fantasy_players()
        if self._query:
            for result in self._fantasy_results:
                is_followed = any(p.get("espn_id") == result.espn_id for p in followed)
                star = "★" if is_followed else "☆"
                item = ListItem(Static(f"{star} {result.name} ({result.team_name})"))
                item.data = ("fantasy_search", result.espn_id, result.name, result.team_name)
                list_view.append(item)
            if not self._fantasy_results:
                list_view.append(ListItem(Static("[italic dim]No matching players.[/italic dim]"), disabled=True))
        elif followed:
            for player in followed:
                label = f"★ {player.get('name', '?')}"
                extra = ", ".join(p for p in (player.get("position", ""), player.get("team_abbr", "")) if p)
                if extra:
                    label += f" ({extra})"
                item = ListItem(Static(label))
                item.data = ("fantasy_remove", player.get("espn_id"))
                list_view.append(item)
        else:
            list_view.append(ListItem(Static("[italic dim]Type a player name to search.[/italic dim]"), disabled=True))
        if len(list_view):
            list_view.index = 0

    @work(exclusive=True)
    async def _search_fantasy_players(self, query: str) -> None:
        if not query:
            self._fantasy_results = []
            self._refresh_list()
            return
        await asyncio.sleep(0.3)  # debounce — avoid a request per keystroke
        try:
            self._fantasy_results = await search_players(self.app.http_client, query)
        except FantasyError:
            self._fantasy_results = []
        self._refresh_list()

    @work
    async def _follow_fantasy_player(self, espn_id: int, name: str, team_name: str) -> None:
        try:
            profile = await fetch_player_profile(self.app.http_client, espn_id)
            entry = {
                "espn_id": espn_id, "name": profile.name, "position": profile.position,
                "team_abbr": profile.team_abbr, "team_name": profile.team_name,
            }
        except FantasyError:
            entry = {"espn_id": espn_id, "name": name, "position": "", "team_abbr": "", "team_name": team_name}
        _, applied = config.toggle_fantasy_player(entry)
        if not applied:
            self.notify(f"You can track up to {config.MAX_FANTASY_PLAYERS} fantasy players", severity="warning")
        self._refresh_list()

    def _append_group(
        self, list_view: ListView, sport: str, key: str, label: str, teams: list, favorites: list[tuple[str, str]]
    ) -> None:
        collapsed = key in self._collapsed[sport]
        arrow = "▸" if collapsed else "▾"
        header = ListItem(Static(f"{arrow} [bold]{label}[/bold]"))
        header.data = ("toggle", sport, key)
        list_view.append(header)
        if not collapsed:
            for team in teams:
                list_view.append(self._team_item(team, favorites, indent=True))

    def _search_matches(self) -> list:
        matches = [
            t for t in _TEAM_MODULES[self._sport].TEAMS
            if self._query in t.name.lower() or self._query in t.city.lower()
        ]
        matches.sort(key=lambda t: t.name)
        return matches

    def _team_item(self, team, favorites: list[tuple[str, str]], indent: bool = False) -> ListItem:
        star = "★" if (self._sport, team.abbreviation) in favorites else "☆"
        prefix = "    " if indent else ""
        item = ListItem(Static(f"{prefix}{star} {team.full_name}"))
        item.data = ("team", self._sport, team.abbreviation)
        return item

    @on(ListView.Selected, "#team-list")
    def on_item_selected(self, event: ListView.Selected) -> None:
        data = getattr(event.item, "data", None)
        if not data:
            return
        kind = data[0]
        if kind == "toggle":
            _, sport, key = data
            group = self._collapsed[sport]
            if key in group:
                group.discard(key)
            else:
                group.add(key)
            self._refresh_list()
        elif kind == "team":
            _, sport, abbreviation = data
            _, applied = config.toggle_favorite(sport, abbreviation)
            if not applied:
                self.notify(f"You can follow up to {config.MAX_FAVORITES} teams", severity="warning")
            self._refresh_list()
        elif kind == "fantasy_search":
            _, espn_id, name, team_name = data
            self._follow_fantasy_player(espn_id, name, team_name)
        elif kind == "fantasy_remove":
            _, espn_id = data
            config.toggle_fantasy_player({"espn_id": espn_id})
            self._refresh_list()

    def action_show_baseball(self) -> None:
        self._switch_sport("MLB")

    def action_show_college_football(self) -> None:
        self._switch_sport("NCAAF")

    def action_show_football(self) -> None:
        self._switch_sport("NFL")

    def action_show_fantasy(self) -> None:
        self._switch_sport("FANTASY")

    def _switch_sport(self, sport: str) -> None:
        if self._confirming or self._sport == sport:
            return
        self._sport = sport
        self._query = ""
        self._fantasy_results = []
        search = self.query_one("#search", Input)
        search.value = ""
        search.placeholder = _FANTASY_PLACEHOLDER if sport == "FANTASY" else _SEARCH_PLACEHOLDER
        self._update_title()
        self._refresh_list()

    def action_request_exit(self) -> None:
        if self._confirming:
            return
        self._confirming = True
        self._show_confirm()

    def _show_confirm(self) -> None:
        entries = config.load_favorites()
        names = []
        for sport, abbr in entries:
            module = _TEAM_MODULES.get(sport)
            team = module.team_by_abbreviation(abbr) if module else None
            names.append(team.full_name if team else f"{sport}:{abbr}")
        for player in config.load_fantasy_players():
            names.append(f"{player.get('name', '?')} (Fantasy)")
        listing = "\n".join(f"  • {n}" for n in names) if names else "  (no teams followed yet)"
        text = (
            "[bold]Exit team picker with these teams?[/bold]\n\n"
            f"{listing}\n\n"
            "[dim]y = yes, back to the pages   ·   n = no, keep browsing[/dim]"
        )
        self.query_one("#confirm-box", Static).update(text)
        self.query_one("#search-row", Horizontal).display = False
        self.query_one("#picker-body", VerticalScroll).display = False
        self.query_one("#confirm-box", Static).display = True

    def action_confirm_yes(self) -> None:
        if not self._confirming:
            return
        self.dismiss()

    def action_confirm_no(self) -> None:
        # 'n' is dual-purpose: switch to basketball when browsing, but
        # cancel the exit-confirmation prompt when it's showing — the
        # two states never overlap, so one key does both jobs.
        if not self._confirming:
            self._switch_sport("NBA")
            return
        self._confirming = False
        self.query_one("#confirm-box", Static).display = False
        self.query_one("#search-row", Horizontal).display = True
        self.query_one("#picker-body", VerticalScroll).display = True
