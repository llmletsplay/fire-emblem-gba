"""Side-scoped observations and bounded actions for a local Link Arena match."""

from __future__ import annotations

import base64
import hmac
import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .bridge import (
    SideBridge,
    argb_to_png,
    parse_detail,
    parse_game_state,
    parse_ui_state,
    parse_units,
)


SIDES = ("A", "B")
ALLOWED_BUTTONS = {"A", "B", "UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT", "LT", "RT"}
MAX_BUTTONS_PER_ACTION = 8
DETAIL_CONTROL_FIELDS = (
    "phase_raw", "phase_name", "chapter", "turn", "cursor", "bm_cursor",
    "bm_camera", "taken_action", "locked", "players_alive", "enemies_alive",
)


def _control_fingerprint(ui_state: str, game_state: str, detail: str, units: str) -> tuple[str, str, str, str]:
    parsed_detail = parse_detail(detail)
    stable_detail = json.dumps(
        {key: parsed_detail.get(key) for key in DETAIL_CONTROL_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )
    # bm_state contains engine bits that can change during a rendered frame
    # without changing the screen/control affordance. Keep it in the raw event
    # log, but do not use it to invalidate otherwise current cursor/menu input.
    return ui_state, game_state, stable_detail, units


class StaleObservation(ValueError):
    pass


class InvalidAction(ValueError):
    pass


class LinkArenaCoordinator:
    def __init__(
        self,
        ports: dict[str, int],
        tokens: dict[str, str],
        match_dir: Path,
        bridges: dict[str, SideBridge] | None = None,
    ):
        self.bridges = bridges or {side: SideBridge(ports[side]) for side in SIDES}
        self.tokens = tokens
        self.match_dir = match_dir
        self.generation = 0
        self.observation_sequence: dict[str, int] = defaultdict(int)
        self.latest_observation: dict[str, str] = {}
        self.latest_fingerprint: dict[str, tuple[str, str, str, str]] = {}
        self.last_fingerprint: dict[str, tuple[str, str, str, str]] = {}
        self.fingerprint_count: dict[str, int] = defaultdict(int)
        self.last_status_fingerprint: dict[str, tuple[str, str, str, str]] = {}
        self.status_fingerprint_count: dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()
        self.log_path = match_dir / "events.jsonl"
        self.decision_ledger: Any | None = None
        self.match_id: str | None = None

    def close(self) -> None:
        with self.lock:
            for bridge in self.bridges.values():
                bridge.close()

    def side_for_token(self, token: str) -> str | None:
        for side in SIDES:
            if hmac.compare_digest(token, self.tokens[side]):
                return side
        return None

    def observe(self, side: str) -> dict[str, Any]:
        with self.lock:
            bridge = self.bridges[side]
            ui_state_raw = bridge.line("STATE")
            state_raw = bridge.line("GAMESTATE")
            detail_raw = bridge.line("DETAIL")
            units_raw = bridge.line("UNITS")
            image_bytes = argb_to_png(bridge.capture())
            ui_state_after_capture = bridge.line("STATE")
            state_after_capture = bridge.line("GAMESTATE")
            detail_after_capture = bridge.line("DETAIL")
            units_after_capture = bridge.line("UNITS")
            fingerprint = _control_fingerprint(
                ui_state_after_capture, state_after_capture,
                detail_after_capture, units_after_capture,
            )
            self.observation_sequence[side] += 1
            observation_id = f"{self.generation}-{side}-{self.observation_sequence[side]}"
            self.latest_observation[side] = observation_id
            self.latest_fingerprint[side] = fingerprint
            screenshot_path = Path(f"side-{side.lower()}") / "observations" / f"{observation_id}.png"
            screenshot_file = self.match_dir / screenshot_path
            screenshot_file.parent.mkdir(parents=True, exist_ok=True)
            screenshot_file.write_bytes(image_bytes)
            coherent = _control_fingerprint(ui_state_raw, state_raw, detail_raw, units_raw) == fingerprint
            detail = parse_detail(detail_after_capture)
            if coherent and not detail.get("locked", False):
                if self.last_fingerprint.get(side) == fingerprint:
                    self.fingerprint_count[side] += 1
                else:
                    self.last_fingerprint[side] = fingerprint
                    self.fingerprint_count[side] = 1
            else:
                self.last_fingerprint.pop(side, None)
                self.fingerprint_count[side] = 0
            settled = coherent and not detail.get("locked", False) and self.fingerprint_count[side] >= 2
            observation = {
                "observation_id": observation_id,
                "side": side,
                "generation": self.generation,
                "ui_state": parse_ui_state(
                    ui_state_after_capture,
                    game_state=parse_game_state(state_after_capture),
                    detail=detail,
                    screenshot_png=image_bytes,
                ),
                "detail": detail,
                "game_state": parse_game_state(state_raw),
                "units": parse_units(units_raw),
                "raw": {"ui_state": ui_state_raw,
                        "ui_state_after_capture": ui_state_after_capture,
                        "game_state": state_raw,
                        "game_state_after_capture": state_after_capture,
                        "detail": detail_raw,
                        "detail_after_capture": detail_after_capture,
                        "units": units_raw,
                        "units_after_capture": units_after_capture},
                "screenshot": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
                "screenshot_file": str(screenshot_path),
                "coherent": coherent,
                "settled": settled,
            }
            self._log({"type": "observation", "side": side, "observation_id": observation_id,
                       "generation": self.generation, "ui_state": observation["ui_state"],
                       "detail": observation["detail"], "game_state": observation["game_state"],
                       "units": observation["units"], "raw": observation["raw"],
                       "screenshot_file": str(screenshot_path), "coherent": observation["coherent"],
                       "settled": observation["settled"]})
            return observation

    def act(self, side: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            observation_id = payload.get("observation_id")
            if not isinstance(observation_id, str) or observation_id != self.latest_observation.get(side):
                raise StaleObservation("observe again before acting; this observation is stale")
            if observation_id.split("-", 1)[0] != str(self.generation):
                raise StaleObservation("the other side acted after this observation; observe again")
            current_fingerprint = _control_fingerprint(
                self.bridges[side].line("STATE"),
                self.bridges[side].line("GAMESTATE"),
                self.bridges[side].line("DETAIL"),
                self.bridges[side].line("UNITS"),
            )
            if current_fingerprint != self.latest_fingerprint.get(side):
                self.latest_observation.pop(side, None)
                self.latest_fingerprint.pop(side, None)
                raise StaleObservation("the game state changed; observe again before acting")

            buttons = payload.get("buttons")
            if not isinstance(buttons, list) or not 1 <= len(buttons) <= MAX_BUTTONS_PER_ACTION:
                raise InvalidAction(f"buttons must contain 1 to {MAX_BUTTONS_PER_ACTION} presses")
            normalized = [button.upper() if isinstance(button, str) else "" for button in buttons]
            invalid = [button for button in normalized if button not in ALLOWED_BUTTONS]
            if invalid:
                raise InvalidAction(f"unsupported button(s): {invalid}")

            hold_frames = payload.get("hold_frames")
            if hold_frames is not None and (
                isinstance(hold_frames, bool)
                or not isinstance(hold_frames, int)
                or not 1 <= hold_frames <= 12
            ):
                raise InvalidAction("hold_frames must be an integer between 1 and 12")
            if hold_frames is None:
                self.bridges[side].act(normalized)
            else:
                self.bridges[side].act(normalized, hold_frames=hold_frames)
            self.generation += 1
            self.latest_observation.clear()
            self.latest_fingerprint.clear()
            self.last_fingerprint.clear()
            self.fingerprint_count.clear()
            self.last_status_fingerprint.clear()
            self.status_fingerprint_count.clear()
            result = {"ok": True, "side": side, "generation": self.generation,
                      "completed_buttons": normalized}
            if hold_frames is not None:
                result["hold_frames"] = hold_frames
            event = {"type": "action", **result, "observation_id": observation_id,
                     "timestamp": time.time()}
            decision_id = payload.get("decision_id")
            agent_side = payload.get("agent_side")
            if isinstance(decision_id, str):
                event["decision_id"] = decision_id
            if agent_side in {"A", "B"}:
                event["agent_side"] = agent_side
                event["seat"] = "1P" if agent_side == "A" else "2P"
            self._log(event)
            if isinstance(decision_id, str) and self.decision_ledger is not None and self.match_id:
                self.decision_ledger.record(self.match_id, event)
            return result

    def status(self) -> dict[str, Any]:
        with self.lock:
            state_by_side = {}
            for side, bridge in self.bridges.items():
                ui_state_raw = bridge.line("STATE")
                game_state_raw = bridge.line("GAMESTATE")
                detail_raw = bridge.line("DETAIL")
                units_raw = bridge.line("UNITS")
                ui_state_after = bridge.line("STATE")
                game_state_after = bridge.line("GAMESTATE")
                detail_after = bridge.line("DETAIL")
                units_after = bridge.line("UNITS")
                before = _control_fingerprint(ui_state_raw, game_state_raw, detail_raw, units_raw)
                fingerprint = _control_fingerprint(
                    ui_state_after, game_state_after, detail_after, units_after,
                )
                coherent = before == fingerprint
                parsed_detail = parse_detail(detail_after)
                if coherent and not parsed_detail.get("locked", False):
                    if self.last_status_fingerprint.get(side) == fingerprint:
                        self.status_fingerprint_count[side] += 1
                    else:
                        self.last_status_fingerprint[side] = fingerprint
                        self.status_fingerprint_count[side] = 1
                else:
                    self.last_status_fingerprint.pop(side, None)
                    self.status_fingerprint_count[side] = 0
                state_by_side[side] = {
                    "ui_state": parse_ui_state(
                        ui_state_after,
                        game_state=parse_game_state(game_state_after),
                        detail=parsed_detail,
                    ),
                    "game_state": parse_game_state(game_state_after),
                    "detail": parsed_detail,
                    "units": parse_units(units_after),
                    "coherent": coherent,
                    "settled": coherent and not parsed_detail.get("locked", False)
                    and self.status_fingerprint_count[side] >= 2,
                }
            return {"generation": self.generation, "sides": state_by_side}

    def _log(self, event: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp": time.time(), **event}, sort_keys=True) + "\n")
