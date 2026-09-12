"""Scoring-plays recap — every play that put a run on the board in
today's game, grouped by inning. Opened with 'z'.
"""

from __future__ import annotations

from rich.console import Group

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from ..models import ScoringPlaysResult
from ..rendering import scoring_plays_lines


class ScoringPlaysScreen(Screen):
    BINDINGS = [
        Binding("escape", "close_screen", "Back"),
        Binding("z", "close_screen", "Back"),
        # Shadow the main app's remaining global hotkeys so they don't
        # leak into this screen's footer or mutate the hidden page
        # behind it (see team_picker.py for the same pattern).
        Binding("s", "noop", show=False),
        Binding("b", "noop", show=False),
        Binding("h", "noop", show=False),
        Binding("r", "noop", show=False),
        Binding("a", "noop", show=False),
        Binding("p", "noop", show=False),
        Binding("question_mark", "noop", show=False),
    ]

    def __init__(self, team_full_name: str, result: ScoringPlaysResult | None) -> None:
        super().__init__()
        self._team_full_name = team_full_name
        self._result = result

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]SCORING PLAYS · {self._team_full_name.upper()}[/bold]", id="scoring-plays-title")
        with VerticalScroll(id="scoring-plays-body"):
            yield Static(id="scoring-plays-content")
        yield Footer()

    def on_mount(self) -> None:
        content = self.query_one("#scoring-plays-content", Static)
        if self._result is None:
            content.update("[italic dim]No game today.[/italic dim]")
        else:
            content.update(Group(*scoring_plays_lines(self._result)))

    def action_noop(self) -> None:
        pass

    def action_close_screen(self) -> None:
        self.dismiss()
