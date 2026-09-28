"""Persistent results for a sequence of FE7 Link Arena matches."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_WINNER_LABEL = {"A": "1P", "B": "2P", "draw": "DRAW"}


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
            for result in self._results:
                label = _WINNER_LABEL.get(result.get("winner"))
                if label == "DRAW":
                    draws += 1
                elif label in wins:
                    wins[label] += 1
            recent = [
                {
                    "game_number": result.get("game_number"),
                    "match_id": result.get("match_id"),
                    "winner": _WINNER_LABEL[result["winner"]],
                }
                for result in reversed(self._results[-5:])
            ]
            return {
                "games_played": len(self._results),
                "wins": wins,
                "draws": draws,
                "recent_games": recent,
            }
