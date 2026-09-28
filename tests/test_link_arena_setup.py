from __future__ import annotations

import base64
import struct
import unittest
import zlib

from src.link_arena.bridge import parse_ui_state
from src.link_arena.setup import ArenaSetup, title_menu_band_count, title_menu_state
from src.link_arena.control import UnsafeScreen
from src.link_arena.coordinator import StaleObservation


def _menu_observation(row_count: int, selected: int | tuple[int, ...]) -> dict:
    width, height = 240, 160
    pixels = bytearray([0, 0, 0, 255] * width * height)
    first_top = 27 if row_count == 4 else 15
    tops = [first_top + index * 24 for index in range(row_count)]
    for top in tops:
        for y in range(top, top + 18):
            for x in range(55, 185):
                offset = (y * width + x) * 4
                pixels[offset : offset + 4] = bytes((30, 90, 180, 255))
    for selected_row in (selected,) if isinstance(selected, int) else selected:
        top = tops[selected_row]
        for y in range(top + 1, top + 6):
            for x in range(185, 201):
                offset = (y * width + x) * 4
                pixels[offset : offset + 4] = bytes((250, 190, 70, 255))

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * width * 4 : (y + 1) * width * 4])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )
    return {"screenshot": "data:image/png;base64," + base64.b64encode(png).decode("ascii")}


def _weapon_panel_png(selected_row: int) -> bytes:
    width, height = 240, 160
    pixels = bytearray([70, 75, 80, 255] * width * height)
    left, top, right, bottom = 14, 14, 113, 97
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            offset = (y * width + x) * 4
            pixels[offset : offset + 4] = bytes((40, 50, 120, 255))
    center_y = top + 11 + selected_row * 16
    for y in range(center_y - 4, center_y + 4):
        for x in range(1, 8):
            offset = (y * width + x) * 4
            pixels[offset : offset + 4] = bytes((230, 230, 230, 255))

    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * width * 4 : (y + 1) * width * 4])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _battle_forecast_png() -> bytes:
    width, height = 240, 160
    pixels = bytearray([70, 75, 80, 255] * width * height)
    for y in range(6, 74):
        for x in range(160, 226):
            offset = (y * width + x) * 4
            pixels[offset : offset + 4] = bytes((40, 50, 120, 255))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * width * 4 : (y + 1) * width * 4])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _unit_status_png(*, left: int = 166, top: int = 7, panel_height: int = 80) -> bytes:
    width, height = 240, 160
    pixels = bytearray([70, 75, 80, 255] * width * height)
    for y in range(top, top + panel_height):
        for x in range(left, left + 68):
            offset = (y * width + x) * 4
            pixels[offset : offset + 4] = bytes((40, 50, 120, 255))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * width * 4 : (y + 1) * width * 4])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


def _phase_transition_png(*, banner: bool) -> bytes:
    width, height = 240, 160
    pixels = bytearray([70, 75, 80, 255] * width * height)
    if banner:
        for y in range(70, 95):
            for x in range(20, 220):
                offset = (y * width + x) * 4
                pixels[offset : offset + 4] = bytes((30, 220, 60, 255))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        rows.extend(pixels[y * width * 4 : (y + 1) * width * 4])

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows)))
        + chunk(b"IEND", b"")
    )


