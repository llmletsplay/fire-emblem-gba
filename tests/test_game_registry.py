from src.data.game_registry import GAME_REGISTRY, get_game_info


def test_registry_contains_supported_gba_fire_emblem_games():
    assert set(GAME_REGISTRY) == {"BE8E", "AE7E"}
    assert GAME_REGISTRY["AE7E"].game_id == "fe7"
    assert GAME_REGISTRY["BE8E"].game_id == "fe8"


def test_get_game_info_by_id():
    fe7 = get_game_info("fe7")
    fe8 = get_game_info("fe8")

    assert fe7 is not None
    assert fe7.rom_code == "AE7E"
    assert "Blazing Blade" in fe7.title
    assert fe7.addresses.player_units == 0x0202BD08

    assert fe8 is not None
    assert fe8.rom_code == "BE8E"
    assert "Sacred Stones" in fe8.title
    assert fe8.addresses.player_units == 0x0202BE4C


def test_unknown_game_info_is_none():
    assert get_game_info("fe6") is None
