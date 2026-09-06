import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sportspages_tui import config
from sportspages_tui.app import SportsPagesApp


async def main() -> None:
    config.save_favorites(["ATL"])
    app = SportsPagesApp()
    async with app.run_test(size=(100, 55)) as pilot:
        await pilot.pause(3)
        app.action_toggle_batting()
        app.action_toggle_stats()
        await pilot.pause(2)
        svg = app.export_screenshot()
        Path("tests/screenshot.svg").write_text(svg)
        print("saved tests/screenshot.svg")
    config.save_favorites([])


if __name__ == "__main__":
    asyncio.run(main())
