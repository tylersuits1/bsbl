"""Team picker — MLB > league > team, with search across all leagues.
Reached on first launch (no favorites yet) or via the 'a' hotkey.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ListItem, ListView, Static

from .. import config, mlb_teams


class TeamPickerScreen(Screen):
    BINDINGS = [("escape", "dismiss_screen", "Back")]

    def __init__(self) -> None:
        super().__init__()
        self._query = ""

    def compose(self) -> ComposeResult:
        yield Static("FOLLOW A TEAM", id="picker-title")
        yield Input(placeholder="Search teams, or leave blank to browse by league", id="search")
        with VerticalScroll(id="picker-body"):
            yield ListView(id="team-list")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value.strip().lower()
        self._refresh_list()

    def _refresh_list(self) -> None:
        list_view = self.query_one("#team-list", ListView)
        list_view.clear()
        favorites = config.load_favorites()

        if self._query:
            matches = [
                t for t in mlb_teams.TEAMS
                if self._query in t.name.lower() or self._query in t.city.lower()
            ]
            matches.sort(key=lambda t: t.name)
            for team in matches:
                list_view.append(self._team_item(team, favorites))
            return

        for league in mlb_teams.LEAGUES:
            list_view.append(ListItem(Static(f"[bold]{league}[/bold]"), disabled=True))
            for division in ("East", "Central", "West"):
                teams = mlb_teams.teams_in_division(league, division)
                if not teams:
                    continue
                list_view.append(ListItem(Static(f"  [dim]{division}[/dim]"), disabled=True))
                for team in teams:
                    list_view.append(self._team_item(team, favorites, indent=True))

    def _team_item(self, team: mlb_teams.TeamInfo, favorites: list[str], indent: bool = False) -> ListItem:
        star = "★" if team.abbreviation in favorites else "☆"
        prefix = "    " if indent else ""
        item = ListItem(Static(f"{prefix}{star} {team.full_name}"))
        item.data = team.abbreviation
        return item

    @on(ListView.Selected, "#team-list")
    def on_team_selected(self, event: ListView.Selected) -> None:
        abbreviation = getattr(event.item, "data", None)
        if not abbreviation:
            return
        _, applied = config.toggle_favorite(abbreviation)
        if not applied:
            self.notify(f"You can follow up to {config.MAX_FAVORITES} teams", severity="warning")
        self._refresh_list()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
