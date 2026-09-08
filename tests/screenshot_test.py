import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bsbl import config
from bsbl.app import BsblApp


async def main() -> None:
    config.save_favorites([("MLB", "ATL"), ("MLB", "MIL")])
    app = BsblApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause(4)
        svg = app.export_screenshot()
        Path("tests/screenshot.svg").write_text(svg)
        print("saved tests/screenshot.svg")
    config.save_favorites([])


if __name__ == "__main__":
    asyncio.run(main())
