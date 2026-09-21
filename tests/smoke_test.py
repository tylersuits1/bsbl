"""Manual smoke test — drives the real app against live MLB data via
Textual's headless test pilot. Not a pytest suite (network + timing
dependent); run directly: `python tests/smoke_test.py`.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import Input, ListView

from bsbl import config
from bsbl.app import BsblApp
from bsbl.screens.team_picker import TeamPickerScreen


async def main() -> None:
    config.save_favorites([("MLB", "ATL"), ("MLB", "MIL")])
    config.save_players([])

    app = BsblApp()
    async with app.run_test(size=(100, 55)) as pilot:
        await pilot.pause(3)
        print("=== Initial team ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "ATL"
        assert app.last_updated is not None
        print("=== Page ===", f"{app.current_index + 1}/{len(app.teams)}")
        assert app.current_index == 0 and len(app.teams) == 2

        headline_list = app.screen.query_one("#headlines-list", ListView)
        print("=== Headlines collapsed on open ===", not app._body.show_headlines, "| display:", headline_list.display)
        assert app._body.show_headlines is False
        assert headline_list.display is False

        await pilot.press("h")
        await pilot.pause(0.5)
        print("=== Headline items after 'h' ===", len(headline_list))
        assert len(headline_list) >= 1

        await pilot.press("right")
        await pilot.pause(3)
        print("=== After right arrow ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "MIL"

        await pilot.press("s")
        await pilot.pause(2)
        print("=== After 's' — show_stats ===", app._body.show_stats)
        assert app._body.show_stats is True

        await pilot.press("b")
        await pilot.pause(1)
        print("=== After 'b' — show_batting ===", app._body.show_batting)
        assert app._body.show_batting is True
        batting_widget = app.screen.query_one("#batting-section")
        assert batting_widget.display is True

        await pilot.press("left")
        await pilot.pause(2)
        print("=== Back to first team ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "ATL"

        await pilot.press("question_mark")
        await pilot.pause(0.5)
        print("=== After '?' — screen stack depth ===", len(app.screen_stack))
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        await pilot.pause(0.5)

        await pilot.press("p")
        print("=== After 'p' — live_paused ===", app.live_paused)
        assert app.live_paused is True

        # -- team picker: collapsible division groups, search, search
        # clear, escape confirmation --
        await pilot.press("a")
        await pilot.pause(0.5)
        picker = app.screen
        assert isinstance(picker, TeamPickerScreen)

        team_list = picker.query_one("#team-list", ListView)
        print("=== Picker items (browse) ===", len(team_list))
        assert len(team_list) > 0

        search = picker.query_one("#search", Input)
        search.value = "brave"
        picker._query = "brave"
        picker._refresh_list()
        await pilot.pause(0.2)
        team_list = picker.query_one("#team-list", ListView)
        print("=== Search 'brave' matches ===", len(team_list))
        assert len(team_list) == 1

        await pilot.click("#clear-search")
        await pilot.pause(0.2)
        print("=== Search value after clear ===", repr(search.value))
        assert search.value == ""

        await pilot.press("escape")
        await pilot.pause(0.2)
        print("=== Picker confirming ===", picker._confirming)
        assert picker._confirming is True
        await pilot.press("n")  # cancels the confirmation prompt
        await pilot.pause(0.2)
        assert picker._confirming is False

        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("shift+enter")
        await pilot.pause(0.5)
        assert len(app.screen_stack) == 1

    config.save_favorites([])
    config.save_players([])
    print("\nSMOKE TEST PASSED — no crashes, all assertions held")


if __name__ == "__main__":
    asyncio.run(main())
