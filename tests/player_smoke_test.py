"""Manual smoke test for the player-following flow — search a real MLB
player, follow them via the team picker's pinned PLAYERS entry, then
load the aggregate Players page against live data. Not a pytest suite
(network + timing dependent); run directly:
`python tests/player_smoke_test.py`.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.widgets import ListView

from bsbl import config
from bsbl.app import BsblApp
from bsbl.screens.player_picker import PlayerPickerScreen
from bsbl.screens.team_picker import TeamPickerScreen


async def main() -> None:
    config.save_favorites([])
    config.save_players([])

    app = BsblApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause(1)
        # No favorites at all -> the picker opens automatically.
        assert len(app.screen_stack) == 2
        picker = app.screen
        assert isinstance(picker, TeamPickerScreen)

        # The pinned "PLAYERS" entry is the first row in the list —
        # selecting it pushes the dedicated player-search screen.
        team_list = picker.query_one("#team-list", ListView)
        team_list.focus()
        team_list.index = 0
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(0.3)
        print("=== Screen stack depth after opening Players ===", len(app.screen_stack))
        assert len(app.screen_stack) == 3
        player_screen = app.screen
        assert isinstance(player_screen, PlayerPickerScreen)

        await pilot.click("#search")
        await pilot.press(*"acuna")
        await pilot.pause(1.0)  # debounce + live search
        player_list = player_screen.query_one("#player-list", ListView)
        print("=== Player search results ===", len(player_list))
        assert len(player_list) >= 1

        player_list.focus()
        player_list.index = 0
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(0.3)

        followed = config.load_players()
        print("=== Followed players ===", followed)
        assert len(followed) == 1

        await pilot.press("escape")  # back to the team picker
        await pilot.pause(0.3)
        print("=== Screen stack depth after Players back ===", len(app.screen_stack))
        assert len(app.screen_stack) == 2
        assert isinstance(app.screen, TeamPickerScreen)

        await pilot.press("escape")  # exit-confirmation prompt
        await pilot.pause(0.2)
        await pilot.press("y")
        await pilot.pause(0.5)
        assert len(app.screen_stack) == 1

        print("=== app.teams ===", [t.abbreviation for t in app.teams])
        assert app.teams[-1].abbreviation == "PLAYERS"

        app.current_index = len(app.teams) - 1
        app.load_current_team()
        await pilot.pause(3)

        print("=== Players page loaded, last_updated ===", app.last_updated)
        assert app.last_updated is not None

    config.save_favorites([])
    config.save_players([])
    print("\nPLAYER SMOKE TEST PASSED — no crashes, all assertions held")


if __name__ == "__main__":
    asyncio.run(main())
