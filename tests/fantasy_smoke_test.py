"""Manual smoke test for the fantasy-player tracking flow — search a
real NFL player, follow them via the team picker, then load the
aggregate Fantasy page against live data. Not a pytest suite (network +
timing dependent); run directly: `python tests/fantasy_smoke_test.py`.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import ListView

from sportspages_tui import config
from sportspages_tui.app import SportsPagesApp
from sportspages_tui.screens.team_picker import TeamPickerScreen


async def main() -> None:
    config.save_favorites([])
    config.save_fantasy_players([])

    app = SportsPagesApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause(1)
        # No favorites at all -> the picker opens automatically.
        assert len(app.screen_stack) == 2
        picker = app.screen
        assert isinstance(picker, TeamPickerScreen)

        team_list = picker.query_one("#team-list", ListView)
        team_list.focus()
        await pilot.pause(0.1)
        await pilot.press("p")
        await pilot.pause(0.2)
        print("=== Picker sport after 'p' ===", picker._sport)
        assert picker._sport == "FANTASY"

        await pilot.click("#search")
        await pilot.press(*"mahomes")
        await pilot.pause(1.0)  # debounce + live search
        team_list = picker.query_one("#team-list", ListView)
        print("=== Fantasy search results ===", len(team_list))
        assert len(team_list) >= 1

        team_list.focus()
        team_list.index = 0
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(1.0)  # profile-fetch worker

        followed = config.load_fantasy_players()
        print("=== Followed fantasy players ===", followed)
        assert len(followed) == 1 and followed[0]["position"] == "QB"

        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("y")
        await pilot.pause(0.5)
        assert len(app.screen_stack) == 1

        print("=== app.teams ===", [(t.sport, t.abbreviation) for t in app.teams])
        assert app.teams[-1].sport == "FANTASY"

        app.current_index = len(app.teams) - 1
        app.load_current_team()
        await pilot.pause(3)

        summary = app.screen.query_one("#summary")
        print("=== Fantasy page loaded, last_updated ===", app.last_updated)
        assert app.last_updated is not None

    config.save_favorites([])
    config.save_fantasy_players([])
    print("\nFANTASY SMOKE TEST PASSED — no crashes, all assertions held")


if __name__ == "__main__":
    asyncio.run(main())
