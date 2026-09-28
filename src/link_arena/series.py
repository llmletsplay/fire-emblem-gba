"""Persistent results for a sequence of FE7 Link Arena matches."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


_WINNER_LABEL = {"A": "1P", "B": "2P", "draw": "DRAW"}


def _validated_official_score(value: Any, *, winner: str) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("source") != "fe7_final_result_screen":
        return None
    points = value.get("points_by_seat")
    first = value.get("first_place")
    second = value.get("second_place")
    hashes = value.get("screen_sha256_by_bridge")
    if (
        not isinstance(points, dict)
        or set(points) != {"1P", "2P"}
        or any(isinstance(points.get(seat), bool) or not isinstance(points.get(seat), int)
               or not 0 <= points[seat] <= 9999 for seat in ("1P", "2P"))
        or not isinstance(first, dict)
        or not isinstance(second, dict)
        or first.get("seat") != _WINNER_LABEL.get(winner)
        or second.get("seat") not in {"1P", "2P"}
        or second.get("seat") == first.get("seat")
        or first.get("points") != points.get(first.get("seat"))
        or second.get("points") != points.get(second.get("seat"))
        or isinstance(first.get("points"), bool)
        or not isinstance(first.get("points"), int)
        or isinstance(second.get("points"), bool)
        or not isinstance(second.get("points"), int)
        or first["points"] <= second["points"]
        or value.get("winner_matches_terminal_roster") is not True
        or not isinstance(value.get("stable_paired_reads"), int)
        or value["stable_paired_reads"] < 2
        or not isinstance(hashes, dict)
        or set(hashes) != {"A", "B"}
        or any(not isinstance(digest, str) or len(digest) != 64
               or any(char not in "0123456789abcdef" for char in digest)
               for digest in hashes.values())
    ):
        return None
    return {
        "source": value["source"],
        "points_by_seat": {seat: points[seat] for seat in ("1P", "2P")},
        "first_place": dict(first),
        "second_place": dict(second),
        "screen_sha256_by_bridge": dict(hashes),
        "stable_paired_reads": value["stable_paired_reads"],
        "winner_matches_terminal_roster": True,
    }


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    """Serialize ledger appends across runner and migration processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            locked = True
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class MatchSeries:
    """Append-only, restart-safe scoreboard for completed arena games.

    The ledger records only verified terminal results from autoplay. Policy
    evaluations and knockout counts are deliberately not treated as FE7
    points or match wins.
    """

    def __init__(self, data_dir: Path):
        self.path = data_dir / "series" / "results.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._results = self._load()

    def _load(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(value, dict):
                        continue
                    match_id = value.get("match_id")
                    winner = value.get("winner")
                    if (
                        not isinstance(match_id, str)
                        or winner not in _WINNER_LABEL
                        or match_id in seen
                    ):
                        continue
                    official_score = _validated_official_score(
                        value.get("official_score"), winner=winner,
                    )
                    value = dict(value)
                    value["official_score_status"] = "verified" if official_score else "unavailable"
                    if official_score is None:
                        value.pop("official_score", None)
                    else:
                        value["official_score"] = official_score
                    seen.add(match_id)
                    results.append(value)
        except OSError:
            pass
        return results

    def record(self, match_id: str, result: dict[str, Any]) -> bool:
        """Persist one confirmed terminal result; duplicate match IDs are ignored."""
        winner = result.get("winner")
        if winner not in _WINNER_LABEL:
            raise ValueError(f"unknown Link Arena winner: {winner!r}")
        if not match_id:
            raise ValueError("match ID is required to record a Link Arena result")

        with self._lock:
            if any(item.get("match_id") == match_id for item in self._results):
                return False
            entry = {
                "schema_version": 1,
                "game_number": len(self._results) + 1,
                "match_id": match_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "winner": winner,
                "players_alive": result.get("players_alive"),
                "npcs_alive": result.get("npcs_alive"),
            }
            official_score = _validated_official_score(
                result.get("official_score"), winner=winner,
            )
            entry["official_score_status"] = "verified" if official_score else "unavailable"
            if official_score is not None:
                entry["official_score"] = official_score
            line = (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8")
            with self.path.open("a+b") as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell() > 0:
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) != b"\n":
                        stream.seek(0, os.SEEK_END)
                        stream.write(b"\n")
                stream.seek(0, os.SEEK_END)
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            self._results.append(entry)
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            wins = {"1P": 0, "2P": 0}
            draws = 0
            point_totals = {"1P": 0, "2P": 0}
            scored_games = 0
            for result in self._results:
                label = _WINNER_LABEL.get(result.get("winner"))
                if label == "DRAW":
                    draws += 1
                elif label in wins:
                    wins[label] += 1
                official_score = result.get("official_score")
                points = official_score.get("points_by_seat") if isinstance(official_score, dict) else None
                if isinstance(points, dict) and all(
                    isinstance(points.get(seat), int) and not isinstance(points.get(seat), bool)
                    for seat in ("1P", "2P")
                ):
                    point_totals["1P"] += points["1P"]
                    point_totals["2P"] += points["2P"]
                    scored_games += 1
            recent = [
                {
                    "game_number": result.get("game_number"),
                    "match_id": result.get("match_id"),
                    "winner": _WINNER_LABEL[result["winner"]],
                    "official_score": result.get("official_score"),
                }
                for result in reversed(self._results[-5:])
            ]
            return {
                "games_played": len(self._results),
                "wins": wins,
                "draws": draws,
                "recent_games": recent,
                "official_points": {
                    "games_scored": scored_games,
                    "totals": point_totals,
                    "most_recent": next((
                        result.get("official_score") for result in reversed(self._results)
                        if isinstance(result.get("official_score"), dict)
                    ), None),
                },
            }


class DecisionLedger:
    """Durable, series-wide JSONL trace of policy choices and executed inputs."""

    _EVENT_FIELDS = {
        "decision": (
            "decision_id", "side", "seat", "bridge_side", "attempt", "decision",
            "observation_id", "generation", "observation", "policy_input", "policy",
            "inference", "policy_input_sha256", "actor_position", "target_position",
        ),
        "decision_replanned": (
            "decision_id", "side", "attempt", "stage", "reason",
        ),
        "decision_interrupted": (
            "decision_id", "side", "reason",
        ),
        "exchange_submitted": (
            "decision_id", "side", "bridge_side", "decision",
            "after_ui_state", "generation",
        ),
        "action": (
            "decision_id", "agent_side", "seat", "side", "completed_buttons",
            "observation_id", "generation", "hold_frames",
        ),
        "policy_call_failed": (
            "side", "bridge_side", "policy", "inference", "error",
        ),
    }

    def __init__(self, data_dir: Path, *, backfill: bool = True):
        self.data_dir = data_dir
        self.path = data_dir / "series" / "decisions.jsonl"
        self.lock_path = data_dir / "series" / ".decisions.lock"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with _exclusive_file_lock(self.lock_path):
            self._event_ids, self._event_indexed_size = self._load_event_ids()
        if backfill:
            self.backfill_legacy_matches()

    def _load_event_ids(self, offset: int = 0) -> tuple[set[str], int]:
        event_ids: set[str] = set()
        try:
            with self.path.open("rb") as stream:
                size = os.fstat(stream.fileno()).st_size
                if offset > size:
                    offset = 0
                stream.seek(offset)
                for line in stream:
                    try:
                        value = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if isinstance(value, dict) and isinstance(value.get("event_id"), str):
                        event_ids.add(value["event_id"])
        except OSError:
            return event_ids, 0
        return event_ids, size

    def record(
        self,
        match_id: str,
        event: dict[str, Any],
        *,
        source_event_id: str | None = None,
        trace_origin: str = "live",
    ) -> bool:
        """Append one allow-listed event; returns false for unrelated events."""
        event_type = event.get("type")
        fields = self._EVENT_FIELDS.get(event_type)
        if fields is None:
            return False
        entry = {
            "schema_version": 1,
            "event_type": event_type,
            "match_id": match_id,
            "timestamp": event.get("timestamp", time.time()),
        }
        entry.update({field: event[field] for field in fields if field in event})
        if source_event_id is not None:
            entry["source_event_id"] = source_event_id
        entry["trace_origin"] = trace_origin
        canonical = json.dumps(
            entry, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        event_id = hashlib.sha256(canonical).hexdigest()
        with self._lock, _exclusive_file_lock(self.lock_path):
            # Another runner or a one-off migration can append while this
            # instance is alive, so refresh the dedupe index under the shared
            # process lock before deciding whether this event is new.
            new_ids, indexed_size = self._load_event_ids(self._event_indexed_size)
            if indexed_size < self._event_indexed_size:
                new_ids, indexed_size = self._load_event_ids()
            self._event_ids.update(new_ids)
            self._event_indexed_size = indexed_size
            if event_id in self._event_ids:
                return False
            entry["event_id"] = event_id
            line = (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            with self.path.open("a+b") as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell() > 0:
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) != b"\n":
                        stream.seek(0, os.SEEK_END)
                        stream.write(b"\n")
                stream.seek(0, os.SEEK_END)
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
                self._event_indexed_size = stream.tell()
            self._event_ids.add(event_id)
        return True

    @staticmethod
    def _read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
        rows: list[tuple[int, dict[str, Any]]] = []
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict):
                        rows.append((line_number, value))
        except OSError:
            pass
        return rows

    def backfill_legacy_matches(self, *, exclude_match_ids: set[str] | None = None) -> int:
        """Import pre-ledger per-match decision/input traces idempotently.

        Earlier runner versions logged choices and accepted button presses in
        separate per-match JSONL files. Their timestamps and bridge assignment
        are used to join those events; original files remain untouched.
        """
        added = 0
        try:
            match_dirs = sorted(
                path for path in self.data_dir.iterdir()
                if path.is_dir() and (path / "session.json").is_file()
            )
        except OSError:
            return 0

        for match_dir in match_dirs:
            try:
                session = json.loads((match_dir / "session.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            match_id = session.get("match_id") if isinstance(session, dict) else None
            if not isinstance(match_id, str):
                continue
            if exclude_match_ids and match_id in exclude_match_ids:
                continue
            auto_rows = self._read_jsonl(match_dir / "minimax-autoplay.jsonl")
            input_rows = self._read_jsonl(match_dir / "events.jsonl")
            timeline = []
            for source_order, source_name, rows in (
                (0, "autoplay", auto_rows), (1, "input", input_rows),
            ):
                for line_number, row in rows:
                    try:
                        timestamp = float(row.get("timestamp", 0))
                    except (TypeError, ValueError):
                        timestamp = 0.0
                    timeline.append((timestamp, source_order, line_number, source_name, row))
            timeline.sort(key=lambda value: (value[0], value[1], value[2]))
            bridge_for_agent = {"A": "A", "B": "B"}
            team_for_agent: dict[str, str] = {}
            latest_observation: dict[str, dict[str, Any]] = {}
            active: dict[str, tuple[str, str]] = {}
            for timestamp, _source_order, line_number, source, row in timeline:
                event_type = row.get("type")
                if source == "autoplay" and event_type == "agent_bridge_assignment":
                    mapping = row.get("bridge_for_agent")
                    teams = row.get("own_team_by_agent")
                    if isinstance(mapping, dict):
                        bridge_for_agent.update({
                            side: bridge for side, bridge in mapping.items()
                            if side in {"A", "B"} and bridge in {"A", "B"}
                        })
                    if isinstance(teams, dict):
                        team_for_agent.update({
                            side: team for side, team in teams.items()
                            if side in {"A", "B"} and team in {"player", "npc"}
                        })
                    continue

                if source == "input" and event_type == "observation":
                    bridge = row.get("side")
                    if bridge in {"A", "B"}:
                        latest_observation[bridge] = row
                    continue

                if source == "autoplay" and event_type == "decision":
                    agent_side = row.get("side")
                    if agent_side not in {"A", "B"}:
                        continue
                    bridge = row.get("bridge_side", bridge_for_agent[agent_side])
                    if bridge not in {"A", "B"}:
                        continue
                    decision_id = row.get("decision_id")
                    legacy_decision = not isinstance(decision_id, str)
                    if legacy_decision:
                        seed = f"{match_id}:minimax-autoplay.jsonl:{line_number}"
                        decision_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]
                    observation = row.get("observation")
                    if not isinstance(observation, dict):
                        old = latest_observation.get(bridge, {})
                        observation = {
                            key: old.get(key)
                            for key in (
                                "observation_id", "generation", "ui_state", "detail",
                                "game_state", "units", "coherent", "settled", "screenshot_file",
                            )
                            if key in old
                        }
                    policy = row.get("policy")
                    if not isinstance(policy, dict):
                        policy = {
                            "name": "fe7-link-arena-minimax-depth-two",
                            "version": 1,
                            "own_team": team_for_agent.get(agent_side),
                            "implementation_sha256": None,
                            "legacy_unhashed": True,
                        }
                    policy_input = {
                        "own_team": policy.get("own_team"),
                        "units": observation.get("units", []),
                    }
                    policy_input_sha256 = row.get("policy_input_sha256")
                    if not isinstance(policy_input_sha256, str):
                        digest_bytes = json.dumps(
                            policy_input, sort_keys=True, separators=(",", ":"),
                        ).encode("utf-8")
                        policy_input_sha256 = hashlib.sha256(digest_bytes).hexdigest()
                    normalized = {
                        "type": "decision",
                        "timestamp": row.get("timestamp", timestamp),
                        "decision_id": decision_id,
                        "side": agent_side,
                        "seat": "1P" if agent_side == "A" else "2P",
                        "bridge_side": bridge,
                        "attempt": row.get("attempt"),
                        "decision": row.get("decision"),
                        "observation_id": row.get("observation_id", observation.get("observation_id")),
                        "generation": row.get("generation", observation.get("generation")),
                        "observation": observation,
                        "policy": policy,
                        "policy_input_sha256": policy_input_sha256,
                    }
                    if self.record(
                        match_id, normalized,
                        source_event_id=(
                            f"minimax-autoplay.jsonl:{line_number}" if legacy_decision else None
                        ),
                        trace_origin="legacy_backfill" if legacy_decision else "live",
                    ):
                        added += 1
                    active[bridge] = (decision_id, agent_side)
                    continue

                if source == "autoplay" and event_type in {
                    "decision_replanned", "decision_interrupted", "exchange_submitted",
                }:
                    agent_side = row.get("side")
                    bridge = row.get("bridge_side")
                    if bridge not in {"A", "B"} and agent_side in {"A", "B"}:
                        bridge = bridge_for_agent[agent_side]
                    current = active.get(bridge) if bridge in {"A", "B"} else None
                    decision_id = row.get("decision_id")
                    if not isinstance(decision_id, str) and current is not None:
                        decision_id = current[0]
                    normalized = {**row, "decision_id": decision_id}
                    if isinstance(decision_id, str) and self.record(
                        match_id, normalized,
                        source_event_id=f"minimax-autoplay.jsonl:{line_number}",
                        trace_origin="legacy_backfill" if "decision_id" not in row else "live",
                    ):
                        added += 1
                    if event_type != "decision_interrupted" and bridge in {"A", "B"}:
                        active.pop(bridge, None)
                    continue

                if source == "input" and event_type == "action":
                    bridge = row.get("side")
                    current = active.get(bridge) if bridge in {"A", "B"} else None
                    decision_id = row.get("decision_id") or (current[0] if current else None)
                    if not isinstance(decision_id, str):
                        continue
                    normalized = {
                        **row,
                        "decision_id": decision_id,
                        "agent_side": row.get("agent_side") or (current[1] if current else None),
                    }
                    normalized["seat"] = (
                        "1P" if normalized["agent_side"] == "A"
                        else "2P" if normalized["agent_side"] == "B"
                        else None
                    )
                    if self.record(
                        match_id, normalized,
                        source_event_id=f"events.jsonl:{line_number}" if "decision_id" not in row else None,
                        trace_origin="legacy_backfill" if "decision_id" not in row else "live",
                    ):
                        added += 1
        return added
