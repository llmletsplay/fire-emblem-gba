"""Unattended FE7 Link Arena setup and minimax driver.

The runner navigates the prepared title/Extras/Link Arena path, completes the
link handshake, and then executes policy-selected exchanges with verified
single-button cursor and menu steps. An unknown transition stops for
supervision before it sends another input.
"""

from __future__ import annotations

import base64
import json
import hashlib
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .agents import AgentDecision, MinimaxAgent
from .control import (
    UnsafeScreen,
    VerifiedInputController,
    _DIRECTION_DELTA,
    _MAP_STATES,
    _cursor,
    _directional_cursor_target,
    _ui,
)
from .setup import ArenaSetup
from .scores import is_points_bonus_transition, read_final_result_screen


class MinimaxAutoplay:
    def __init__(
        self,
        coordinator: Any,
        match_dir: Path,
        *,
        play_minimax: bool = True,
        poll_interval: float = 0.5,
        settle_timeout: float = 60.0,
        roster_stability_seconds: float = 3.0,
        decision_ledger: Any | None = None,
        match_id: str | None = None,
        agents: Mapping[str, MinimaxAgent] | None = None,
    ):
        self.coordinator = coordinator
        self.match_dir = match_dir
        self.play_minimax = play_minimax
        self.poll_interval = poll_interval
        self.roster_stability_seconds = max(0.0, roster_stability_seconds)
        self.controller = VerifiedInputController(
            coordinator,
            poll_interval=min(0.1, poll_interval),
            settle_timeout=settle_timeout,
        )
        self.agents = {side: MinimaxAgent(side) for side in ("A", "B")}
        if agents is not None:
            for side, agent in agents.items():
                normalized_side = side.upper()
                if normalized_side not in self.agents:
                    raise ValueError(f"unknown Link Arena agent side: {side!r}")
                if agent.side != normalized_side:
                    raise ValueError(f"agent assigned to {normalized_side} has side {agent.side}")
                self.agents[normalized_side] = agent
        kinds = [agent.benchmark_metadata().get("kind") for agent in self.agents.values()]
        hosted_count = sum(kind == "hosted_language_model" for kind in kinds)
        self.stream_mode = "supervised" if not play_minimax else (
            "llm_duel" if hosted_count == 2 else
            "mixed_agents" if hosted_count == 1 else
            "minimax"
        )
        # mGBA can start either linked Lua VM first, so bridge labels are not
        # a reliable proxy for the 1P/2P controllers.
        self.agent_bridge = {"A": "A", "B": "B"}
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.log_path = match_dir / "minimax-autoplay.jsonl"
        self.decision_ledger = decision_ledger
        self.match_id = match_id
        self._pending_decision_id: str | None = None
        self._policy_sha256 = self._policy_fingerprint()
        self.status: dict[str, Any] = {"state": "waiting_for_link_arena_map"}

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            raise RuntimeError("minimax autoplay is already running")
        self.thread = threading.Thread(target=self.run, name="link-arena-minimax", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _log(self, event: dict[str, Any]) -> None:
        event = {"timestamp": time.time(), **event}
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
        if self.decision_ledger is not None and self.match_id is not None:
            self.decision_ledger.record(self.match_id, event)

    @staticmethod
    def _policy_fingerprint() -> str:
        digest = hashlib.sha256()
        for filename in ("agents.py", "minimax.py"):
            path = Path(__file__).with_name(filename)
            digest.update(filename.encode("utf-8") + b"\0")
            digest.update(path.read_bytes())
        return digest.hexdigest()

    @staticmethod
    def _unit(agent: MinimaxAgent, observation: dict[str, Any], character_id: int, *, own: bool) -> dict[str, Any]:
        own_units, opposing_units = agent._teams(observation)
        source = own_units if own else opposing_units
        unit = next((candidate for candidate in source
                     if int(candidate.get("character_id", -1)) == character_id), None)
        if unit is None:
            role = "own" if own else "opposing"
            raise UnsafeScreen(f"selected {role} unit {character_id} is no longer on the board")
        position = unit.get("position")
        if not isinstance(position, list) or len(position) != 2:
            raise UnsafeScreen(f"selected unit {character_id} has no map coordinate")
        return unit

    @staticmethod
    def _unit_is_live(unit: dict[str, Any]) -> bool:
        hp = unit.get("hp")
        current = hp.get("current") if isinstance(hp, dict) else None
        return not (isinstance(current, int) and current <= 0)

    @staticmethod
    def _terminal(observation: dict[str, Any]) -> dict[str, Any] | None:
        state = observation.get("game_state", {})
        def counts(key: str) -> tuple[int, int] | None:
            value = state.get(key)
            if not isinstance(value, str) or "/" not in value:
                return None
            try:
                alive_count, total_count = (int(part) for part in value.split("/", 1))
                return alive_count, total_count
            except ValueError:
                return None
        players, npcs = counts("players"), counts("npcs")
        if players is None or npcs is None:
            return None
        player_alive, player_total = players
        npc_alive, npc_total = npcs
        # Before deployment the prepared save reports a 50-unit player roster
        # and 0/0 NPCs. That is team selection, not a finished 50–0 match.
        # This autoplay is scoped to the five-unit RAGNAROK teams.
        if player_total != 5 or npc_total != 5:
            return None
        if player_alive == 0 or npc_alive == 0:
            # Setup always schedules agent A as FE7's selected 1P-first side
            # and agent B as 2P. ``players``/``npcs`` are global game counts;
            # per-bridge MinimaxAgent.own_team labels can flip with the local
            # camera and must not be used to assign a tournament winner.
            winner = "B" if player_alive == 0 and npc_alive > 0 else (
                "A" if npc_alive == 0 and player_alive > 0 else "draw"
            )
            return {"terminal": True, "players_alive": player_alive, "npcs_alive": npc_alive,
                    "winner": winner}
        return None

    @classmethod
    def _terminal_pair(
        cls, observations: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Accept a terminal candidate only when both linked maps agree.

        FE7 temporarily removes fighters from its map counts while combat
        panels are open. One linked core can also publish a casualty before
        its peer, so a single zero count is never enough. Repeated stability
        is enforced by the turn-boundary loop.
        """
        if not all(side in observations for side in ("A", "B")):
            return None
        first, second = observations["A"], observations["B"]
        first_result = cls._terminal(first)
        second_result = cls._terminal(second)
        if not first_result or not second_result:
            return None
        result_keys = ("winner", "players_alive", "npcs_alive")
        if tuple(first_result[key] for key in result_keys) != tuple(
            second_result[key] for key in result_keys
        ):
            return None
        for observation in (first, second):
            detail = observation.get("detail")
            if (
                _ui(observation).get("name") not in _MAP_STATES
                or observation.get("coherent") is not True
                or observation.get("settled") is not True
                or not isinstance(detail, dict)
                or detail.get("locked") is not False
            ):
                return None
        if cls._roster_fingerprint(first) != cls._roster_fingerprint(second):
            return None
        return first_result

    @staticmethod
    def _screenshot_bytes(observation: dict[str, Any]) -> bytes | None:
        value = observation.get("screenshot")
        if not isinstance(value, str) or not value.startswith("data:image/png;base64,"):
            return None
        try:
            return base64.b64decode(value.split(",", 1)[1], validate=True)
        except (ValueError, TypeError):
            return None

    def _read_official_result(self, terminal: dict[str, Any]) -> dict[str, Any] | None:
        """Advance only the recognized FE7 points prompt and read its result page.

        This runs after synchronized elimination is already confirmed. It sends
        at most one A pulse per linked client, and only while the exact 30-point
        award panel is visible on that client. Any unrecognized page is left
        untouched and the match still completes with its roster result.
        """
        deadline = time.monotonic() + 4.5
        acknowledged: set[str] = set()
        previous_signature: tuple[Any, ...] | None = None
        stable_reads = 0
        winner_label = {"A": "1P", "B": "2P"}.get(terminal.get("winner"))
        self.controller.set_decision_context(None)

        while time.monotonic() < deadline and not self.stop_event.is_set():
            try:
                observations = {
                    side: self.coordinator.observe(side)
                    for side in ("A", "B")
                }
            except Exception as exc:
                self._log({"type": "official_score_capture_failed", "error": type(exc).__name__})
                return None

            results: dict[str, dict[str, Any]] = {}
            for side, observation in observations.items():
                png = self._screenshot_bytes(observation)
                parsed = read_final_result_screen(png) if png is not None else None
                if parsed is not None:
                    results[side] = parsed

            first = results.get("A")
            second = results.get("B")
            if first is not None and second is not None:
                first_places = first["points_by_seat"]
                second_places = second["points_by_seat"]
                signature = (
                    first["first_place"]["seat"],
                    first_places.get("1P"), first_places.get("2P"),
                    second["first_place"]["seat"],
                    second_places.get("1P"), second_places.get("2P"),
                )
                agrees = (
                    first_places == second_places
                    and first["first_place"]["seat"] == second["first_place"]["seat"]
                    and first["first_place"]["seat"] == winner_label
                )
                stable_reads = stable_reads + 1 if signature == previous_signature else 1
                previous_signature = signature
                if agrees and stable_reads >= 2:
                    score = {
                        "source": "fe7_final_result_screen",
                        "points_by_seat": first_places,
                        "first_place": first["first_place"],
                        "second_place": first["second_place"],
                        "screen_sha256_by_bridge": {
                            "A": first["screen_sha256"],
                            "B": second["screen_sha256"],
                        },
                        "layout_by_bridge": {
                            "A": first["layout"],
                            "B": second["layout"],
                        },
                        "stable_paired_reads": stable_reads,
                        "winner_matches_terminal_roster": True,
                    }
                    self._log({"type": "official_score_recorded", "score": score})
                    return score
            else:
                stable_reads = 0
                previous_signature = None

            # A shared, terminal 30-point award panel was captured on both
            # cores in the verified pilot. Use only this fixed FE7 screen as
            # the acknowledgement gate; never tap through an unknown menu.
            if (
                not acknowledged
                and self._terminal_pair(observations) is not None
                and all(
                    (png := self._screenshot_bytes(observation)) is not None
                    and is_points_bonus_transition(png)
                    for observation in observations.values()
                )
            ):
                for side in ("A", "B"):
                    if side in acknowledged:
                        continue
                    observation = self.coordinator.observe(side)
                    png = self._screenshot_bytes(observation)
                    if (
                        self._terminal(observation) != terminal
                        or png is None
                        or not is_points_bonus_transition(png)
                    ):
                        continue
                    try:
                        self.coordinator.act(side, {
                            "observation_id": observation["observation_id"],
                            "buttons": ["A"],
                            "hold_frames": 3,
                        })
                    except Exception as exc:
                        self._log({"type": "official_result_ack_failed", "side": side,
                                   "error": type(exc).__name__})
                        continue
                    acknowledged.add(side)
                    self._log({"type": "official_result_prompt_acknowledged", "side": side,
                               "prompt_sha256": hashlib.sha256(png).hexdigest()})
                    time.sleep(0.15)

            time.sleep(0.2)

        self._log({"type": "official_score_unavailable",
                   "reason": "final result screen was not recognized and agreed by both clients",
                   "acknowledged_sides": sorted(acknowledged)})
        return None

    @staticmethod
    def _phase_raw(observation: dict[str, Any]) -> int | None:
        detail = observation.get("detail")
        value = detail.get("phase_raw") if isinstance(detail, dict) else None
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _roster_fingerprint(observation: dict[str, Any]) -> tuple[Any, ...]:
        """Compare linked-client roster state without local map orientation.

        FE7 can expose a settled map on one core before the other core has
        received the last casualty. Positions differ between the two local
        views, so compare team, character, HP, and inventory instead.
        """
        state = observation.get("game_state")
        state = state if isinstance(state, dict) else {}
        units = []
        for unit in observation.get("units", []):
            if not isinstance(unit, dict):
                continue
            hp = unit.get("hp")
            hp = hp if isinstance(hp, dict) else {}
            inventory = unit.get("inventory")
            items = tuple(sorted(
                (
                    str(item.get("id")),
                    str(item.get("uses")),
                    str(item.get("slot")),
                )
                for item in inventory
                if isinstance(item, dict)
            )) if isinstance(inventory, list) else ()
            units.append((
                str(unit.get("team")),
                str(unit.get("character_id")),
                str(hp.get("current")),
                str(hp.get("max")),
                items,
            ))
        return (
            str(state.get("players")),
            str(state.get("npcs")),
            tuple(sorted(units)),
        )

    @staticmethod
    def _local_roster_team(observation: dict[str, Any]) -> str:
        """Return the roster shown on this linked client's near (y=9) row."""
        bottom_counts = {"player": 0, "npc": 0}
        for unit in observation.get("units", []):
            if not isinstance(unit, dict) or unit.get("team") not in bottom_counts:
                continue
            position = unit.get("position")
            if isinstance(position, list) and len(position) == 2 and position[1] == 9:
                bottom_counts[str(unit["team"])] += 1
        teams = [team for team, count in bottom_counts.items() if count == 5]
        if len(teams) != 1:
            raise UnsafeScreen(
                f"cannot identify the local Link Arena roster from bottom-row units: {bottom_counts}"
            )
        return teams[0]

    def _assign_agent_bridges(self) -> None:
        """Identify the 1P core with a reversible and verified cursor tap.

        mGBA can start either linked Lua VM first. That means bridge labels
        cannot safely stand in for the FE7 player numbers. Probe each settled
        map with one D-pad step, identify the core that accepts the opening
        turn, and restore the cursor before either agent acts.
        """
        active_bridge: str | None = None
        for bridge_side in ("A", "B"):
            before = self.controller.observe_settled(bridge_side)
            if not ArenaSetup.is_arena_map(before):
                raise UnsafeScreen(
                    f"cannot identify player order on bridge {bridge_side}: {_ui(before)!r}"
                )
            x, y = _cursor(before)
            occupied = {
                tuple(unit["position"])
                for unit in before.get("units", [])
                if isinstance(unit, dict)
                and isinstance(unit.get("position"), list)
                and len(unit["position"]) == 2
            }
            fallback: tuple[str, tuple[int, int]] | None = None
            for button in ("RIGHT", "LEFT", "UP", "DOWN"):
                expected = _directional_cursor_target(
                    str(_ui(before).get("name")), (x, y), button,
                )
                if not (0 <= expected[0] < 15 and 0 <= expected[1] < 10):
                    continue
                if fallback is None:
                    fallback = (button, expected)
                # The Link Arena floor is not a fully walkable rectangle.
                # Prefer an adjacent unit tile (known playable floor) over
                # empty board coordinates that can make FE7 snap across the
                # map or keep the cursor stationary.
                if expected in occupied:
                    fallback = (button, expected)
                    break
            if fallback is None:
                raise UnsafeScreen(f"no legal map cursor probe from {bridge_side} at {(x, y)}")
            button, expected_cursor = fallback
            before_ui = _ui(before)
            before_roster = (
                before.get("game_state", {}).get("players"),
                before.get("game_state", {}).get("npcs"),
            )
            self.coordinator.act(bridge_side, {
                "observation_id": before["observation_id"], "buttons": [button],
            })
            after = self.controller.observe_settled(bridge_side)
            after_cursor = _cursor(after)
            after_roster = (
                after.get("game_state", {}).get("players"),
                after.get("game_state", {}).get("npcs"),
            )
            if _ui(after).get("name") != before_ui.get("name") or after_roster != before_roster:
                raise UnsafeScreen(
                    f"turn probe on {bridge_side} changed unrelated state: "
                    f"{before_ui!r} -> {_ui(after)!r}, rosters {before_roster!r} -> {after_roster!r}"
                )
            moved = after_cursor == expected_cursor
            if not moved and after_cursor != (x, y):
                raise UnsafeScreen(
                    f"turn probe on {bridge_side} expected {(x, y)} or {expected_cursor}, "
                    f"observed {after_cursor}"
                )
            self._log({"type": "turn_probe", "bridge_side": bridge_side, "button": button,
                       "before_cursor": (x, y), "after_cursor": after_cursor,
                       "accepted": moved})
            if not moved:
                continue
            opposite = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}[button]
            restored = self.controller.tap_direction(bridge_side, opposite)
            if _cursor(restored) != (x, y):
                raise UnsafeScreen(f"turn probe could not restore {bridge_side} cursor to {(x, y)}")
            active_bridge = bridge_side
            break

        if active_bridge is None:
            raise UnsafeScreen("neither linked bridge accepted a verified opening-turn cursor probe")
        other_bridge = "B" if active_bridge == "A" else "A"
        self.agent_bridge = {"A": active_bridge, "B": other_bridge}
        roster_by_agent: dict[str, str] = {}
        for agent_side, bridge_side in self.agent_bridge.items():
            observation = self.controller.observe_settled(bridge_side)
            team = self._local_roster_team(observation)
            self.agents[agent_side].set_own_team(team)
            roster_by_agent[agent_side] = team
        self._log({"type": "agent_bridge_assignment", "first_agent": "A",
                   "bridge_for_agent": dict(self.agent_bridge),
                   "own_team_by_agent": roster_by_agent,
                   "reason": "verified 1P-first cursor probe"})

    def _decision(self, agent_side: str, bridge_side: str) -> tuple[dict[str, Any], AgentDecision]:
        observation = self.controller.observe_settled(bridge_side)
        if not ArenaSetup.is_arena_map(observation):
            raise UnsafeScreen(
                f"agent {agent_side} bridge {bridge_side} is not at an actionable Link Arena map: "
                f"{_ui(observation)!r}"
            )
        agent = self.agents[agent_side]
        try:
            decision = agent.choose_matchup(observation)
        except Exception as exc:
            self._log({
                "type": "policy_call_failed",
                "side": agent_side,
                "bridge_side": bridge_side,
                "policy": agent.benchmark_metadata(),
                "inference": getattr(agent, "last_call_metadata", {}),
                "error": str(exc),
            })
            raise
        return observation, decision

    def _wait_for_turn_boundary(self, *, phase_raw_before: int | None = None) -> None:
        """Wait for a verified phase transition and actionable maps on both clients.

        Chapter-65 memory can look like an unlocked map during the combat and
        player-phase animations. Prefer the phase banner when it is visible;
        some FE7 handoffs have no banner, so accept a changed raw phase byte
        only after both linked clients have returned to settled arena maps.
        """
        deadline = time.monotonic() + self.controller.settle_timeout
        banner_seen = False
        last_matching_roster: tuple[Any, ...] | None = None
        matching_roster_reads = 0
        matching_roster_since: float | None = None
        roster_mismatch_logged = False
        terminal_signature: tuple[Any, ...] | None = None
        terminal_reads = 0
        terminal_since: float | None = None
        terminal_mismatch_logged = False
        while time.monotonic() < deadline and not self.stop_event.is_set():
            observations = {
                bridge_side: self.controller.observe_settled(bridge_side)
                for bridge_side in ("A", "B")
            }
            terminal = self._terminal_pair(observations)
            if terminal:
                signature = (
                    terminal["winner"], self._roster_fingerprint(observations["A"]),
                )
                terminal_reads = terminal_reads + 1 if signature == terminal_signature else 1
                terminal_signature = signature
                if terminal_reads == 1:
                    terminal_since = time.monotonic()
                terminal_stable_seconds = (
                    time.monotonic() - terminal_since
                    if terminal_since is not None else 0.0
                )
                if (
                    terminal_reads >= 4
                    and terminal_stable_seconds >= self.roster_stability_seconds
                ):
                    self._log({"type": "terminal_roster_confirmed", **terminal,
                               "roster_sync_reads": terminal_reads,
                               "roster_stable_seconds": round(terminal_stable_seconds, 3),
                               "observation_ids": {side: observations[side].get("observation_id")
                                                   for side in ("A", "B")}})
                    raise StopIteration(terminal)
            else:
                terminal_signature = None
                terminal_reads = 0
                terminal_since = None
                candidates = {side: self._terminal(value) for side, value in observations.items()}
                if any(candidates.values()) and not terminal_mismatch_logged:
                    rosters = {}
                    for side, value in observations.items():
                        game_state = value.get("game_state")
                        game_state = game_state if isinstance(game_state, dict) else {}
                        rosters[side] = {
                            "players": game_state.get("players"),
                            "npcs": game_state.get("npcs"),
                            "ui_state": _ui(value),
                            "settled": value.get("settled"),
                        }
                    self._log({"type": "terminal_waiting_for_peer",
                               "terminal_candidates": candidates,
                               "game_rosters": rosters})
                    terminal_mismatch_logged = True
            for bridge_side, observation in observations.items():
                if _ui(observation).get("name") == "phase_transition" and not banner_seen:
                    banner_seen = True
                    self._log({"type": "turn_boundary_banner", "bridge_side": bridge_side,
                               "observation_id": observation.get("observation_id")})
            both_maps = all(ArenaSetup.is_arena_map(value) for value in observations.values())
            phase_values = {side: self._phase_raw(value) for side, value in observations.items()}
            phase_changed = (
                phase_raw_before is not None
                and all(value is not None and value != phase_raw_before
                        for value in phase_values.values())
            )
            transition_verified = both_maps and (banner_seen or phase_changed)
            if transition_verified:
                roster_signatures = {
                    side: self._roster_fingerprint(value)
                    for side, value in observations.items()
                }
                if roster_signatures["A"] == roster_signatures["B"]:
                    matching_roster = roster_signatures["A"]
                    matching_roster_reads = (
                        matching_roster_reads + 1
                        if matching_roster == last_matching_roster else 1
                    )
                    if matching_roster_reads == 1:
                        matching_roster_since = time.monotonic()
                    last_matching_roster = matching_roster
                    stable_seconds = (
                        time.monotonic() - matching_roster_since
                        if matching_roster_since is not None else 0.0
                    )
                    if matching_roster_reads >= 4 and stable_seconds >= self.roster_stability_seconds:
                        self._log({"type": "turn_boundary_ready", "banner_seen": banner_seen,
                                   "reason": "phase_banner" if banner_seen else "phase_raw_changed",
                                   "phase_raw_before": phase_raw_before,
                                   "phase_raw_after": phase_values,
                                   "roster_sync_reads": matching_roster_reads,
                                   "roster_stable_seconds": round(stable_seconds, 3),
                                   "map_observation_ids": {side: value.get("observation_id")
                                                            for side, value in observations.items()}})
                        return
                else:
                    last_matching_roster = None
                    matching_roster_reads = 0
                    matching_roster_since = None
                    if not roster_mismatch_logged:
                        self._log({
                            "type": "turn_boundary_waiting_for_roster_sync",
                            "game_rosters": {
                                side: {
                                    "players": observations[side].get("game_state", {}).get("players"),
                                    "npcs": observations[side].get("game_state", {}).get("npcs"),
                                }
                                for side in ("A", "B")
                            },
                            "observation_ids": {side: value.get("observation_id")
                                                 for side, value in observations.items()},
                        })
                        roster_mismatch_logged = True
            else:
                last_matching_roster = None
                matching_roster_reads = 0
                matching_roster_since = None
            time.sleep(self.poll_interval)
        if self.stop_event.is_set():
            return
        raise UnsafeScreen(
            "Link Arena did not reach settled maps with a stable matching roster after "
            "the phase handoff before the next minimax decision"
        )

    def play_one_exchange(self, side: str) -> tuple[dict[str, Any], int | None]:
        agent = self.agents[side]
        bridge_side = self.agent_bridge[side]
        weapon_menu: dict[str, Any] | None = None
        decision: AgentDecision | None = None
        observation: dict[str, Any] | None = None
        phase_raw_before: int | None = None
        for attempt in range(1, 7):
            observation, decision = self._decision(side, bridge_side)
            phase_raw_before = self._phase_raw(observation)
            decision_id = uuid.uuid4().hex
            self._pending_decision_id = decision_id
            self.controller.set_decision_context(decision_id, side)
            inference_metadata = getattr(agent, "last_call_metadata", None)
            policy_input = (
                inference_metadata.get("policy_input")
                if isinstance(inference_metadata, dict)
                else None
            )
            if not isinstance(policy_input, dict):
                policy_input = {"own_team": agent.own_team, "units": observation.get("units", [])}
            policy_input_bytes = json.dumps(
                policy_input, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
            policy_metadata = agent.benchmark_metadata()
            policy_metadata["implementation_sha256"] = self._policy_sha256
            observation_record = {
                "observation_id": observation.get("observation_id"),
                "generation": observation.get("generation"),
                "ui_state": observation.get("ui_state"),
                "detail": observation.get("detail"),
                "game_state": observation.get("game_state"),
                "units": observation.get("units"),
                "coherent": observation.get("coherent"),
                "settled": observation.get("settled"),
                "screenshot_file": observation.get("screenshot_file"),
            }
            self._log({"type": "decision", "decision_id": decision_id,
                       "side": side, "bridge_side": bridge_side,
                       "attempt": attempt, "decision": decision.as_dict(),
                       "observation_id": observation.get("observation_id"),
                       "generation": observation.get("generation"),
                       "observation": observation_record,
                       "policy_input": policy_input,
                       "policy": policy_metadata,
                       "inference": inference_metadata,
                       "seat": "1P" if side == "A" else "2P",
                       "policy_input_sha256": hashlib.sha256(policy_input_bytes).hexdigest()})

            # Persist the policy choice before any execution-time validation so
            # a bad or stale selection remains visible in the audit trail.
            actor = self._unit(agent, observation, decision.attacker_id, own=True)
            target = self._unit(agent, observation, decision.defender_id, own=False)
            if not self._unit_is_live(target):
                raise UnsafeScreen(f"agent selected fallen defender {decision.defender_id}")
            actor_pos = tuple(int(part) for part in actor["position"])
            target_pos = tuple(int(part) for part in target["position"])

            self.controller.move_cursor_to(bridge_side, actor_pos)
            actor_selected = self.controller.confirm_unit_at_cursor(
                bridge_side,
                team=str(actor["team"]),
                character_id=decision.attacker_id,
                expected_after=lambda result: _ui(result).get("name") in _MAP_STATES,
            )

            try:
                target = self._unit(agent, actor_selected, decision.defender_id, own=False)
            except UnsafeScreen:
                self._log({"type": "decision_replanned", "decision_id": decision_id,
                           "side": side,
                           "attempt": attempt, "stage": "after_actor_selection",
                           "reason": "defender disappeared from live roster"})
                self.controller.set_decision_context(None)
                self._pending_decision_id = None
                continue
            if not self._unit_is_live(target):
                self._log({"type": "decision_replanned", "decision_id": decision_id,
                           "side": side,
                           "attempt": attempt, "stage": "after_actor_selection",
                           "reason": "defender has zero HP"})
                self.controller.set_decision_context(None)
                self._pending_decision_id = None
                continue
            target_pos = tuple(int(part) for part in target["position"])

            self.controller.move_cursor_to(bridge_side, target_pos)
            try:
                weapon_menu = self.controller.confirm_unit_at_cursor(
                    bridge_side,
                    team=str(target["team"]),
                    character_id=decision.defender_id,
                    expected_after=lambda result: (
                        _ui(result).get("name") == "menu"
                        and _ui(result).get("menu_type") in {"item", "arena"}
                    ),
                )
            except UnsafeScreen:
                latest = self.controller.observe_settled(bridge_side)
                target_missing = False
                target_live = False
                try:
                    latest_target = self._unit(agent, latest, decision.defender_id, own=False)
                    target_live = self._unit_is_live(latest_target)
                except UnsafeScreen:
                    target_missing = True
                if ArenaSetup.is_arena_map(latest) and (target_missing or not target_live):
                    self._log({"type": "decision_replanned", "decision_id": decision_id,
                               "side": side,
                               "attempt": attempt, "stage": "target_confirmation",
                               "reason": "defender disappeared before confirmation"})
                    self.controller.set_decision_context(None)
                    self._pending_decision_id = None
                    continue
                raise

            # FE7 removes both selected fighters from the map roster while the
            # weapon panel is open. Their absence here is normal battle setup;
            # confirm_unit_at_cursor already verified the defender on the map
            # immediately before selecting it.
            break
        else:
            raise UnsafeScreen("defender roster kept changing; stopped after six safe replans")

        assert observation is not None and decision is not None and weapon_menu is not None

        weapon_row = agent.weapon_menu_row(observation, decision)
        self.controller.move_menu_to(
            bridge_side, menu_type=str(_ui(weapon_menu)["menu_type"]), row=weapon_row,
        )
        forecast = self.controller.confirm_menu_row(
            bridge_side,
            menu_type=str(_ui(weapon_menu)["menu_type"]),
            row=weapon_row,
            expected_after=lambda result: (
                _ui(result).get("name") == "battle_forecast"
                or _ui(result).get("name") == "unit_status"
                or (_ui(result).get("name") == "menu" and _ui(result).get("menu_type") == "battle")
                or self._terminal(result) is not None
            ),
        )
        forecast_ui = _ui(forecast)
        resolved = lambda value: (
            _ui(value).get("name") in _MAP_STATES
            or self._terminal(value) is not None
            or _ui(value).get("name") in {"battle", "dialogue", "animation"}
        )
        if forecast_ui.get("name") == "battle_forecast":
            result = self.controller.confirm_screen(
                bridge_side,
                screen_name="battle_forecast",
                expected_after=resolved,
            )
        elif forecast_ui.get("name") == "menu" and forecast_ui.get("menu_type") == "battle":
            result = self.controller.confirm_menu_row(
                bridge_side,
                menu_type="battle",
                row=int(forecast_ui["selection"]),
                expected_after=resolved,
            )
        elif forecast_ui.get("name") == "unit_status":
            # FE7 returns to the map with the selected attacker's status card
            # open after the weapon is confirmed. This is a separate, visually
            # recognized confirmation gate; without it the turn never starts
            # and the linked opponent correctly ignores its controls.
            result = self.controller.confirm_screen(
                bridge_side,
                screen_name="unit_status",
                expected_after=resolved,
            )
        else:
            raise UnsafeScreen(
                "weapon selection did not lead to a recognized battle gate: "
                f"{forecast_ui!r}"
            )
        self._log({"type": "exchange_submitted", "decision_id": decision_id,
                   "side": side, "bridge_side": bridge_side,
                   "decision": decision.as_dict(), "after_ui_state": _ui(result),
                   "generation": result.get("generation")})
        self.controller.set_decision_context(None)
        self._pending_decision_id = None
        return result, phase_raw_before

    def run(self) -> None:
        self._log({"type": "runner_started", "play_minimax": self.play_minimax,
                   "stream_mode": self.stream_mode,
                   "policies": {side: agent.benchmark_metadata()
                                for side, agent in self.agents.items()}})
        setup = ArenaSetup(
            self.coordinator,
            self.controller,
            log=self._log,
            status=lambda value: setattr(self, "status", value),
            # The linked lobby can take longer than an ordinary menu to
            # propagate team confirmation between cores. Give that handshake
            # room to settle while keeping every input gated by signatures.
            transition_timeout=max(30.0, self.controller.settle_timeout * 2),
            poll_interval=self.poll_interval,
        )
        setup_complete = False
        while not self.stop_event.is_set():
            try:
                if not setup_complete:
                    self.status = {"state": "setting_up", "stage": "booting_both_sides"}
                    setup.prepare_pair()
                    setup_complete = True
                    if not self.play_minimax:
                        self.status = {"state": "ready", "stage": "opening_map"}
                        self._log({"type": "setup_ready", "opening_map": "FE7 chapter 65",
                                   "teams": {"A": "RAGNAROK", "B": "RAGNAROK"},
                                   "controls": "external_agents_or_supervisor"})
                        return
                    self._assign_agent_bridges()
                # Status reads do not claim observation IDs or capture PNGs,
                # so an operator can still inspect the pair without consuming
                # an agent's one-use action observation.
                snapshot = self.coordinator.status()
                first = snapshot["sides"]["A"]
                second = snapshot["sides"]["B"]
                if any(value.get("coherent") is not True or value.get("settled") is not True
                       or not ArenaSetup.is_arena_map(value) for value in (first, second)):
                    self.status = {"state": "waiting_for_link_arena_map",
                                   "sides": {"A": _ui(first), "B": _ui(second)},
                                   "settled": {"A": first.get("settled"), "B": second.get("settled")}}
                    time.sleep(self.poll_interval)
                    continue
                self.status = {"state": "playing", "generation": first.get("generation")}
                _result, phase_raw_before = self.play_one_exchange("A")
                if self.stop_event.is_set():
                    break
                self.status = {"state": "waiting_for_turn_boundary", "after": "A"}
                self._wait_for_turn_boundary(phase_raw_before=phase_raw_before)
                if self.stop_event.is_set():
                    break
                _result, phase_raw_before = self.play_one_exchange("B")
                self.status = {"state": "waiting_for_turn_boundary", "after": "B"}
                self._wait_for_turn_boundary(phase_raw_before=phase_raw_before)
            except StopIteration as exc:
                terminal = exc.value or {"terminal": True}
                if terminal.get("terminal"):
                    terminal["official_score"] = self._read_official_result(terminal)
                self.status = {"state": "complete", **terminal}
                self._log({"type": "match_complete", **terminal})
                return
            except Exception as exc:
                self.status = {"state": "stopped_for_supervision", "error": str(exc)}
                try:
                    if self._pending_decision_id is not None:
                        self._log({"type": "decision_interrupted",
                                   "decision_id": self._pending_decision_id,
                                   "reason": str(exc)})
                    self.controller.set_decision_context(None)
                    self._pending_decision_id = None
                    self._log({"type": "autoplay_stopped", "error": str(exc)})
                except OSError:
                    # A storage failure is still fail-closed: no further input
                    # is sent after this supervision stop.
                    pass
                return
        self.status = {"state": "stopped"}
        self._log({"type": "autoplay_stopped_by_request"})
