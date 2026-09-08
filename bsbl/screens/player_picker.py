"""Individual MLB player search — its own screen rather than a mode
inside the team picker, since searching for players doesn't fit the
league/division/team tree there. Reached via the pinned "PLAYERS" entry
at the top of the team picker's list; the back button (or Escape)
dismisses back to the team picker underneath.

Unlike the old ESPN-backed fantasy tracker this replaces, MLB Stats
API's people-search already returns position and current team, so
following a player needs no extra fetch — season stats are only
fetched lazily, when the aggregate Players page is actually viewed.
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
from ..mlb_api import MlbStatsError, MlbStatsService
from ..models import PlayerSearchResult

_SEARCH_PLACEHOLDER = "Search MLB players by name"


class PlayerPickerScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        # Pushed on top of the team picker, so it's the only screen the
        # app's key-binding chain sees while open — the team picker's
        # own shadows underneath don't apply here. Without these,
        # letters like 'b'/'p' would leak through to the app's
        # Batting/Pause-Live actions on the hidden page beneath both.
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
        self._service = MlbStatsService()
        self._query = ""
        self._results: list[PlayerSearchResult] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="picker-header"):
            yield Button("← Back", id="back-button")
        yield Static("[bold]PLAYERS[/bold] — search MLB players", id="picker-title")
        with Horizontal(id="search-row"):
            yield Input(placeholder=_SEARCH_PLACEHOLDER, id="search")
            yield Button("✕", id="clear-search")
        with VerticalScroll(id="picker-body"):
            yield ListView(id="player-list")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()
        self.query_one("#search", Input).focus()

    async def on_unmount(self) -> None:
        await self._service.aclose()

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
        followed = config.load_players()
        if self._query:
            for result in self._results:
                is_followed = any(p.get("player_id") == result.person_id for p in followed)
                star = "★" if is_followed else "☆"
                extra = ", ".join(p for p in (result.position, result.team_abbr) if p)
                label = f"{star} {result.name} ({extra})" if extra else f"{star} {result.name}"
                item = ListItem(Static(label))
                item.data = ("player_search", result)
                list_view.append(item)
            if not self._results:
                list_view.append(ListItem(Static("[italic dim]No matching players.[/italic dim]"), disabled=True))
        elif followed:
            for player in followed:
                extra = ", ".join(p for p in (player.get("position", ""), player.get("team_abbr", "")) if p)
                label = f"★ {player.get('name', '?')}" + (f" ({extra})" if extra else "")
                item = ListItem(Static(label))
                item.data = ("player_remove", player.get("player_id"))
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
            self._results = await self._service.search_players(query)
        except MlbStatsError:
            self._results = []
        self._refresh_list()

    @on(ListView.Selected, "#player-list")
    def on_item_selected(self, event: ListView.Selected) -> None:
        data = getattr(event.item, "data", None)
        if not data:
            return
        kind = data[0]
        if kind == "player_search":
            result: PlayerSearchResult = data[1]
            entry = {
                "player_id": result.person_id, "name": result.name,
                "position": result.position, "team_abbr": result.team_abbr,
            }
            _, applied = config.toggle_player(entry)
            if not applied:
                self.notify(f"You can track up to {config.MAX_PLAYERS} players", severity="warning")
            self._refresh_list()
        elif kind == "player_remove":
            _, player_id = data
            config.toggle_player({"player_id": player_id})
            self._refresh_list()
