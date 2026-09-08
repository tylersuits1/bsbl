"""MLB team picker — browsed by league > division, with search. Reached
on first launch (no favorites yet) or via the 'a' hotkey. Division
groups start collapsed so browsing isn't one long scroll; Escape asks
for a y/n confirmation before handing control back to the app.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ListItem, ListView, Static

from .. import config, mlb_teams

_DIVISIONS = ("East", "Central", "West")

_SEARCH_PLACEHOLDER = "Search teams, or leave blank to browse"


class TeamPickerScreen(Screen):
    BINDINGS = [
        Binding("escape", "request_exit", "Back"),
        Binding("y", "confirm_yes", "Confirm"),
        Binding("n", "confirm_no", "Cancel"),
        # Shadow the main app's remaining global hotkeys so they don't
        # leak into this screen's footer, or silently mutate the hidden
        # page behind it (e.g. pressing 's' here toggling its stats panel).
        Binding("s", "noop", show=False),
        Binding("b", "noop", show=False),
        Binding("r", "noop", show=False),
        Binding("a", "noop", show=False),
        Binding("p", "noop", show=False),
        Binding("d", "noop", show=False),
        Binding("question_mark", "noop", show=False),
    ]

    def action_noop(self) -> None:
        pass

    def __init__(self) -> None:
        super().__init__()
        self._query = ""
        self._confirming = False
        # Division groups start collapsed — makes the initial browse
        # view a short list of headers instead of every team at once.
        self._collapsed: set[str] = {key for key, _, _ in self._groups()}

    def compose(self) -> ComposeResult:
        yield Static("[bold]FOLLOW A TEAM[/bold]", id="picker-title")
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

    def _groups(self) -> list[tuple[str, str, list]]:
        """(group key, display label, teams) for every league/division —
        used both to render the browse list and to seed the
        collapsed-by-default state up front.
        """
        groups = []
        for league in mlb_teams.LEAGUES:
            for division in _DIVISIONS:
                teams = mlb_teams.teams_in_division(league, division)
                if teams:
                    groups.append((f"{league}/{division}", f"{league} — {division}", teams))
        return groups

    def _refresh_list(self) -> None:
        list_view = self.query_one("#team-list", ListView)
        list_view.clear()

        favorites = config.load_favorites()

        if self._query:
            for team in self._search_matches():
                list_view.append(self._team_item(team, favorites))
            if len(list_view):
                list_view.index = 0
            return

        for key, label, teams in self._groups():
            self._append_group(list_view, key, label, teams, favorites)

        # ListView needs a highlighted item before Enter/click do
        # anything — without this, a user opening the picker and
        # immediately hitting Enter on the first group sees nothing
        # happen.
        if len(list_view):
            list_view.index = 0

    def _append_group(
        self, list_view: ListView, key: str, label: str, teams: list, favorites: list[tuple[str, str]]
    ) -> None:
        collapsed = key in self._collapsed
        arrow = "▸" if collapsed else "▾"
        header = ListItem(Static(f"{arrow} [bold]{label}[/bold]"))
        header.data = ("toggle", key)
        list_view.append(header)
        if not collapsed:
            for team in teams:
                list_view.append(self._team_item(team, favorites, indent=True))

    def _search_matches(self) -> list:
        matches = [
            t for t in mlb_teams.TEAMS
            if self._query in t.name.lower() or self._query in t.city.lower()
        ]
        matches.sort(key=lambda t: t.name)
        return matches

    def _team_item(self, team, favorites: list[tuple[str, str]], *, indent: bool = False) -> ListItem:
        star = "★" if ("MLB", team.abbreviation) in favorites else "☆"
        prefix = "    " if indent else ""
        item = ListItem(Static(f"{prefix}{star} {team.full_name}"))
        item.data = ("team", team.abbreviation)
        return item

    @on(ListView.Selected, "#team-list")
    def on_item_selected(self, event: ListView.Selected) -> None:
        data = getattr(event.item, "data", None)
        if not data:
            return
        kind = data[0]
        if kind == "toggle":
            _, key = data
            if key in self._collapsed:
                self._collapsed.discard(key)
            else:
                self._collapsed.add(key)
            self._refresh_list()
        elif kind == "team":
            _, abbreviation = data
            _, applied = config.toggle_favorite("MLB", abbreviation)
            if not applied:
                self.notify(f"You can follow up to {config.MAX_FAVORITES} teams", severity="warning")
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
            if sport != "MLB":
                continue
            team = mlb_teams.team_by_abbreviation(abbr)
            names.append(team.full_name if team else f"MLB:{abbr}")
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
