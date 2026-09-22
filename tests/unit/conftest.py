"""Shared fixtures for the offline unit test suite — no network, no real
`~/.config/bsbl`. See tests/smoke_test.py etc. for the live/manual tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bsbl import config
from bsbl.models import BoxScore, GameStatus, LineScore, TeamSide


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets its own throwaway config dir — never touches the
    real user's ~/.config/bsbl/favorites.json.
    """
    config_dir = tmp_path / "bsbl-config"
    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "FAVORITES_FILE", config_dir / "favorites.json")
    return config_dir


def make_box_score(**overrides) -> BoxScore:
    """A minimal-but-complete BoxScore with sensible defaults, so each
    test only has to override the one or two fields it cares about.
    """
    defaults = dict(
        home=TeamSide(name="Braves", city="Atlanta", abbreviation="ATL", score=1),
        away=TeamSide(name="Phillies", city="Philadelphia", abbreviation="PHI", score=3),
        home_line=LineScore(runs=1, hits=2, errors=0),
        away_line=LineScore(runs=3, hits=5, errors=1),
        away_innings=[0, 3, 0],
        home_innings=[1, 0, 0],
        inning_half="Top",
        inning=4,
        venue="Truist Park",
        weather="Cloudy, 74°F",
        home_pitcher="Chris Sale",
        home_pitcher_ip="3.0 IP",
        away_pitcher="Aaron Nola",
        away_pitcher_ip="3.0 IP",
        status=GameStatus.LIVE,
    )
    defaults.update(overrides)
    return BoxScore(**defaults)


@pytest.fixture
def box_score():
    return make_box_score


def aware(*args, **kwargs) -> datetime:
    """A UTC-aware datetime — every timestamp in the models is expected
    to carry tzinfo.
    """
    return datetime(*args, tzinfo=timezone.utc, **kwargs)
