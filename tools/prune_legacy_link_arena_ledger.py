#!/usr/bin/env python3
"""Archive and remove legacy-backfill rows from a Link Arena series ledger."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.link_arena.series import _exclusive_file_lock
from tools.audit_link_arena_ledger import _canonical_event_hash, audit_ledger


_KNOWN_MALFORMED_SHA256 = "1aad963f1b81decd4988583e25fbbc3ba2839f05bac8df529d4329770f7686af"
_MANIFEST_NAME = "legacy-backfill-pruned.json"
_ALLOWED_ORIGINS = {"live", "legacy_backfill"}


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _manifest_for(path: Path) -> dict[str, Any] | None:
    manifest_path = path.parent / _MANIFEST_NAME
    if not manifest_path.exists():
        return None
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read existing prune manifest {manifest_path}: {exc}") from None
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"invalid existing prune manifest: {manifest_path}")
    relative = value.get("archive_relpath")
    expected_hash = value.get("archive_sha256")
    excluded = value.get("excluded_match_ids")
    if (
        not isinstance(relative, str)
        or not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(char not in "0123456789abcdef" for char in expected_hash)
        or not isinstance(excluded, list)
        or any(not isinstance(match_id, str) or not match_id for match_id in excluded)
    ):
        raise ValueError(f"invalid existing prune manifest fields: {manifest_path}")
    archive_relpath = Path(relative)
    if archive_relpath.is_absolute() or ".." in archive_relpath.parts:
        raise ValueError(f"unsafe archive path in prune manifest: {manifest_path}")
    archive = path.parent / archive_relpath
    try:
        actual_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"cannot verify archived ledger {archive}: {exc}") from None
    if actual_hash != expected_hash:
        raise ValueError(f"archived ledger hash mismatch: {archive}")
    return value


def _inspect(path: Path, original: bytes) -> tuple[dict[str, Any], list[bytes], list[dict[str, Any]]]:
    audit, events = audit_ledger(path)
    malformed = audit["malformed_lines"]
    if any(
        audit[key]
        for key in (
            "duplicate_event_id_count",
            "event_id_hash_mismatch_lines",
            "missing_common_field_lines",
            "unknown_event_types",
            "unlinked_actions_and_exchanges",
            "private_reasoning_key_occurrences",
            "hosted_policy_events_missing_reasoning_capture_policy",
        )
    ):
        raise ValueError("ledger has integrity, linkage, or privacy defects beyond the known malformed line")
    if len(malformed) > 1 or any(
        item.get("sha256") != _KNOWN_MALFORMED_SHA256 or item.get("bytes") != 39
        for item in malformed
    ):
        raise ValueError("ledger contains an unexpected malformed line; refusing to discard it")

    event_by_line: dict[int, dict[str, Any]] = {}
    valid_ids: set[str] = set()
    malformed_lines = {item["line"]: item for item in malformed}
    for line_number, raw_line in enumerate(original.splitlines(keepends=True), start=1):
        if line_number in malformed_lines:
            continue
        raw = raw_line.rstrip(b"\r\n")
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError(f"unexpected malformed JSON at line {line_number}") from None
        if not isinstance(event, dict):
            raise ValueError(f"unexpected non-object event at line {line_number}")
        origin = event.get("trace_origin")
        if origin not in _ALLOWED_ORIGINS:
            raise ValueError(f"unknown trace origin {origin!r} at line {line_number}")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or event_id != _canonical_event_hash(event):
            raise ValueError(f"event hash mismatch at line {line_number}")
        if event_id in valid_ids:
            raise ValueError(f"duplicate event ID at line {line_number}")
        valid_ids.add(event_id)
        event_by_line[line_number] = event

    if len(event_by_line) != len(events):
        raise ValueError("event parser and auditor disagree on the number of valid rows")
    legacy_events = [event for event in event_by_line.values()
                     if event.get("trace_origin") == "legacy_backfill"]
    for event in legacy_events:
        inference = event.get("inference")
        provider = inference.get("provider") if isinstance(inference, dict) else None
        if provider not in {None, "local"}:
            raise ValueError("legacy rows include hosted inference; refusing to prune model evidence")

    kept_lines: list[bytes] = []
    for line_number, raw_line in enumerate(original.splitlines(keepends=True), start=1):
        if line_number in malformed_lines:
            continue
        event = event_by_line.get(line_number)
        if event is not None and event.get("trace_origin") == "legacy_backfill":
            continue
        kept_lines.append(raw_line)

    kept_events = [
        event for event in event_by_line.values()
        if event.get("trace_origin") == "live"
    ]
    kept_decision_ids = {
        event.get("decision_id") for event in kept_events
        if event.get("event_type") == "decision"
        and isinstance(event.get("decision_id"), str)
    }
    newly_unlinked = [
        event for event in kept_events
        if event.get("event_type") in {"action", "exchange_submitted"}
        and event.get("decision_id") not in kept_decision_ids
    ]
    if newly_unlinked:
        raise ValueError(
            "pruning would unlink live actions/exchanges from legacy decisions; "
            "refusing to remove their required decision records"
        )

    excluded_match_ids = sorted({
        event["match_id"] for event in legacy_events
        if isinstance(event.get("match_id"), str)
    })
    legacy_event_ids = sorted(event["event_id"] for event in legacy_events)
    report = {
        "valid_rows_before": audit["valid_rows"],
        "live_rows_retained": sum(
            event.get("trace_origin") == "live" for event in event_by_line.values()
        ),
        "legacy_backfill_rows_removed": len(legacy_events),
        "malformed_lines_quarantined": malformed,
        "excluded_match_ids": excluded_match_ids,
        "pruned_legacy_event_ids_sha256": hashlib.sha256(
            ("\n".join(legacy_event_ids) + ("\n" if legacy_event_ids else "")).encode("ascii")
        ).hexdigest(),
    }
    return report, kept_lines, events


def prune_legacy_ledger(path: Path, *, apply: bool) -> dict[str, Any]:
    ledger = path.expanduser().resolve()
    if not ledger.is_file():
        raise ValueError(f"ledger does not exist: {ledger}")
    lock_path = ledger.with_name(".decisions.lock")
    with _exclusive_file_lock(lock_path):
        original = ledger.read_bytes()
        report, kept_lines, _events = _inspect(ledger, original)
        manifest = _manifest_for(ledger)
        if manifest is not None:
            prior_excluded = set(manifest["excluded_match_ids"])
            if not set(report["excluded_match_ids"]).issubset(prior_excluded):
                raise ValueError("new legacy rows appeared outside the previously pruned match set")
        if not apply:
            return {"applied": False, **report}
        if not report["legacy_backfill_rows_removed"] and not report["malformed_lines_quarantined"]:
            return {"applied": True, "already_clean": True, **report}

        original_sha256 = hashlib.sha256(original).hexdigest()
        if manifest is None:
            archive_dir = ledger.parent / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_name = f"decisions.pre-legacy-prune.{original_sha256[:12]}.jsonl"
            archive = archive_dir / archive_name
            if archive.exists():
                if hashlib.sha256(archive.read_bytes()).hexdigest() != original_sha256:
                    raise ValueError(f"archive path already exists with different contents: {archive}")
            else:
                with archive.open("xb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
            archive_relpath = archive.relative_to(ledger.parent).as_posix()
            manifest = {
                "schema_version": 1,
                "operation": "prune_legacy_backfill_from_canonical_ledger",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "archive_relpath": archive_relpath,
                "archive_sha256": original_sha256,
                "excluded_match_ids": report["excluded_match_ids"],
            }
        else:
            prior_excluded = set(manifest["excluded_match_ids"])
            manifest["excluded_match_ids"] = sorted(
                prior_excluded | set(report["excluded_match_ids"])
            )
            manifest["last_pruned_at"] = datetime.now(timezone.utc).isoformat()

        manifest.update({key: value for key, value in report.items()
                         if key != "excluded_match_ids"})
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        _atomic_write(ledger.parent / _MANIFEST_NAME, manifest_bytes)

        cleaned = b"".join(kept_lines)
        _atomic_write(ledger, cleaned)
        after, _after_events = audit_ledger(ledger)
        if (
            after["malformed_lines"]
            or after["trace_origins"].get("legacy_backfill", 0)
            or after["valid_rows"] != report["live_rows_retained"]
            or after["duplicate_event_id_count"]
            or after["event_id_hash_mismatch_lines"]
            or after["unlinked_actions_and_exchanges"]
            or after["private_reasoning_key_occurrences"]
        ):
            raise RuntimeError("post-prune audit failed; original ledger is preserved in the archive")
        return {
            "applied": True,
            "already_clean": False,
            "archive": manifest["archive_relpath"],
            "archive_sha256": manifest["archive_sha256"],
            **report,
            "valid_rows_after": after["valid_rows"],
            "trace_origins_after": after["trace_origins"],
            "malformed_lines_after": after["malformed_lines"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path, help="path to series/decisions.jsonl")
    parser.add_argument("--apply", action="store_true", help="archive then remove legacy and known malformed rows")
    args = parser.parse_args()
    try:
        result = prune_legacy_ledger(args.ledger, apply=args.apply)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
