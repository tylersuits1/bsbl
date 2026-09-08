"""Fantasy football player search — its own screen rather than a mode
inside the team picker, since searching for individual NFL players
doesn't fit the league/division/team tree there. Reached via the
pinned "FANTASY" entry at the top of the team picker's list; the back
button (or Escape) dismisses back to the team picker underneath.
"""

from __future__ import annotations

import asyncio

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, ListItem, ListView, Static

from .. import config
from ..fantasy_api import FantasyError, PlayerSearchResult, fetch_player_profile, search_players

_SEARCH_PLACEHOLDER = "Search NFL players by name"


class FantasyPickerScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._query = ""
        self._results: list[PlayerSearchResult] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="fantasy-header"):
            yield Button("← Back", id="back-button")
        yield Static("[bold]FANTASY[/bold] — search NFL players", id="picker-title")
        with Horizontal(id="search-row"):
            yield Input(placeholder=_SEARCH_PLACEHOLDER, id="search")
            yield Button("✕", id="clear-search")
        with VerticalScroll(id="picker-body"):
            yield ListView(id="player-list")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()
        self.query_one("#search", Input).focus()

    @on(Button.Pressed, "#back-button")
    def on_back_pressed(self, event: Button.Pressed) -> None:
        self.action_go_back()

    def action_go_back(self) -> None:
        self.dismiss()

    @on(Input.Changed, "#search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._query = event.value.strip()
        self._search_players(self._query)

    @on(Button.Pressed, "#clear-search")
    def on_clear_search(self, event: Button.Pressed) -> None:
        search = self.query_one("#search", Input)
        search.value = ""
        search.focus()
        self._query = ""
        self._results = []
        self._refresh_list()

    def _refresh_list(self) -> None:
        list_view = self.query_one("#player-list", ListView)
        list_view.clear()
        followed = config.load_fantasy_players()
        if self._query:
            for result in self._results:
                is_followed = any(p.get("espn_id") == result.espn_id for p in followed)
                star = "★" if is_followed else "☆"
                item = ListItem(Static(f"{star} {result.name} ({result.team_name})"))
                item.data = ("fantasy_search", result.espn_id, result.name, result.team_name)
                list_view.append(item)
            if not self._results:
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
    async def _search_players(self, query: str) -> None:
        if not query:
            self._results = []
            self._refresh_list()
            return
        await asyncio.sleep(0.3)  # debounce — avoid a request per keystroke
        try:
            self._results = await search_players(self.app.http_client, query)
        except FantasyError:
            self._results = []
        self._refresh_list()

    @work
    async def _follow_player(self, espn_id: int, name: str, team_name: str) -> None:
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

    @on(ListView.Selected, "#player-list")
    def on_item_selected(self, event: ListView.Selected) -> None:
        data = getattr(event.item, "data", None)
        if not data:
            return
        kind = data[0]
        if kind == "fantasy_search":
            _, espn_id, name, team_name = data
            self._follow_player(espn_id, name, team_name)
        elif kind == "fantasy_remove":
            _, espn_id = data
            config.toggle_fantasy_player({"espn_id": espn_id})
            self._refresh_list()
