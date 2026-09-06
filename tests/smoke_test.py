"""Manual smoke test — drives the real app against live MLB data via
Textual's headless test pilot. Not a pytest suite (network + timing
dependent); run directly: `python tests/smoke_test.py`.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sportspages_tui import config
from sportspages_tui.app import SportsPagesApp


async def main() -> None:
    config.save_favorites(["ATL", "MIL"])

    app = SportsPagesApp()
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.pause(3)
        print("=== Initial team ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "ATL"

        await pilot.press("right")
        await pilot.pause(3)
        print("=== After right arrow ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "MIL"

        await pilot.press("s")
        await pilot.pause(2)
        print("=== After 's' — show_stats ===", app._body.show_stats)
        assert app._body.show_stats is True
        stats_widget = app.screen.query_one("#stats-section")
        print("    stats section visible:", stats_widget.display)
        assert stats_widget.display is True

        await pilot.press("b")
        await pilot.pause(1)
        batting_widget = app.screen.query_one("#batting-section")
        print("=== After 'b' — batting section visible ===", batting_widget.display)
        assert batting_widget.display is True

        await pilot.press("left")
        await pilot.pause(2)
        print("=== After left arrow ===", app.current_team.full_name)
        assert app.current_team.abbreviation == "ATL"

        print("=== Headlines fetched ===", len(app.headlines))
        assert len(app.headlines) > 0

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

    config.save_favorites([])
    print("\nSMOKE TEST PASSED — no crashes, all assertions held")


if __name__ == "__main__":
    asyncio.run(main())
