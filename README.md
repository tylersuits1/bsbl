# sportspages-tui

A newspaper-styled terminal UI for following MLB games — the same spirit
as the [the-sports-pages](https://github.com/tylersuits1/the-sports-pages)
Flutter app, but for the terminal, in the tradition of tools like
Newsboat: launch it, swipe left/right between your teams, scroll up/down
through the news, single-letter hotkeys for everything else.

Built with [Textual](https://textual.textualize.io/), pulling live data
from the free, keyless MLB Stats API (`statsapi.mlb.com`) and ESPN's
public news/odds feeds — no API key required, no account, nothing to
sign up for.

## Status

v1, MLB only. NCAAF (college football) is a planned fast-follow once this
shell is proven out — see the Flutter sibling app for the fuller feature
set this is working toward (divisions/conferences, AP rankings, quarter
scores, game leaders, reader-view headlines).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
sportspages
# or: python -m sportspages_tui
```

On first launch (no followed teams yet) it opens the team picker
directly. Your followed teams persist between runs in
`~/.config/sportspages-tui/favorites.json` — unlike the Flutter app,
where favorites reset on restart.

## Keys

| Key     | Action                              |
|---------|--------------------------------------|
| ← / →   | Switch between followed teams        |
| ↑ / ↓   | Scroll headlines / page content      |
| `s`     | Toggle player stats                  |
| `b`     | Toggle batting order                 |
| `r`     | Refresh now                          |
| `a`     | Follow / unfollow teams              |
| `p`     | Pause / resume live auto-refresh     |
| `d`     | Toggle dark / light theme            |
| `?`     | Help screen                          |
| `q`     | Quit                                 |

Live scores auto-refresh every 20 seconds while a game is in progress,
same cadence as the Flutter app, and stop once the game goes final.

## Project layout

```
sportspages_tui/
├── app.py              # Textual App — main screen, key bindings, live refresh
├── rendering.py         # pure functions building the Rich renderables (masthead, box score, etc.)
├── mlb_api.py           # MLB Stats API + ESPN news/odds clients (async)
├── mlb_teams.py         # static team/league/division table
├── models.py            # dataclasses (BoxScore, TeamSide, PlayerStat, Headline, ...)
├── config.py            # favorites persistence (~/.config/sportspages-tui/)
├── date_format.py       # short (body) vs full (masthead) date formatting
├── screens/
│   ├── team_picker.py   # MLB > league > division > team, with search
│   └── help.py          # keybinding reference overlay
└── app.tcss              # styling
```

## Testing

No live game finishing during development makes the "up next" /
completed-game path hard to eyeball manually, so there's a headless
smoke test that drives the real app (via Textual's test pilot) against
live data and asserts on state — team switching, panel toggles, live
data actually arriving:

```bash
python tests/smoke_test.py
```

`tests/screenshot_test.py` dumps an SVG render of the live app to
`tests/screenshot.svg` for visual spot-checks (gitignored, not meant to
be committed).
