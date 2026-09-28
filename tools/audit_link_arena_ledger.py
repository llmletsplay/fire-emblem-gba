#!/usr/bin/env python3
"""Audit a Link Arena series decision ledger and optionally export valid rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


_EVENT_TYPES = {
    "decision",
    "decision_replanned",
    "decision_interrupted",
    "exchange_submitted",
    "action",
    "policy_call_failed",
}
_JOINED_EVENT_TYPES = {"action", "exchange_submitted"}
_PRIVATE_REASONING_KEYS = {
    "reasoning_content",
    "chain_of_thought",
    "hidden_reasoning",
}


def _canonical_event_hash(event: dict[str, Any]) -> str:
    payload = {key: value for key, value in event.items() if key != "event_id"}
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _find_private_reasoning_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if str(key).lower() in _PRIVATE_REASONING_KEYS:
                found.append(child_path)
            found.extend(_find_private_reasoning_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_private_reasoning_keys(child, f"{path}[{index}]"))
    return found


def audit_ledger(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    valid_rows: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    event_types: Counter[str] = Counter()
    origins: Counter[str] = Counter()
    ids: Counter[str] = Counter()
    id_hash_mismatches: list[int] = []
    missing_common_fields: list[int] = []
    unknown_event_types: list[dict[str, Any]] = []
    hidden_reasoning_fields: list[dict[str, Any]] = []
    decision_rows_by_match_side: Counter[str] = Counter()
    models_by_provider: Counter[str] = Counter()
    rows_by_match: Counter[str] = Counter()
    hosted_decisions_with_visible_rationale = 0

    with path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            raw_content = raw_line.rstrip(b"\r\n")
            if not raw_content:
                continue
            try:
                row = json.loads(raw_content)
            except (json.JSONDecodeError, UnicodeDecodeError):
                malformed.append({
                    "line": line_number,
                    "bytes": len(raw_content),
                    "sha256": hashlib.sha256(raw_content).hexdigest(),
                })
                continue
            if not isinstance(row, dict):
                malformed.append({
                    "line": line_number,
                    "bytes": len(raw_content),
                    "sha256": hashlib.sha256(raw_content).hexdigest(),
                })
                continue

            valid_rows.append(row)
            event_type = row.get("event_type")
            if isinstance(event_type, str):
                event_types[event_type] += 1
            else:
                event_type = "<missing>"
                event_types[event_type] += 1
            if event_type not in _EVENT_TYPES:
                unknown_event_types.append({"line": line_number, "event_type": event_type})

            origin = row.get("trace_origin")
            if isinstance(origin, str):
                origins[origin] += 1
            match_id = row.get("match_id")
            if isinstance(match_id, str):
                rows_by_match[match_id] += 1

            missing = [
                key for key in ("schema_version", "event_type", "match_id", "timestamp", "trace_origin", "event_id")
                if key not in row
            ]
            if missing:
                missing_common_fields.append(line_number)

            event_id = row.get("event_id")
            if isinstance(event_id, str):
                ids[event_id] += 1
                try:
                    if _canonical_event_hash(row) != event_id:
                        id_hash_mismatches.append(line_number)
                except (TypeError, ValueError):
                    id_hash_mismatches.append(line_number)

            private_keys = _find_private_reasoning_keys(row)
            if private_keys:
                hidden_reasoning_fields.append({"line": line_number, "keys": private_keys})

            decision_id = row.get("decision_id")
            if event_type == "decision" and isinstance(decision_id, str):
                side = row.get("side") or row.get("seat") or "<unknown>"
                decision_rows_by_match_side[f"{match_id}/{side}"] += 1
                inference = row.get("inference")
                inference = inference if isinstance(inference, dict) else {}
                provider = str(inference.get("provider") or "local")
                model = str(inference.get("model_resolved") or inference.get("model_requested") or inference.get("policy") or "unknown")
                models_by_provider[f"{provider}/{model}"] += 1
                rationale = inference.get("rationale")
                if provider != "local" and isinstance(rationale, str) and rationale.strip():
                    hosted_decisions_with_visible_rationale += 1

    # Check joins after the full scan so events can appear in either order.
    decision_ids = {
        row.get("decision_id") for row in valid_rows
        if row.get("event_type") == "decision" and isinstance(row.get("decision_id"), str)
    }
    joined_rows = Counter()
    unlinked_rows = Counter()
    for row in valid_rows:
        event_type = row.get("event_type")
        if event_type not in _JOINED_EVENT_TYPES:
            continue
        decision_id = row.get("decision_id")
        if isinstance(decision_id, str) and decision_id in decision_ids:
            joined_rows[event_type] += 1
        else:
            unlinked_rows[event_type] += 1

    duplicate_event_ids = sum(count - 1 for count in ids.values() if count > 1)
    summary = {
        "schema_version": 1,
        "ledger_path": str(path),
        "valid_rows": len(valid_rows),
        "malformed_lines": malformed,
        "event_types": dict(sorted(event_types.items())),
        "trace_origins": dict(sorted(origins.items())),
        "matches": len(rows_by_match),
        "rows_by_match": dict(sorted(rows_by_match.items())),
        "decision_rows_by_match_side": dict(sorted(decision_rows_by_match_side.items())),
        "model_provider_decision_rows": dict(sorted(models_by_provider.items())),
        "unique_event_ids": len(ids),
        "duplicate_event_id_count": duplicate_event_ids,
        "event_id_hash_mismatch_lines": id_hash_mismatches,
        "missing_common_field_lines": missing_common_fields,
        "unknown_event_types": unknown_event_types,
        "joined_actions_and_exchanges": dict(sorted(joined_rows.items())),
        "unlinked_actions_and_exchanges": dict(sorted(unlinked_rows.items())),
        "private_reasoning_key_occurrences": hidden_reasoning_fields,
        "hosted_decisions_with_visible_rationale": hosted_decisions_with_visible_rationale,
    }
    return summary, valid_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="path to series/decisions.jsonl")
    parser.add_argument(
        "--export-valid", type=Path,
        help="write valid JSON rows to this derived file and an adjacent .audit.json report",
    )
    args = parser.parse_args()
    try:
        summary, valid_rows = audit_ledger(args.ledger)
    except OSError as exc:
        parser.error(f"cannot read ledger: {exc}")

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.export_valid:
        args.export_valid.parent.mkdir(parents=True, exist_ok=True)
        with args.export_valid.open("w", encoding="utf-8", newline="\n") as output:
            for row in valid_rows:
                output.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        audit_path = args.export_valid.with_suffix(args.export_valid.suffix + ".audit.json")
        audit_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    has_integrity_issues = any((
        summary["malformed_lines"],
        summary["duplicate_event_id_count"],
        summary["event_id_hash_mismatch_lines"],
        summary["missing_common_field_lines"],
        summary["unknown_event_types"],
        summary["unlinked_actions_and_exchanges"],
        summary["private_reasoning_key_occurrences"],
    ))
    return 1 if has_integrity_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
