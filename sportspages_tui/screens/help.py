"""Keybinding reference overlay, opened with '?'."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_KEYS = [
    ("← / →", "Switch between followed teams"),
    ("↑ / ↓", "Move through the headlines list"),
    ("enter", "Open the highlighted headline in your browser"),
    ("s", "Toggle player stats"),
    ("b", "Toggle batting order"),
    ("r", "Refresh now"),
    ("a", "Follow / unfollow teams"),
    ("p", "Pause / resume live auto-refresh"),
    ("d", "Toggle dark / light theme"),
    ("?", "This help screen"),
    ("q", "Quit"),
]


class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss_screen", "Close"), ("?", "dismiss_screen", "Close")]

    def compose(self) -> ComposeResult:
        lines = ["[bold]KEYS[/bold]", ""]
        for key, desc in _KEYS:
            lines.append(f"  [bold]{key:<8}[/bold] {desc}")
        lines.append("")
        lines.append("[dim]Press Esc or ? to close[/dim]")
        with Vertical(id="help-box"):
            yield Static("\n".join(lines))

    def action_dismiss_screen(self) -> None:
        self.dismiss()
