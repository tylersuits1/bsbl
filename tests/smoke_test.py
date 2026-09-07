"""Manual smoke test — drives the real app against live MLB/NCAAF/NFL/NBA
data via Textual's headless test pilot. Not a pytest suite (network +
timing dependent); run directly: `python tests/smoke_test.py`.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import Input, ListView

from sportspages_tui import config
from sportspages_tui.app import SportsPagesApp
from sportspages_tui.screens.team_picker import TeamPickerScreen


async def main() -> None:
    config.save_favorites([
        ("MLB", "ATL"), ("MLB", "MIL"), ("NCAAF", "UGA"), ("NFL", "SF"), ("NBA", "LAL"),
    ])
    config.save_fantasy_players([])  # isolate from fantasy_smoke_test.py's state

    app = SportsPagesApp()
    async with app.run_test(size=(100, 55)) as pilot:
        await pilot.pause(3)
        print("=== Initial team ===", app.current_team.full_name)
        assert app.current_team.sport == "MLB" and app.current_team.abbreviation == "ATL"
        assert app.last_updated is not None
        print("=== Page ===", f"{app.current_index + 1}/{len(app.teams)}")
        assert app.current_index == 0 and len(app.teams) == 5

        headline_list = app.screen.query_one("#headlines-list", ListView)
        print("=== Headline items in list ===", len(headline_list))
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

        # Cross into the NCAAF team — 's' should now drive standings (not
        # MLB stats), and 'l' drives leaders, its own dedicated key.
        await pilot.press("right")
        await pilot.pause(3)
        print("=== After right arrow (into NCAAF) ===", app.current_team.full_name)
        assert app.current_team.sport == "NCAAF" and app.current_team.abbreviation == "UGA"

        await pilot.press("s")
        await pilot.pause(2)
        print("=== NCAAF 's' — show_standings ===", app._body.show_standings, "show_stats unchanged:", app._body.show_stats)
        assert app._body.show_standings is True
        assert app._body.show_stats is True  # untouched, still set from the MLB team above

        await pilot.press("l")
        await pilot.pause(2)
        print("=== NCAAF 'l' — show_leaders ===", app._body.show_leaders)
        assert app._body.show_leaders is True

        # Cross into NFL, then NBA — same PeriodBoxScore render path,
        # should load without crashing on either.
        await pilot.press("right")
        await pilot.pause(3)
        print("=== After right arrow (into NFL) ===", app.current_team.full_name)
        assert app.current_team.sport == "NFL" and app.current_team.abbreviation == "SF"

        await pilot.press("right")
        await pilot.pause(3)
        print("=== After right arrow (into NBA) ===", app.current_team.full_name)
        assert app.current_team.sport == "NBA" and app.current_team.abbreviation == "LAL"

        for _ in range(4):
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

        await pilot.press("d")
        await pilot.pause(0.5)
        print("=== After 'd' — theme ===", app.theme)
        assert app.theme == "ansi-light"

        # -- team picker: 4 sport tabs, collapsible groups, search clear,
        # escape confirmation --
        await pilot.press("a")
        await pilot.pause(0.5)
        picker = app.screen
        assert isinstance(picker, TeamPickerScreen)
        assert picker._sport == "MLB"

        # Sport-select keys are screen-level hotkeys, so (like Enter)
        # they need the team list focused rather than the search box —
        # the search box has to accept every letter as literal query
        # text, since plenty of team names start with b/c/f/n.
        team_list = picker.query_one("#team-list", ListView)
        team_list.focus()
        await pilot.pause(0.1)

        await pilot.press("c")
        await pilot.pause(0.2)
        print("=== Picker sport after 'c' ===", picker._sport)
        assert picker._sport == "NCAAF"

        await pilot.press("f")
        await pilot.pause(0.2)
        print("=== Picker sport after 'f' ===", picker._sport)
        assert picker._sport == "NFL"

        await pilot.press("n")
        await pilot.pause(0.2)
        print("=== Picker sport after 'n' ===", picker._sport)
        assert picker._sport == "NBA"

        await pilot.press("b")
        await pilot.pause(0.2)
        print("=== Picker sport after 'b' ===", picker._sport)
        assert picker._sport == "MLB"

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
        await pilot.press("n")  # cancels the confirm — 'n' means NBA only when NOT confirming
        await pilot.pause(0.2)
        assert picker._confirming is False

        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("y")
        await pilot.pause(0.5)
        assert len(app.screen_stack) == 1

    config.save_favorites([])
    print("\nSMOKE TEST PASSED — no crashes, all assertions held")


if __name__ == "__main__":
    asyncio.run(main())
