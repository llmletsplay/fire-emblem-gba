from __future__ import annotations

import unittest
import tempfile
import copy
from pathlib import Path
from unittest.mock import patch

from src.link_arena.agents import AgentDecision, MinimaxAgent
from src.link_arena.bridge import SideBridge, parse_detail, parse_ui_state
from src.link_arena.autoplay import MinimaxAutoplay
from src.link_arena.control import UnsafeScreen, VerifiedInputController
from src.link_arena.coordinator import InvalidAction, LinkArenaCoordinator, StaleObservation


def _observation(*, state="player_phase", cursor=(0, 0), selection=0, menu=None):
    ui = {"name": "menu", "menu_type": menu, "selection": selection} if menu else {"name": state}
    return {
        "observation_id": "0-A-1",
        "side": "A",
        "generation": 0,
        "ui_state": ui,
        "detail": {"bm_cursor": list(cursor), "locked": False},
        "game_state": {"chapter": 65, "turn": 1, "players": "5/5", "npcs": "5/5"},
        "units": [
            {"team": "player", "character_id": 1, "position": [cursor[0], cursor[1]]},
            {"team": "npc", "character_id": 2, "position": [4, 1]},
        ],
        "coherent": True,
        "settled": True,
    }


def _endgame_observation(*, players="2/5", npcs="0/5", observation_id="endgame"):
    units = [
        {"team": "player", "character_id": 9,
         "hp": {"current": 44, "max": 60}, "inventory": []},
        {"team": "player", "character_id": 22,
         "hp": {"current": 60, "max": 60}, "inventory": []},
    ]
    if npcs != "0/5":
        units.append({"team": "npc", "character_id": 22,
                      "hp": {"current": 38, "max": 60}, "inventory": []})
    return {
        "observation_id": observation_id,
        "ui_state": {"name": "link_arena_map"},
        "game_state": {"chapter": 65, "players": players, "npcs": npcs},
        "detail": {"phase_raw": 1, "locked": False},
        "units": units,
        "coherent": True,
        "settled": True,
    }


class FakeCoordinator:
    def __init__(self, observation):
        self.current = observation
        self.sent = []

    def observe(self, side):
        return self.current

    def act(self, side, payload):
        self.sent.append(payload["buttons"])
        button = payload["buttons"][0]
        if self.current["ui_state"]["name"] == "menu":
            self.current["ui_state"]["selection"] += 1 if button == "DOWN" else -1
        else:
            cursor = self.current["detail"]["bm_cursor"]
            delta = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}[button]
            if self.current["ui_state"]["name"] == "link_arena_map" and button == "UP" and cursor[1] == 9:
                cursor[:] = [cursor[0], 1]
            elif self.current["ui_state"]["name"] == "link_arena_map" and button == "DOWN" and cursor[1] == 1:
                cursor[:] = [cursor[0], 9]
            else:
                cursor[:] = [cursor[0] + delta[0], cursor[1] + delta[1]]


class FakeBridge:
    def __init__(self):
        self.actions = []
        self.values = {
            "STATE": "player_phase",
            "GAMESTATE": "FE7|phase=player_phase|chapter=65|turn=1|cursor=0,0|locked=N|players=5/5|enemies=0/0|npcs=5/5",
            "DETAIL": "FE7_DETAIL|phase_raw=01|phase_name=unknown|chapter=65|turn=1|cursor=0,0|bm_cursor=0,0|bm_camera=0,0|bm_state=00000000|taken_action=0|locked=0|players_alive=5|enemies_alive=0",
            "UNITS": "FE7_UNITS|P:{id=1,cls=1,hp=20/20,pos=(0,0)}|N:{id=2,cls=1,hp=20/20,pos=(4,1)}",
        }

    def line(self, command):
        return self.values[command]

    def capture(self):
        return bytes(240 * 160 * 4)

    def act(self, buttons, *, hold_frames=None):
        self.actions.append((buttons, hold_frames))

    def close(self):
        pass