class LinkArenaSetupTests(unittest.TestCase):
    def test_pair_stages_both_team_pickers_before_confirming_either(self):
        setup = ArenaSetup(
            object(), object(), log=lambda _event: None,
            status=lambda _value: None, transition_timeout=0.1, poll_interval=0,
        )
        calls = []
        setup._select_linked_battle_team = lambda side: calls.append(("picker", side))
        setup._confirm_default_team = lambda side: calls.append(("confirm", side))
        setup._connect_and_start = lambda: calls.append(("connect",))

        setup.prepare_pair()

        self.assertEqual(
            calls,
            [("picker", "A"), ("picker", "B"), ("confirm", "A"),
             ("confirm", "B"), ("connect",)],
        )

    def test_title_and_extras_menu_selection_is_read_from_marker(self):
        self.assertEqual(title_menu_state(_menu_observation(4, 2)), ("main", 2))
        self.assertEqual(title_menu_state(_menu_observation(5, 4)), ("extras", 4))
        blinking = _menu_observation(4, ())
        self.assertIsNone(title_menu_state(blinking))
        self.assertEqual(title_menu_band_count(blinking), 4)

    def test_ambiguous_menu_marker_fails_closed(self):
        self.assertIsNone(title_menu_state(_menu_observation(4, (1, 3))))

    def test_stale_battle_byte_is_reinterpreted_only_for_unlocked_arena_phase(self):
        parsed = parse_ui_state(
            "battle",
            game_state={"chapter": 65, "phase": "player_phase"},
            detail={"locked": False},
        )
        self.assertEqual(parsed["name"], "player_phase")
        self.assertEqual(parsed["raw_name"], "battle")
        self.assertEqual(
            parse_ui_state(
                "battle",
                game_state={"chapter": 1, "phase": "player_phase"},
                detail={"locked": False},
            ),
            {"name": "battle"},
        )

    def test_impossible_menu_flag_is_map_only_with_chapter_65_deployed_rosters(self):
        game_state = {"chapter": 65, "players": "5/5", "npcs": "5/5"}
        detail = {"locked": False, "bm_cursor": [8, 9]}
        self.assertEqual(
            parse_ui_state("menu:0xE1:48", game_state=game_state, detail=detail),
            {"name": "link_arena_map", "raw_name": "menu:0xE1:48", "source": "fe7_ch65_map"},
        )
        self.assertEqual(
            parse_ui_state("menu:arena:0", game_state=game_state, detail=detail),
            {"name": "menu", "menu_type": "arena", "selection": 0},
        )
        self.assertEqual(
            parse_ui_state(
                "menu:0xE1:48",
                game_state={"chapter": 65, "players": "50/50", "npcs": "0/0"},
                detail=detail,
            )["name"],
            "menu",
        )

    def test_link_arena_phase_banner_is_not_misclassified_as_actionable_map(self):
        game_state = {"chapter": 65, "players": "5/5", "npcs": "5/5"}
        detail = {"locked": False, "bm_cursor": [8, 9]}
        self.assertEqual(
            parse_ui_state(
                "menu:0xE1:48", game_state=game_state, detail=detail,
                screenshot_png=_phase_transition_png(banner=True),
            ),
            {"name": "phase_transition", "source": "fe7_ch65_player_phase_banner"},
        )
        self.assertEqual(
            parse_ui_state(
                "menu:0xE1:48", game_state=game_state, detail=detail,
                screenshot_png=_phase_transition_png(banner=False),
            )["name"],
            "link_arena_map",
        )

    def test_link_arena_weapon_menu_requires_unique_wedge_and_reads_exact_row(self):
        game_state = {"chapter": 65, "players": "4/5", "npcs": "5/5"}
        detail = {"locked": True, "bm_cursor": [6, 1]}
        for row in range(5):
            with self.subTest(row=row):
                parsed = parse_ui_state(
                    "menu:0xE1:48", game_state=game_state, detail=detail,
                    screenshot_png=_weapon_panel_png(row),
                )
                self.assertEqual(parsed, {
                    "name": "menu", "menu_type": "item", "selection": row,
                    "source": "fe7_ch65_weapon_panel",
                })

    def test_link_arena_battle_forecast_is_a_confirm_only_screen(self):
        parsed = parse_ui_state(
            "menu:0xE1:48",
            game_state={"chapter": 65, "players": "4/5", "npcs": "5/5"},
            detail={"locked": True, "bm_cursor": [6, 1]},
            screenshot_png=_battle_forecast_png(),
        )
        self.assertEqual(parsed, {"name": "battle_forecast", "source": "fe7_ch65_forecast"})

    def test_selected_unit_status_panel_is_a_confirm_only_attack_gate(self):
        for index, screenshot in enumerate(
            (
                _unit_status_png(),
                _unit_status_png(top=27, panel_height=93),
                _unit_status_png(left=6, top=27, panel_height=93),
            )
        ):
            with self.subTest(panel=index):
                parsed = parse_ui_state(
                    "menu:0xE1:48",
                    game_state={"chapter": 65, "players": "4/5", "npcs": "4/5"},
                    detail={"locked": False, "bm_cursor": [6, 1]},
                    screenshot_png=screenshot,
                )
                self.assertEqual(parsed, {
                    "name": "unit_status", "source": "fe7_ch65_selected_unit_status",
                })

    def test_arena_map_requires_chapter_phase_and_both_five_unit_rosters(self):
        observation = {
            "ui_state": {"name": "player_phase"},
            "game_state": {"chapter": 65, "players": "5/5", "npcs": "5/5"},
        }
        self.assertTrue(ArenaSetup.is_arena_map(observation))
        observation["game_state"]["players"] = "0/0"
        self.assertFalse(ArenaSetup.is_arena_map(observation))

    def test_startup_tap_retries_stale_observation_only_inside_boot_gate(self):
        class FakeController:
            def observe_settled(self, side):
                return {
                    "observation_id": "0-A-1",
                    "game_state": {
                        "chapter": 0,
                        "phase": "start_screen",
                        "players": "0/0",
                        "npcs": "0/0",
                    },
                    "ui_state": {"name": "menu", "menu_type": "0x10", "selection": 48},
                    "coherent": True,
                    "settled": True,
                    **_menu_observation(0, ()),
                }

        class FakeCoordinator:
            def __init__(self):
                self.attempts = 0

            def act(self, side, payload):
                self.attempts += 1
                if self.attempts == 1:
                    raise StaleObservation("animated startup frame")

        events = []
        coordinator = FakeCoordinator()
        setup = ArenaSetup(
            coordinator, FakeController(), log=events.append, status=lambda _value: None,
            transition_timeout=0.1, poll_interval=0,
        )
        setup._press_startup("A")
        self.assertEqual(coordinator.attempts, 2)
        self.assertEqual(len(events), 1)

    def test_startup_gate_will_not_tap_start_over_a_visible_menu(self):
        class FakeController:
            def observe_settled(self, side):
                return {
                    "observation_id": "0-A-1",
                    "game_state": {
                        "chapter": 0,
                        "phase": "start_screen",
                        "players": "0/0",
                        "npcs": "0/0",
                    },
                    "ui_state": {"name": "menu"},
                    "coherent": True,
                    "settled": True,
                    **_menu_observation(4, 2),
                }

        class FakeCoordinator:
            def __init__(self):
                self.attempts = 0

            def act(self, side, payload):
                self.attempts += 1

        coordinator = FakeCoordinator()
        setup = ArenaSetup(
            coordinator, FakeController(), log=lambda _event: None, status=lambda _value: None,
            transition_timeout=0.1, poll_interval=0,
        )
        with self.assertRaisesRegex(UnsafeScreen, "guarded START"):
            setup._press_startup("A")
        self.assertEqual(coordinator.attempts, 0)

    def test_title_menu_keeps_the_latest_observation_after_stability_reads(self):
        class FakeCoordinator:
            def __init__(self):
                self.row = 0
                self.sequence = 0
                self.latest = {}
                self.moves = []

            def observe(self, side):
                self.sequence += 1
                observation_id = f"0-{side}-{self.sequence}"
                self.latest[side] = observation_id
                return {
                    "observation_id": observation_id,
                    "game_state": {"chapter": 0, "phase": "start_screen", "players": "0/0", "npcs": "0/0"},
                    "ui_state": {"name": "not_in_game"},
                    "screenshot": _menu_observation(4, self.row)["screenshot"],
                    "coherent": True,
                    "settled": True,
                }

            def status(self):
                return {"sides": {"A": {"coherent": True, "settled": True}}}

            def act(self, side, payload):
                if payload["observation_id"] != self.latest[side]:
                    raise StaleObservation("stale title observation")
                self.moves.append(payload["buttons"])
                self.row = (self.row + 1) % 4

        class FakeController:
            def __init__(self, coordinator):
                self.coordinator = coordinator

            def observe_settled(self, side):
                return self.coordinator.observe(side)

        coordinator = FakeCoordinator()
        setup = ArenaSetup(
            coordinator, FakeController(coordinator), log=lambda _event: None,
            status=lambda _value: None, transition_timeout=0.2, poll_interval=0,
        )
        result = setup._move_title_menu("A", "main", 3)
        self.assertEqual(coordinator.moves, [["DOWN"], ["DOWN"], ["DOWN"]])
        self.assertEqual(title_menu_state(result), ("main", 3))
        self.assertEqual(result["observation_id"], coordinator.latest["A"])


if __name__ == "__main__":
    unittest.main()
