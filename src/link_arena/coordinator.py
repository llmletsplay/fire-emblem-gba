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

from .bridge import SideBridge, argb_to_png, parse_game_state, parse_units


SIDES = ("A", "B")
ALLOWED_BUTTONS = {"A", "B", "UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT", "LT", "RT"}
MAX_BUTTONS_PER_ACTION = 8


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
        self.latest_state: dict[str, str] = {}
        self.lock = threading.RLock()
        self.log_path = match_dir / "events.jsonl"

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
            state_raw = bridge.line("GAMESTATE")
            units_raw = bridge.line("UNITS")
            image_bytes = argb_to_png(bridge.capture())
            state_after_capture = bridge.line("GAMESTATE")
            self.observation_sequence[side] += 1
            observation_id = f"{self.generation}-{side}-{self.observation_sequence[side]}"
            self.latest_observation[side] = observation_id
            self.latest_state[side] = state_after_capture
            screenshot_path = Path(f"side-{side.lower()}") / "observations" / f"{observation_id}.png"
            screenshot_file = self.match_dir / screenshot_path
            screenshot_file.parent.mkdir(parents=True, exist_ok=True)
            screenshot_file.write_bytes(image_bytes)
            observation = {
                "observation_id": observation_id,
                "side": side,
                "generation": self.generation,
                "game_state": parse_game_state(state_raw),
                "units": parse_units(units_raw),
                "raw": {"game_state": state_raw,
                        "game_state_after_capture": state_after_capture,
                        "units": units_raw},
                "screenshot": "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"),
                "screenshot_file": str(screenshot_path),
                "coherent": state_raw == state_after_capture,
                "settled": None,
            }
            self._log({"type": "observation", "side": side, "observation_id": observation_id,
                       "generation": self.generation, "game_state": observation["game_state"],
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
            if self.bridges[side].line("GAMESTATE") != self.latest_state.get(side):
                self.latest_observation.pop(side, None)
                raise StaleObservation("the game state changed; observe again before acting")

            buttons = payload.get("buttons")
            if not isinstance(buttons, list) or not 1 <= len(buttons) <= MAX_BUTTONS_PER_ACTION:
                raise InvalidAction(f"buttons must contain 1 to {MAX_BUTTONS_PER_ACTION} presses")
            normalized = [button.upper() if isinstance(button, str) else "" for button in buttons]
            invalid = [button for button in normalized if button not in ALLOWED_BUTTONS]
            if invalid:
                raise InvalidAction(f"unsupported button(s): {invalid}")

            self.bridges[side].act(normalized)
            self.generation += 1
            self.latest_observation.clear()
            self.latest_state.clear()
            result = {"ok": True, "side": side, "generation": self.generation,
                      "completed_buttons": normalized}
            self._log({"type": "action", **result, "observation_id": observation_id,
                       "timestamp": time.time()})
            return result

    def status(self) -> dict[str, Any]:
        with self.lock:
            state_by_side = {}
            for side, bridge in self.bridges.items():
                raw = bridge.line("GAMESTATE")
                state_by_side[side] = parse_game_state(raw)
            return {"generation": self.generation, "sides": state_by_side}

    def _log(self, event: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp": time.time(), **event}, sort_keys=True) + "\n")