class LinkArenaControlTests(unittest.TestCase):
    def test_stale_observation_retries_once_when_generation_and_screen_are_unchanged(self):
        class RefreshOnceCoordinator:
            def __init__(self):
                self.current = _observation(state="player_phase", cursor=(1, 1))
                self.current["generation"] = 0
                self.calls = 0

            def observe(self, _side):
                self.current["observation_id"] = f"0-A-{self.calls + 1}"
                return copy.deepcopy(self.current)

            def act(self, _side, payload):
                self.calls += 1
                if self.calls == 1:
                    raise StaleObservation("another same-generation observation replaced this ID")
                self.asserted_id = payload["observation_id"]
                self.current["detail"]["bm_cursor"] = [2, 1]

        coordinator = RefreshOnceCoordinator()
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        result = controller.tap_direction("A", "RIGHT")

        self.assertEqual(coordinator.calls, 2)
        self.assertEqual(coordinator.asserted_id, "0-A-2")
        self.assertEqual(result["detail"]["bm_cursor"], [2, 1])

    def test_stale_observation_after_generation_change_is_never_replayed(self):
        class GenerationChangedCoordinator:
            def __init__(self):
                self.current = _observation(state="player_phase", cursor=(1, 1))
                self.current["generation"] = 0
                self.calls = 0

            def observe(self, _side):
                if self.current["generation"] == 0:
                    self.current["observation_id"] = "0-A-1"
                return copy.deepcopy(self.current)

            def act(self, _side, _payload):
                self.calls += 1
                self.current["generation"] = 1
                self.current["observation_id"] = "1-A-2"
                raise StaleObservation("the other side acted after this observation")

        coordinator = GenerationChangedCoordinator()
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        with self.assertRaisesRegex(UnsafeScreen, "game state changed"):
            controller.tap_direction("A", "RIGHT")

        self.assertEqual(coordinator.calls, 1)

    def test_visually_selected_link_arena_menu_can_settle_while_map_lock_is_set(self):
        observation = _observation(menu="item", selection=3)
        observation["detail"]["locked"] = True
        observation["settled"] = False
        class LockedMenuCoordinator:
            def observe(self, _side):
                return observation

        controller = VerifiedInputController(
            LockedMenuCoordinator(), poll_interval=0, settle_timeout=0.1,
        )
        self.assertIs(controller.observe_settled("A"), observation)

    def test_visually_classified_battle_forecast_can_settle_while_locked(self):
        observation = _observation()
        observation["ui_state"] = {"name": "battle_forecast"}
        observation["detail"]["locked"] = True
        observation["settled"] = False
        class LockedForecastCoordinator:
            def observe(self, _side):
                return observation

        controller = VerifiedInputController(
            LockedForecastCoordinator(), poll_interval=0, settle_timeout=0.1,
        )
        self.assertIs(controller.observe_settled("A"), observation)

    def test_parses_link_arena_menu_and_detail_cursor(self):
        assert parse_ui_state("menu:item:3") == {"name": "menu", "menu_type": "item", "selection": 3}
        detail = parse_detail(
            "FE7_DETAIL|phase_raw=01|chapter=65|cursor=0,0|bm_cursor=7,9|bm_camera=0,0|bm_state=00E10040|locked=0"
        )
        assert detail["bm_cursor"] == [7, 9]
        assert detail["bm_state"] == 0x00E10040
        assert detail["locked"] is False


    def test_move_cursor_verifies_one_press_per_tile(self):
        coordinator = FakeCoordinator(_observation(cursor=(1, 1)))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        result = controller.move_cursor_to("A", (3, 2))

        assert result["detail"]["bm_cursor"] == [3, 2]
        assert coordinator.sent == [["RIGHT"], ["RIGHT"], ["DOWN"]]


    def test_link_arena_vertical_cursor_steps_wrap_between_deployed_rows(self):
        coordinator = FakeCoordinator(_observation(state="link_arena_map", cursor=(7, 9)))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        top = controller.tap_direction("A", "UP")
        assert top["detail"]["bm_cursor"] == [7, 1]
        bottom = controller.tap_direction("A", "DOWN")
        assert bottom["detail"]["bm_cursor"] == [7, 9]
        assert coordinator.sent == [["UP"], ["DOWN"]]

    def test_map_cursor_can_skip_a_fallen_unit_tile(self):
        observation = _observation(state="link_arena_map", cursor=(8, 1))
        observation["units"] = [
            {"team": "player", "character_id": 1, "position": [8, 1],
             "hp": {"current": 20, "max": 20}},
            {"team": "player", "character_id": 3, "position": [6, 1],
             "hp": {"current": 20, "max": 20}},
            {"team": "npc", "character_id": 2, "position": [7, 1],
             "hp": {"current": 0, "max": 20}},
        ]

        class FallenTileCoordinator(FakeCoordinator):
            def act(self, side, payload):
                self.sent.append(payload["buttons"])
                if payload["buttons"] == ["LEFT"]:
                    # FE7 skips x=7 because the unit there has fallen.
                    self.current["detail"]["bm_cursor"][:] = [6, 1]
                else:
                    super().act(side, payload)

        coordinator = FallenTileCoordinator(observation)
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        result = controller.move_cursor_to("A", (6, 1))

        self.assertEqual(result["detail"]["bm_cursor"], [6, 1])
        self.assertEqual(coordinator.sent, [["LEFT"]])


    def test_map_edge_is_rejected_before_sending_input(self):
        coordinator = FakeCoordinator(_observation(cursor=(0, 0)))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        with self.assertRaisesRegex(UnsafeScreen, "off the map"):
            controller.tap_direction("A", "LEFT")

        assert coordinator.sent == []

    def test_unit_confirmation_uses_a_short_pulse(self):
        class RecordingCoordinator(FakeCoordinator):
            def __init__(self, observation):
                super().__init__(observation)
                self.frames = []

            def act(self, side, payload):
                self.frames.append(payload.get("hold_frames"))

        coordinator = RecordingCoordinator(_observation(cursor=(0, 0)))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)
        controller.confirm_unit_at_cursor(
            "A", team="player", character_id=1, expected_after=lambda _observation: True,
        )
        self.assertEqual(coordinator.frames, [3])


    def test_menu_row_is_checked_and_horizontal_menu_input_is_rejected(self):
        coordinator = FakeCoordinator(_observation(menu="item", selection=1))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        result = controller.tap_direction("A", "DOWN")
        assert result["ui_state"]["selection"] == 2
        with self.assertRaisesRegex(UnsafeScreen, "left/right"):
            controller.tap_direction("A", "RIGHT")
        assert coordinator.sent == [["DOWN"]]


    def test_unexpected_cursor_delta_fails_closed_after_press(self):
        class DriftCoordinator(FakeCoordinator):
            def act(self, side, payload):
                super().act(side, payload)
                self.current["detail"]["bm_cursor"][0] += 1

        coordinator = DriftCoordinator(_observation(cursor=(1, 1)))
        controller = VerifiedInputController(coordinator, poll_interval=0, settle_timeout=0.1)

        with self.assertRaisesRegex(UnsafeScreen, "expected cursor"):
            controller.tap_direction("A", "RIGHT")


    def test_coordinator_marks_only_repeated_coherent_snapshots_settled(self):
        bridge = FakeBridge()
        with tempfile.TemporaryDirectory() as folder:
            coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                               bridges={"A": bridge, "B": bridge})

            first = coordinator.observe("A")
            second = coordinator.observe("A")

            assert first["coherent"] is True
            assert first["settled"] is False
            assert second["settled"] is True
            assert second["detail"]["bm_cursor"] == [0, 0]
            coordinator.close()

    def test_coordinator_passes_valid_short_hold_to_bridge(self):
        bridge = FakeBridge()
        with tempfile.TemporaryDirectory() as folder:
            coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                               bridges={"A": bridge, "B": bridge})
            observation = coordinator.observe("A")
            result = coordinator.act("A", {
                "observation_id": observation["observation_id"],
                "buttons": ["A"], "hold_frames": 3,
            })
            self.assertEqual(result["hold_frames"], 3)
            self.assertEqual(bridge.actions, [(["A"], 3)])
            coordinator.close()

    def test_coordinator_rejects_unsafe_hold_duration_before_input(self):
        for hold_frames in (0, 13, True, 1.5):
            with self.subTest(hold_frames=hold_frames):
                bridge = FakeBridge()
                with tempfile.TemporaryDirectory() as folder:
                    coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                                       bridges={"A": bridge, "B": bridge})
                    observation = coordinator.observe("A")
                    with self.assertRaisesRegex(InvalidAction, "hold_frames"):
                        coordinator.act("A", {
                            "observation_id": observation["observation_id"],
                            "buttons": ["A"], "hold_frames": hold_frames,
                        })
                    self.assertEqual(bridge.actions, [])
                    coordinator.close()

    def test_side_bridge_encodes_short_confirmation_pulses(self):
        class RecordingSocket:
            def __init__(self):
                self.writes = []
            def gettimeout(self):
                return 8.0
            def settimeout(self, _timeout):
                pass
            def sendall(self, data):
                self.writes.append(data)
            def recv(self, _length):
                return b"QUEUE_COMPLETE\n"
            def close(self):
                pass

        bridge = SideBridge(1234)
        fake_socket = RecordingSocket()
        bridge._socket = fake_socket
        bridge.act(["A"], hold_frames=3)
        self.assertEqual(fake_socket.writes, [b"A@3;\n"])
        bridge.close()


    def test_cursor_change_without_game_state_change_invalidates_action(self):
        bridge = FakeBridge()
        with tempfile.TemporaryDirectory() as folder:
            coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                               bridges={"A": bridge, "B": bridge})
            observation = coordinator.observe("A")
            bridge.values["DETAIL"] = bridge.values["DETAIL"].replace("bm_cursor=0,0", "bm_cursor=1,0")

            with self.assertRaisesRegex(StaleObservation, "game state changed"):
                coordinator.act("A", {"observation_id": observation["observation_id"], "buttons": ["RIGHT"]})
            coordinator.close()

    def test_volatile_engine_bits_do_not_make_control_state_stale(self):
        class AnimatedBridge(FakeBridge):
            def __init__(self):
                super().__init__()
                self.state_bit = 0

            def line(self, command):
                if command == "DETAIL":
                    self.state_bit ^= 0x100
                    return self.values[command].replace("bm_state=00000000", f"bm_state={self.state_bit:08X}")
                return super().line(command)

        bridge = AnimatedBridge()
        with tempfile.TemporaryDirectory() as folder:
            coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                               bridges={"A": bridge, "B": bridge})
            observation = coordinator.observe("A")
            self.assertTrue(observation["coherent"])
            result = coordinator.act("A", {"observation_id": observation["observation_id"], "buttons": ["A"]})
            self.assertTrue(result["ok"])
            coordinator.close()

    def test_status_sampling_does_not_invalidate_a_fresh_observation(self):
        bridge = FakeBridge()
        with tempfile.TemporaryDirectory() as folder:
            coordinator = LinkArenaCoordinator({"A": 1, "B": 2}, {"A": "a", "B": "b"}, Path(folder),
                                               bridges={"A": bridge, "B": bridge})
            observation = coordinator.observe("A")
            coordinator.status()
            action = coordinator.act("A", {
                "observation_id": observation["observation_id"],
                "buttons": ["A"],
            })
            self.assertTrue(action["ok"])
            coordinator.close()

    def test_empty_boot_roster_is_not_a_terminal_match(self):
        observation = {"game_state": {"players": "0/0", "npcs": "0/0"}}
        self.assertIsNone(MinimaxAutoplay._terminal(observation))

    def test_startup_probe_maps_agent_roles_to_the_core_that_accepts_the_first_turn(self):
        class ActiveBridgeCoordinator:
            def __init__(self):
                self.active = "B"
                self.sent = []
                def local_view(cursor, bottom_team):
                    top_team = "npc" if bottom_team == "player" else "player"
                    units = [
                        {"team": top_team, "character_id": index, "position": [index + 5, 1]}
                        for index in range(5)
                    ] + [
                        {"team": bottom_team, "character_id": index + 10,
                         "position": [index + 5, 9]}
                        for index in range(5)
                    ]
                    return {
                        "observation_id": "0-test-1",
                        "ui_state": {"name": "link_arena_map"},
                        "detail": {"bm_cursor": list(cursor), "locked": False},
                        "game_state": {
                            "chapter": 65, "players": "5/5", "npcs": "5/5",
                        },
                        "units": units,
                        "coherent": True,
                        "settled": True,
                    }

                # Side A's bottom row is player; side B's is the opposing NPC
                # array. The active 1P bridge is deliberately B in this case.
                self.current = {
                    "A": local_view((8, 9), "player"),
                    "B": local_view((5, 9), "npc"),
                }

            def observe(self, side):
                return self.current[side]

            def act(self, side, payload):
                button = payload["buttons"][0]
                self.sent.append((side, button))
                if side != self.active:
                    return
                cursor = self.current[side]["detail"]["bm_cursor"]
                dx, dy = {"RIGHT": (1, 0), "LEFT": (-1, 0), "UP": (0, -1), "DOWN": (0, 1)}[button]
                cursor[:] = [cursor[0] + dx, cursor[1] + dy]

        coordinator = ActiveBridgeCoordinator()
        with tempfile.TemporaryDirectory() as folder:
            autoplay = MinimaxAutoplay(coordinator, Path(folder), poll_interval=0)
            autoplay._assign_agent_bridges()

        self.assertEqual(autoplay.agent_bridge, {"A": "B", "B": "A"})
        self.assertEqual(autoplay.agents["A"].own_team, "npc")
        self.assertEqual(autoplay.agents["B"].own_team, "player")
        self.assertEqual(coordinator.current["A"]["detail"]["bm_cursor"], [8, 9])
        self.assertEqual(coordinator.current["B"]["detail"]["bm_cursor"], [5, 9])
        self.assertEqual(coordinator.sent, [("A", "RIGHT"), ("B", "RIGHT"), ("B", "LEFT")])

    def test_saved_team_selection_roster_is_not_a_terminal_match(self):
        observation = {"game_state": {"players": "50/50", "npcs": "0/0"}}
        self.assertIsNone(MinimaxAutoplay._terminal(observation))

    def test_agent_team_orientation_tracks_the_roster_on_its_local_near_row(self):
        agent = MinimaxAgent("A")
        agent.set_own_team("npc")
        own, opponents = agent._teams(_observation())
        self.assertEqual([unit["character_id"] for unit in own], [2])
        self.assertEqual([unit["character_id"] for unit in opponents], [1])

    def test_weapon_menu_row_counts_unmodeled_weapons_and_skips_known_gear(self):
        observation = _observation()
        observation["units"] = [
            {
                "team": "player",
                "character_id": 22,
                "inventory": [
                    {"id": 0x84, "slot": 0, "uses": 20},  # Durandal, not scorer-modeled
                    {"id": 0x45, "slot": 1, "uses": 20},  # Luna
                    {"id": 0x7B, "slot": 2, "uses": 255},  # Iron Rune, no attack-menu row
                    {"id": 0x48, "slot": 3, "uses": 20},  # Fenrir
                    {"id": 0x70, "slot": 4, "uses": 255},  # Delphi Shield
                ],
            },
            {"team": "npc", "character_id": 11, "inventory": []},
        ]
        decision = AgentDecision(
            side="A", attacker_id=22, defender_id=11, weapon_id=0x48,
            weapon_name="Fenrir", inventory_slot=3, score=0.0,
            worst_reply_item=None,
        )

        row = MinimaxAgent("A").weapon_menu_row(observation, decision)

        self.assertEqual(row, 2)

    def test_weapon_menu_row_still_rejects_an_unknown_item_id(self):
        observation = _observation()
        observation["units"][0]["inventory"] = [
            {"id": 0x45, "slot": 0, "uses": 20},
            {"id": 0xFE, "slot": 1, "uses": 20},
        ]
        decision = AgentDecision(
            side="A", attacker_id=1, defender_id=2, weapon_id=0x45,
            weapon_name="Luna", inventory_slot=0, score=0.0,
            worst_reply_item=None,
        )

        with self.assertRaisesRegex(ValueError, "inventory item 254 is not classified"):
            MinimaxAgent("A").weapon_menu_row(observation, decision)

    def test_zero_live_roster_with_deployed_foe_is_terminal(self):
        observation = {"game_state": {"players": "0/5", "npcs": "1/5"}}
        result = MinimaxAutoplay._terminal(observation)
        self.assertEqual(result["winner"], "B")
        self.assertEqual(result["players_alive"], 0)

    def test_link_arena_winner_uses_fe_player_number_not_local_roster_label(self):
        # 1P/A can see its near row tagged "npc" in a rotated bridge view;
        # FE7's global P/N counts still map to the configured A=1P, B=2P order.
        result = MinimaxAutoplay._terminal({
            "game_state": {"players": "0/5", "npcs": "2/5"},
        })
        self.assertEqual(result["winner"], "B")

    def test_terminal_candidate_requires_both_settled_linked_maps_to_agree(self):
        one_npc_left = _endgame_observation(npcs="1/5", observation_id="A-map")
        transient_zero = _endgame_observation(observation_id="B-map")
        self.assertIsNone(MinimaxAutoplay._terminal_pair({
            "A": one_npc_left, "B": transient_zero,
        }))

        transient_zero["ui_state"] = {"name": "menu"}
        transient_zero["settled"] = False
        self.assertIsNone(MinimaxAutoplay._terminal_pair({
            "A": transient_zero, "B": transient_zero,
        }))

        terminal = _endgame_observation(observation_id="A-final")
        peer = _endgame_observation(observation_id="B-final")
        self.assertEqual(MinimaxAutoplay._terminal_pair({"A": terminal, "B": peer}), {
            "terminal": True, "players_alive": 2, "npcs_alive": 0, "winner": "A",
        })

    def test_turn_boundary_waits_when_only_one_linked_core_reports_zero_units(self):
        class TransientTerminalController:
            settle_timeout = 1.0

            def __init__(self):
                self.calls = {"A": 0, "B": 0}

            def observe_settled(self, side):
                self.calls[side] += 1
                npcs = "0/5" if side == "B" and self.calls[side] == 1 else "1/5"
                return _endgame_observation(
                    npcs=npcs, observation_id=f"{side}-{self.calls[side]}",
                )

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), poll_interval=0,
                                     roster_stability_seconds=0)
            runner.controller = TransientTerminalController()
            events = []
            runner._log = events.append

            runner._wait_for_turn_boundary(phase_raw_before=0)

        self.assertEqual(runner.controller.calls, {"A": 5, "B": 5})
        self.assertEqual(events[0]["type"], "terminal_waiting_for_peer")
        self.assertEqual(events[-1]["type"], "turn_boundary_ready")

    def test_match_completion_waits_for_four_paired_stable_terminal_reads(self):
        class StableTerminalController:
            settle_timeout = 1.0

            def __init__(self):
                self.calls = {"A": 0, "B": 0}

            def observe_settled(self, side):
                self.calls[side] += 1
                return _endgame_observation(observation_id=f"{side}-{self.calls[side]}")

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), poll_interval=0,
                                     roster_stability_seconds=0)
            runner.controller = StableTerminalController()
            events = []
            runner._log = events.append

            with self.assertRaises(StopIteration) as caught:
                runner._wait_for_turn_boundary(phase_raw_before=1)

        self.assertEqual(caught.exception.value["winner"], "A")
        self.assertEqual(runner.controller.calls, {"A": 4, "B": 4})
        self.assertEqual(events[-1]["type"], "terminal_roster_confirmed")

    def test_setup_only_runner_stops_at_gameplay_map_for_external_agents(self):
        events = []

        class PreparedSetup:
            def __init__(self, _coordinator, _controller, *, log, status, **_kwargs):
                self.log = log
                self.status = status

            def prepare_pair(self):
                self.status({"state": "ready", "stage": "opening_map"})
                self.log({"type": "setup_complete", "opening_map": "FE7 chapter 65"})

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), play_minimax=False, poll_interval=0)
            runner._log = events.append
            with patch("src.link_arena.autoplay.ArenaSetup", PreparedSetup):
                runner.run()

        self.assertEqual(runner.status, {"state": "ready", "stage": "opening_map"})
        self.assertFalse(runner.play_minimax)
        self.assertEqual([event["type"] for event in events],
                         ["runner_started", "setup_complete", "setup_ready"])

    def test_turn_boundary_waits_for_phase_banner_to_clear_before_next_agent(self):
        class SequencedController:
            settle_timeout = 1.0

            def __init__(self):
                self.calls = {"A": 0, "B": 0}
                self.states = {
                    "A": ["link_arena_map", "phase_transition", "link_arena_map",
                          "link_arena_map", "link_arena_map", "link_arena_map"],
                    "B": ["phase_transition", "link_arena_map", "link_arena_map",
                          "link_arena_map", "link_arena_map", "link_arena_map"],
                }

            def observe_settled(self, side):
                index = self.calls[side]
                self.calls[side] += 1
                return {
                    "observation_id": f"{side}-{index}",
                    "ui_state": {"name": self.states[side][index]},
                    "game_state": {
                        "chapter": 65, "players": "5/5", "npcs": "5/5",
                    },
                }

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), poll_interval=0,
                                     roster_stability_seconds=0)
            runner.controller = SequencedController()
            events = []
            runner._log = events.append

            runner._wait_for_turn_boundary()

        self.assertEqual(runner.controller.calls, {"A": 6, "B": 6})
        self.assertEqual([event["type"] for event in events],
                         ["turn_boundary_banner", "turn_boundary_ready"])

    def test_turn_boundary_accepts_synchronized_phase_byte_when_banner_is_absent(self):
        class ChangedPhaseController:
            settle_timeout = 1.0

            def __init__(self):
                self.calls = {"A": 0, "B": 0}

            def observe_settled(self, side):
                self.calls[side] += 1
                return {
                    "observation_id": f"{side}-map",
                    "ui_state": {"name": "link_arena_map"},
                    "game_state": {
                        "chapter": 65, "players": "5/5", "npcs": "5/5",
                    },
                    "detail": {"phase_raw": 0},
                }

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), poll_interval=0,
                                     roster_stability_seconds=0)
            runner.controller = ChangedPhaseController()
            events = []
            runner._log = events.append

            runner._wait_for_turn_boundary(phase_raw_before=1)

        self.assertEqual(runner.controller.calls, {"A": 4, "B": 4})
        self.assertEqual(events[0]["reason"], "phase_raw_changed")
        self.assertEqual(events[0]["phase_raw_after"], {"A": 0, "B": 0})

    def test_turn_boundary_restarts_stability_after_a_late_roster_change(self):
        class RosterSyncController:
            settle_timeout = 1.0

            def __init__(self):
                self.calls = {"A": 0, "B": 0}

            def observe_settled(self, side):
                index = self.calls[side]
                self.calls[side] += 1
                delayed_change = index == 2 and side == "B"
                npc_count = 4 if index < 2 else 3
                npc_hp = 12 if index < 2 else 10
                if delayed_change:
                    npc_count = 4
                    npc_hp = 12
                return {
                    "observation_id": f"{side}-{index}",
                    "ui_state": {"name": "link_arena_map"},
                    "game_state": {
                        "chapter": 65, "players": "5/5", "npcs": f"{npc_count}/5",
                    },
                    "detail": {"phase_raw": 0},
                    "units": [
                        {"team": "player", "character_id": 1,
                         "hp": {"current": 20, "max": 20}, "inventory": []},
                        {"team": "npc", "character_id": 2,
                         "hp": {"current": npc_hp, "max": 20}, "inventory": []},
                    ],
                }

        with tempfile.TemporaryDirectory() as folder:
            runner = MinimaxAutoplay(object(), Path(folder), poll_interval=0,
                                     roster_stability_seconds=0)
            runner.controller = RosterSyncController()
            events = []
            runner._log = events.append

            runner._wait_for_turn_boundary(phase_raw_before=1)

        self.assertEqual(runner.controller.calls, {"A": 7, "B": 7})
        self.assertEqual(events[0]["type"], "turn_boundary_waiting_for_roster_sync")
        self.assertEqual(events[-1]["type"], "turn_boundary_ready")
        self.assertEqual(events[-1]["roster_sync_reads"], 4)
