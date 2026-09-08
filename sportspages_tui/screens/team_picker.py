"""Team picker — one continuous list spanning every sport (MLB, NCAAF,
NFL, NBA), each as its own section of league/conference > division >
team, separated by a rule so scrolling from one sport into the next
reads as a clear break. Search matches teams across all sports at once
(tagged by sport in the results), so there's no per-sport mode to
switch. A pinned entry at the top opens Fantasy football player search
on its own screen, since players don't fit this team tree. Reached on
first launch (no favorites yet) or via the 'a' hotkey. Division groups
start collapsed so browsing isn't one long scroll; Escape asks for a
y/n confirmation before handing control back to the app.
"""

from __future__ import annotations

from rich.rule import Rule
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ListItem, ListView, Static

from .. import config, mlb_teams, nba_teams, ncaaf_teams, nfl_teams
from .fantasy_picker import FantasyPickerScreen

_MLB_DIVISIONS = ("East", "Central", "West")

_TEAM_MODULES = {
    "MLB": mlb_teams,
    "NCAAF": ncaaf_teams,
    "NFL": nfl_teams,
    "NBA": nba_teams,
}

_SEARCH_PLACEHOLDER = "Search all teams, or leave blank to browse"


class TeamPickerScreen(Screen):
    BINDINGS = [
        Binding("escape", "request_exit", "Back"),
        Binding("y", "confirm_yes", "Confirm"),
        Binding("n", "confirm_no", "Cancel"),
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
        self._query = ""
        self._confirming = False
        # Division groups start collapsed — makes the initial browse view
        # a short list of sport/division headers instead of every team
        # in every sport at once. Keyed per sport so each sport's
        # collapse state is independent.
        self._collapsed: dict[str, set[str]] = {
            sport: {key for key, _, _ in self._groups_for_sport(sport)} for sport in _TEAM_MODULES
        }

    def compose(self) -> ComposeResult:
        yield Static("[bold]FOLLOW A TEAM[/bold]  [dim](type to search every sport)[/dim]", id="picker-title")
        with Horizontal(id="search-row"):
            yield Input(placeholder=_SEARCH_PLACEHOLDER, id="search")
            yield Button("✕", id="clear-search")
        with VerticalScroll(id="picker-body"):
            yield ListView(id="team-list")
        yield Static(id="confirm-box")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value.strip().lower()
        self._refresh_list()

    @on(Button.Pressed, "#clear-search")
    def on_clear_search(self, event: Button.Pressed) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.focus()
        self._query = ""
        self._refresh_list()

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

        favorites = config.load_favorites()

        if self._query:
            matches = self._search_matches()
            for sport, team in matches:
                list_view.append(self._team_item(sport, team, favorites, show_sport=True))
            if not matches:
                list_view.append(ListItem(Static("[italic dim]No matching teams.[/italic dim]"), disabled=True))
            if len(list_view):
                list_view.index = 0
            return

        fantasy_item = ListItem(Static("[bold]\U0001f3c8 FANTASY[/bold] — search & follow NFL players"))
        fantasy_item.data = ("fantasy_open",)
        list_view.append(fantasy_item)

        for sport in _TEAM_MODULES:
            list_view.append(ListItem(Static(Rule(style="dim")), disabled=True))
            list_view.append(ListItem(Static(f"[bold underline]{sport}[/bold underline]"), disabled=True))
            for key, label, teams in self._groups_for_sport(sport):
                self._append_group(list_view, sport, key, label, teams, favorites)

        # ListView needs a highlighted item before Enter/click do
        # anything — without this, a user opening the picker and
        # immediately hitting Enter on the first group sees nothing
        # happen.
        if len(list_view):
            list_view.index = 0

    def _append_group(
        self, list_view: ListView, sport: str, key: str, label: str, teams: list, favorites: list[tuple[str, str]]
    ) -> None:
        collapsed = key in self._collapsed[sport]
        arrow = "▸" if collapsed else "▾"
        header = ListItem(Static(f"    {arrow} [bold]{label}[/bold]"))
        header.data = ("toggle", sport, key)
        list_view.append(header)
        if not collapsed:
            for team in teams:
                list_view.append(self._team_item(sport, team, favorites, indent=True))

    def _search_matches(self) -> list[tuple[str, object]]:
        matches = []
        for sport, module in _TEAM_MODULES.items():
            for team in module.TEAMS:
                if self._query in team.name.lower() or self._query in team.city.lower():
                    matches.append((sport, team))
        matches.sort(key=lambda pair: pair[1].name)
        return matches

    def _team_item(
        self, sport: str, team, favorites: list[tuple[str, str]], *, indent: bool = False, show_sport: bool = False
    ) -> ListItem:
        star = "★" if (sport, team.abbreviation) in favorites else "☆"
        prefix = "        " if indent else ""
        tag = f"[dim]{sport}[/dim] " if show_sport else ""
        item = ListItem(Static(f"{prefix}{star} {tag}{team.full_name}"))
        item.data = ("team", sport, team.abbreviation)
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
        elif kind == "fantasy_open":
            self.app.push_screen(FantasyPickerScreen())

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
        if not self._confirming:
            return
        self._confirming = False
        self.query_one("#confirm-box", Static).display = False
        self.query_one("#search-row", Horizontal).display = True
        self.query_one("#picker-body", VerticalScroll).display = True
