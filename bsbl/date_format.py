"""Date/time formatting — mirrors the Flutter app's convention of a full
date (with year) only in the masthead, and a short date (no year)
everywhere else in the body.
"""

from __future__ import annotations

from datetime import datetime

_ORDINAL_WORDS = [
    "",
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
    "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth",
    "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth",
    "Nineteenth", "Twentieth",
]


def format_full_date(dt: datetime) -> str:
    """'Sat, Aug 29, 2026' — masthead only."""
    return dt.strftime("%a, %b %-d, %Y")


def format_short_date(dt: datetime) -> str:
    """'Sat, Aug 29' — no year, for the page body."""
    return dt.strftime("%a, %b %-d")


def format_clock_time(dt: datetime) -> str:
    """'4:10 PM' in local time."""
    local = dt.astimezone()
    return local.strftime("%-I:%M %p")


def format_short_datetime(dt: datetime) -> str:
    return f"{format_short_date(dt.astimezone())} · {format_clock_time(dt)}"


def ordinal_inning(n: int) -> str:
    """1 -> 'First', 2 -> 'Second', ... falls back to a numeric suffix for
    the rare extra-inning game that runs past the 20th.
    """
    if 1 <= n < len(_ORDINAL_WORDS):
        return _ORDINAL_WORDS[n]
    last_two = n % 100
    if 11 <= last_two <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
