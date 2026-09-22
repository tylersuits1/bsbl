"""config.py persistence — every test runs against a throwaway config
dir via the autouse `isolated_config` fixture in conftest.py, never the
real ~/.config/bsbl/favorites.json.
"""

from __future__ import annotations

from bsbl import config


def test_load_favorites_empty_when_no_file():
    assert config.load_favorites() == []


def test_save_and_load_favorites_round_trip():
    config.save_favorites([("MLB", "ATL"), ("MLB", "MIL")])
    assert config.load_favorites() == [("MLB", "ATL"), ("MLB", "MIL")]


def test_load_favorites_migrates_legacy_abbreviations_key(isolated_config):
    isolated_config.mkdir(parents=True, exist_ok=True)
    (isolated_config / "favorites.json").write_text('{"abbreviations": ["ATL", "MIL"]}')
    assert config.load_favorites() == [("MLB", "ATL"), ("MLB", "MIL")]


def test_load_favorites_ignores_non_mlb_sport_tag():
    # An older on-disk entry from a since-removed sport shouldn't crash
    # loading, and app.py filters non-MLB entries out itself — but the
    # raw (sport, abbr) tuple should still come back from load_favorites.
    config.save_favorites([("MLB", "ATL"), ("NFL", "KC")])
    assert config.load_favorites() == [("MLB", "ATL"), ("NFL", "KC")]


def test_load_favorites_handles_corrupt_json(isolated_config):
    isolated_config.mkdir(parents=True, exist_ok=True)
    (isolated_config / "favorites.json").write_text("{not valid json")
    assert config.load_favorites() == []


def test_toggle_favorite_adds_then_removes():
    updated, applied = config.toggle_favorite("MLB", "ATL")
    assert applied is True
    assert updated == [("MLB", "ATL")]

    updated, applied = config.toggle_favorite("MLB", "ATL")
    assert applied is True
    assert updated == []


def test_toggle_favorite_respects_max_favorites():
    for i in range(config.MAX_FAVORITES):
        _, applied = config.toggle_favorite("MLB", f"T{i}")
        assert applied is True

    _, applied = config.toggle_favorite("MLB", "ONE_TOO_MANY")
    assert applied is False
    assert len(config.load_favorites()) == config.MAX_FAVORITES


def test_load_players_empty_when_no_file():
    assert config.load_players() == []


def test_save_and_load_players_round_trip():
    players = [{"player_id": 1, "name": "Ronald Acuña Jr.", "position": "RF", "team_abbr": "ATL"}]
    config.save_players(players)
    assert config.load_players() == players


def test_toggle_player_adds_then_removes():
    player = {"player_id": 42, "name": "Test Player", "position": "SS", "team_abbr": "ATL"}
    updated, applied = config.toggle_player(player)
    assert applied is True
    assert updated == [player]

    updated, applied = config.toggle_player({"player_id": 42})
    assert applied is True
    assert updated == []


def test_toggle_player_respects_max_players():
    for i in range(config.MAX_PLAYERS):
        _, applied = config.toggle_player({"player_id": i, "name": f"Player {i}"})
        assert applied is True

    _, applied = config.toggle_player({"player_id": "one_too_many", "name": "Nope"})
    assert applied is False
    assert len(config.load_players()) == config.MAX_PLAYERS


def test_favorites_and_players_persist_independently():
    config.save_favorites([("MLB", "ATL")])
    config.save_players([{"player_id": 1, "name": "X"}])
    assert config.load_favorites() == [("MLB", "ATL")]
    assert config.load_players() == [{"player_id": 1, "name": "X"}]
