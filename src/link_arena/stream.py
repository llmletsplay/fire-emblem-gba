"""Read-only stream telemetry assembled from a live Link Arena session."""

from __future__ import annotations

import base64
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .bridge import argb_to_png


def _roster_count(value: object) -> tuple[int | None, int | None]:
    if not isinstance(value, str) or "/" not in value:
        return None, None
    try:
        alive, total = (int(part) for part in value.split("/", 1))
    except ValueError:
        return None, None
    if alive < 0 or total < 0 or alive > total:
        return None, None
    return alive, total


class LinkArenaStreamState:
    """Build a token-free, read-only snapshot for the OBS browser overlay.

    The stream endpoint is safe to expose to a local browser source: it does
    not return agent credentials, raw bridge commands, or bearer tokens. The
    HTTP server remains bound to loopback.
    """

    def __init__(
        self,
        coordinator: Any,
        *,
        match_id: str,
        started_at: str,
        autoplay: Any | None,
    ):
        self.coordinator = coordinator
        self.match_id = match_id
        self.started_at = started_at
        self.autoplay = autoplay
        self._lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._offsets: dict[str, int] = {}
        self._input_counts = {"A": 0, "B": 0}
        self._exchange_counts = {"A": 0, "B": 0}
        self._score_totals = {"A": 0.0, "B": 0.0}
        self._recent: list[dict[str, Any]] = []
        self._agent_labels = self._labels_from_autoplay(autoplay)

    @staticmethod
    def _labels_from_autoplay(autoplay: Any | None) -> dict[str, str]:
        labels: dict[str, str] = {}
        if autoplay is not None and not getattr(autoplay, "play_minimax", False):
            return {"A": "External agent", "B": "External agent"}
        agents = getattr(autoplay, "agents", {})
        if not isinstance(agents, dict):
            return labels
        for side, agent in agents.items():
            metadata = agent.benchmark_metadata() if hasattr(agent, "benchmark_metadata") else {}
            if metadata.get("kind") == "hosted_language_model":
                label = f"{metadata.get('provider', 'model')} · {metadata.get('model_requested', 'unknown')}"
            else:
                label = "Depth-two minimax"
            labels[side] = label
        return labels

    def _consume_events(self, key: str, path: Path, *, kind: str) -> None:
        try:
            size = path.stat().st_size
            offset = self._offsets.get(key, 0)
            if size < offset:
                offset = 0
            with path.open("rb") as stream:
                stream.seek(offset)
                chunk = stream.read()
                last_newline = chunk.rfind(b"\n")
                if last_newline < 0:
                    return
                chunk = chunk[:last_newline + 1]
                self._offsets[key] = offset + last_newline + 1
        except OSError:
            return

        for line in chunk.splitlines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if not isinstance(event, dict):
                continue
            side = event.get("side")
            if side not in {"A", "B"}:
                continue
            if kind == "input" and event.get("type") == "action":
                buttons = event.get("completed_buttons")
                if isinstance(buttons, list):
                    self._input_counts[side] += len(buttons)
            elif kind == "autoplay" and event.get("type") == "exchange_submitted":
                decision = event.get("decision")
                decision = decision if isinstance(decision, dict) else {}
                self._exchange_counts[side] += 1
                value = decision.get("score")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self._score_totals[side] += float(value)
                self._recent.append({
                    "side": side,
                    "attacker_id": decision.get("attacker_id"),
                    "defender_id": decision.get("defender_id"),
                    "weapon": decision.get("weapon_name", "Unknown weapon"),
                    "evaluation": value,
                    "rationale": decision.get("rationale"),
                    "agent": self._agent_labels.get(side, "Agent"),
                    "timestamp": event.get("timestamp"),
                })
                self._recent = self._recent[-8:]

    def _read_metrics(self) -> None:
        self._consume_events("inputs", self.coordinator.log_path, kind="input")
        autoplay_log = getattr(self.autoplay, "log_path", None)
        if isinstance(autoplay_log, Path):
            self._consume_events("autoplay", autoplay_log, kind="autoplay")

    def frames(self) -> dict[str, Any]:
        """Capture both linked screens without re-reading metrics or mutating the game."""
        frames: dict[str, str | None] = {"1P": None, "2P": None}
        with self._frame_lock:
            for bridge_side, player_side in (("A", "1P"), ("B", "2P")):
                try:
                    png = argb_to_png(self.coordinator.bridges[bridge_side].capture())
                    frames[player_side] = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
                except Exception:
                    frames[player_side] = None
        return {"updated_at": time.time(), "frames": frames}

    @staticmethod
    def _team(game_state: dict[str, Any], units: list[dict[str, Any]], *, one_player: bool) -> dict[str, Any]:
        key = "players" if one_player else "npcs"
        alive, total = _roster_count(game_state.get(key))
        team_name = "player" if one_player else "npc"
        members = [unit for unit in units if unit.get("team") == team_name]
        hp_now = hp_max = 0
        for unit in members:
            hp = unit.get("hp")
            if not isinstance(hp, dict):
                continue
            current, maximum = hp.get("current"), hp.get("max")
            if isinstance(current, int) and isinstance(maximum, int):
                hp_now += max(0, current)
                hp_max += max(0, maximum)
        if alive is None:
            alive = len(members)
        if total is None:
            total = max(alive, 5)
        return {
            "alive": alive,
            "total": total,
            "kos": max(0, total - alive),
            "hp_current": hp_now,
            "hp_max": hp_max,
            "members_observed": len(members),
        }

    def snapshot(self, *, include_frame: bool = True) -> dict[str, Any]:
        with self._lock:
            self._read_metrics()
            status = self.coordinator.status()
            sides = status.get("sides", {})
            side_a = sides.get("A", {}) if isinstance(sides, dict) else {}
            side_b = sides.get("B", {}) if isinstance(sides, dict) else {}
            game_state = side_a.get("game_state", {}) if isinstance(side_a, dict) else {}
            detail = side_a.get("detail", {}) if isinstance(side_a, dict) else {}
            game_state = game_state if isinstance(game_state, dict) else {}
            detail = detail if isinstance(detail, dict) else {}

            units_a = side_a.get("units", []) if isinstance(side_a, dict) else []
            units_b = side_b.get("units", []) if isinstance(side_b, dict) else []
            units = units_a if isinstance(units_a, list) and units_a else units_b
            units = [unit for unit in units if isinstance(unit, dict)]

            phase_name = str(detail.get("phase_name") or game_state.get("phase") or "unknown")
            normalized_phase = phase_name.lower().replace("_phase", "").replace("_animation", "")
            active_side = "1P" if normalized_phase == "player" else (
                "2P" if normalized_phase in {"npc", "enemy"} else None
            )
            turn = detail.get("turn", game_state.get("turn"))
            chapter = detail.get("chapter", game_state.get("chapter"))
            autoplay_status = getattr(self.autoplay, "status", {})
            if not isinstance(autoplay_status, dict):
                autoplay_status = {}

            winner_side = autoplay_status.get("winner")
            winner = {"A": "1P", "B": "2P", "draw": "DRAW"}.get(winner_side)
            try:
                elapsed = max(0, int(time.time() - datetime.fromisoformat(
                    self.started_at.replace("Z", "+00:00")
                ).timestamp()))
            except (ValueError, TypeError, OverflowError):
                elapsed = None

            frames: dict[str, str | None] = {"1P": None, "2P": None}
            if include_frame:
                frames = self.frames()["frames"]

            averages = {}
            for side in ("A", "B"):
                count = self._exchange_counts[side]
                averages[side] = (
                    round(self._score_totals[side] / count, 2) if count else None
                )
            return {
                "schema_version": 1,
                "updated_at": time.time(),
                "match": {
                    "id": self.match_id,
                    "elapsed_seconds": elapsed,
                    "mode": getattr(self.autoplay, "stream_mode", None) or (
                        "minimax" if getattr(self.autoplay, "play_minimax", False) else "supervised"
                    ),
                    "agents": {
                        "1P": self._agent_labels.get("A", "External agent"),
                        "2P": self._agent_labels.get("B", "External agent"),
                    },
                    "runner_state": autoplay_status.get("state", "ready"),
                    "runner_stage": autoplay_status.get("stage"),
                    "runner_error": autoplay_status.get("error"),
                    "winner": winner,
                },
                "game": {
                    "chapter": chapter,
                    "turn": turn,
                    "phase": phase_name,
                    "phase_label": f"{active_side} PHASE" if active_side else "LINK ARENA",
                    "active_side": active_side,
                    "coherent": bool(side_a.get("coherent") and side_b.get("coherent")),
                },
                "teams": {
                    "1P": self._team(game_state, units, one_player=True),
                    "2P": self._team(game_state, units, one_player=False),
                },
                "metrics": {
                    "inputs": {"1P": self._input_counts["A"], "2P": self._input_counts["B"]},
                    "exchanges": {"1P": self._exchange_counts["A"], "2P": self._exchange_counts["B"]},
                    "average_minimax_evaluation": {"1P": averages["A"], "2P": averages["B"]},
                    "recent_exchanges": list(reversed(self._recent)),
                },
                "frames": frames,
            }
