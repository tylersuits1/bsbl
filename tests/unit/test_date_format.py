"""date_format.py is pure and platform-sensitive — format_full_date/
format_short_date/format_clock_time used to use the '%-d'/'%-I' glibc/BSD
strftime extensions, which raise ValueError on native Windows Python
(no GNU no-padding flag support in the MSVC runtime). Regression-tests
the portable replacement as much as the actual output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bsbl.date_format import (
    format_clock_time,
    format_full_date,
    format_short_date,
    format_short_datetime,
    ordinal_inning,
)

_EASTERN = timezone(timedelta(hours=-4))


def test_format_full_date_no_leading_zero_on_single_digit_day():
    dt = datetime(2026, 8, 5, 16, 10, tzinfo=_EASTERN)
    assert format_full_date(dt) == "Wed, Aug 5, 2026"


def test_format_full_date_double_digit_day():
    dt = datetime(2026, 8, 29, 16, 10, tzinfo=_EASTERN)
    assert format_full_date(dt) == "Sat, Aug 29, 2026"


def test_format_short_date_has_no_year():
    dt = datetime(2026, 8, 29, 16, 10, tzinfo=_EASTERN)
    assert format_short_date(dt) == "Sat, Aug 29"


@pytest.mark.parametrize(
    "hour, minute, expected",
    [
        (16, 10, "4:10 PM"),
        (9, 5, "9:05 AM"),
        (0, 5, "12:05 AM"),   # midnight edge case
        (12, 0, "12:00 PM"),  # noon edge case
        (23, 59, "11:59 PM"),
        (1, 0, "1:00 AM"),
    ],
)
def test_format_clock_time(hour, minute, expected):
    dt = datetime(2026, 8, 5, hour, minute, tzinfo=_EASTERN)
    assert format_clock_time(dt) == expected


def test_format_clock_time_converts_to_local():
    # 8pm UTC is 4pm Eastern (-4h) — format_clock_time should localize,
    # not just format the tz the datetime happens to carry.
    dt = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)
    local = dt.astimezone(_EASTERN)
    assert format_clock_time(dt) == format_clock_time(local)


def test_format_short_datetime_combines_date_and_time():
    dt = datetime(2026, 8, 5, 16, 10, tzinfo=_EASTERN)
    assert format_short_datetime(dt) == "Wed, Aug 5 · 4:10 PM"


@pytest.mark.parametrize(
    "n, expected",
    [
        (1, "First"),
        (2, "Second"),
        (9, "Ninth"),
        (20, "Twentieth"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (24, "24th"),
        (11, "Eleventh"),  # covered by the word table, not the 11-13 "th" rule
        (111, "111th"),   # past the word table: 11-13 exception applies even past 100
        (112, "112th"),
        (113, "113th"),
        (101, "101st"),
    ],
)
def test_ordinal_inning(n, expected):
    assert ordinal_inning(n) == expected
