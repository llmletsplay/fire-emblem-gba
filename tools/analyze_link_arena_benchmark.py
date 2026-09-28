#!/usr/bin/env python3
"""Produce reproducible descriptive statistics from one frozen Link Arena study series."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.link_arena.series import _exclusive_file_lock, _validated_official_score
from tools.audit_link_arena_ledger import audit_ledger
from tools.link_arena import _seat_assignment_for


_VALID_WINNERS = {"A", "B", "draw"}
_SEAT_BY_SIDE = {"A": "1P", "B": "2P"}
_SIDES = ("A", "B")
_POLICY_SLOTS = ("A", "B")
_Z_95 = 1.959963984540054


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    with path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            raw = raw_line.rstrip(b"\r\n")
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError):
                malformed.append({
                    "line": line_number,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
                continue
            if not isinstance(value, dict):
                malformed.append({
                    "line": line_number,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                })
                continue
            rows.append(value)
    return rows, malformed


def _clean_policy_metadata(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item for key, item in value.items()
        if key not in {"policy_slot", "own_team"}
    }


def _manifest_policy_slots(session: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    assignment = session.get("seat_assignment")
    agents = session.get("agents_by_seat")
    if not isinstance(assignment, dict) or not isinstance(agents, dict):
        raise ValueError(f"match {session.get('match_id')} lacks frozen seat or policy metadata")
    slot_by_side = assignment.get("policy_slot_by_seat")
    if not isinstance(slot_by_side, dict) or set(slot_by_side) != set(_SIDES):
        raise ValueError(f"match {session.get('match_id')} has an invalid policy-slot assignment")
    slot_values = list(slot_by_side.values())
    if any(not isinstance(slot, str) or slot not in _POLICY_SLOTS for slot in slot_values):
        raise ValueError(f"match {session.get('match_id')} has an invalid policy-slot name")
    if set(slot_values) != set(_POLICY_SLOTS):
        raise ValueError(f"match {session.get('match_id')} must assign both policy slots exactly once")

    metadata_by_slot: dict[str, dict[str, Any]] = {}
    for side in _SIDES:
        metadata = agents.get(side)
        if not isinstance(metadata, dict) or metadata.get("policy_slot") != slot_by_side[side]:
            raise ValueError(f"match {session.get('match_id')} has inconsistent agent-slot metadata")
        metadata_by_slot[slot_by_side[side]] = _clean_policy_metadata(metadata)
    return dict(slot_by_side), metadata_by_slot


def _read_sessions(data_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    sessions: dict[str, dict[str, Any]] = {}
    malformed: list[str] = []
    for path in sorted(data_dir.glob("*/session.json")):
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed.append(path.parent.name)
            continue
        if not isinstance(session, dict) or not isinstance(session.get("match_id"), str):
            malformed.append(path.parent.name)
            continue
        match_id = session["match_id"]
        if match_id in sessions:
            raise ValueError(f"duplicate match manifest ID: {match_id}")
        sessions[match_id] = session
    return sessions, malformed


def _wilson_interval(successes: int, failures: int) -> dict[str, float | int | None]:
    n = successes + failures
    if n == 0:
        return {"n": 0, "estimate": None, "lower_95": None, "upper_95": None}
    p = successes / n
    z2 = _Z_95 * _Z_95
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    margin = _Z_95 * math.sqrt((p * (1 - p) / n) + z2 / (4 * n * n)) / denominator
    return {
        "n": n,
        "estimate": p,
        "lower_95": max(0.0, center - margin),
        "upper_95": min(1.0, center + margin),
    }


def _percentile(sorted_values: list[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, math.ceil(probability * len(sorted_values)) - 1))
    return sorted_values[index]


def _bootstrap_mean_interval(
    values: list[float], *, seed: int, resamples: int,
) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "lower_95": None, "upper_95": None}
    if len(values) == 1:
        value = values[0]
        return {"n": 1, "mean": value, "lower_95": None, "upper_95": None}
    ordered_values = sorted(values)
    rng = random.Random(seed)
    count = len(ordered_values)
    estimates = sorted(
        sum(ordered_values[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(resamples)
    )
    return {
        "n": count,
        "mean": statistics.fmean(values),
        "lower_95": _percentile(estimates, 0.025),
        "upper_95": _percentile(estimates, 0.975),
    }


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _usage_count(usage: Any, names: tuple[str, ...]) -> int | None:
    if not isinstance(usage, dict):
        return None
    for name in names:
        value = _nonnegative_int(usage.get(name))
        if value is not None:
            return value
    return None


def _collect_inference_metrics(metric: dict[str, Any], inference: Any) -> None:
    if not isinstance(inference, dict):
        return
    latency = inference.get("latency_ms")
    if isinstance(latency, (int, float)) and not isinstance(latency, bool) and latency >= 0:
        metric["latency_ms"].append(float(latency))
    usage = inference.get("usage")
    input_tokens = _usage_count(usage, ("prompt_tokens", "input_tokens"))
    output_tokens = _usage_count(usage, ("completion_tokens", "output_tokens"))
    reasoning_tokens = _usage_count(usage, ("reasoning_tokens",))
    if reasoning_tokens is None and isinstance(usage, dict):
        details = usage.get("completion_tokens_details")
        if isinstance(details, dict):
            reasoning_tokens = _usage_count(details, ("reasoning_tokens",))
    if input_tokens is not None:
        metric["input_tokens"] += input_tokens
        metric["input_token_observations"] += 1
    if output_tokens is not None:
        metric["output_tokens"] += output_tokens
        metric["output_token_observations"] += 1
    if reasoning_tokens is not None:
        metric["reported_reasoning_tokens"] += reasoning_tokens
        metric["reasoning_token_observations"] += 1


def _summarize(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": _percentile(ordered, 0.95),
    }


def _load_results(path: Path) -> tuple[
    dict[str, dict[str, Any]], list[dict[str, Any]], int, int,
]:
    rows, malformed = _read_jsonl(path)
    valid: dict[str, dict[str, Any]] = {}
    invalid_rows = 0
    duplicates = 0
    for row in rows:
        match_id = row.get("match_id")
        winner = row.get("winner")
        if not isinstance(match_id, str) or not isinstance(winner, str) or winner not in _VALID_WINNERS:
            invalid_rows += 1
            continue
        if match_id in valid:
            duplicates += 1
            continue
        result = dict(row)
        try:
            score = _validated_official_score(row.get("official_score"), winner=winner)
        except (TypeError, ValueError):
            score = None
        if score is None:
            result.pop("official_score", None)
            result["official_score_status"] = "unavailable"
        else:
            result["official_score"] = score
            result["official_score_status"] = "verified"
        valid[match_id] = result
    return valid, malformed, invalid_rows, duplicates


def _validate_study_manifests(sessions: dict[str, dict[str, Any]]) -> tuple[
    dict[str, str], dict[str, dict[str, Any]], str, int | None, dict[str, Any],
]:
    if not sessions:
        raise ValueError("no match session manifests found; select a frozen study DataDir")
    baseline_policies: dict[str, dict[str, Any]] | None = None
    baseline_hashes: tuple[str, str] | None = None
    baseline_policy: str | None = None
    baseline_seed: int | None = None
    baseline_slots: dict[str, str] | None = None
    baseline_runtime: dict[str, Any] | None = None
    for match_id, session in sessions.items():
        slot_by_side, metadata_by_slot = _manifest_policy_slots(session)
        assignment = session["seat_assignment"]
        schedule = assignment.get("policy")
        seed = assignment.get("seed")
        if not isinstance(schedule, str) or schedule not in {
            "fixed_policy_slots_v1",
            "deterministic_randomized_seat_swapped_pairs_v1",
        }:
            raise ValueError(f"match {match_id} has an unknown seat-schedule version")
        alternate = schedule == "deterministic_randomized_seat_swapped_pairs_v1"
        if alternate and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise ValueError(f"match {match_id} has an invalid seat-order seed")
        ordinal = assignment.get("match_ordinal")
        if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
            raise ValueError(f"match {match_id} has an invalid match ordinal")
        expected_assignment = _seat_assignment_for(
            ordinal, seed=seed if alternate else 0, alternate=alternate,
        )
        if assignment != expected_assignment:
            raise ValueError(f"match {match_id} seat assignment does not match its frozen schedule")
        rom_hash = session.get("rom_sha256")
        save_hash = session.get("seed_save_sha256")
        runtime = session.get("runtime_provenance")
        if not isinstance(rom_hash, str) or not isinstance(save_hash, str):
            raise ValueError(f"match {match_id} lacks ROM/save hashes")
        if not isinstance(runtime, dict) or any(
            not isinstance(runtime.get(key), str)
            or len(runtime[key]) != 64
            or any(char not in "0123456789abcdef" for char in runtime[key])
            for key in ("source_tree_sha256", "mgba_binary_sha256")
        ):
            raise ValueError(f"match {match_id} lacks frozen runtime provenance")
        bridge_hash = session.get("bridge_script_sha256")
        if (
            not isinstance(bridge_hash, str) or len(bridge_hash) != 64
            or any(char not in "0123456789abcdef" for char in bridge_hash)
        ):
            raise ValueError(f"match {match_id} lacks a valid generated bridge-script hash")
        if baseline_policies is None:
            baseline_policies = metadata_by_slot
            baseline_hashes = (rom_hash, save_hash)
            baseline_policy = schedule
            baseline_seed = seed if alternate else None
            baseline_slots = slot_by_side
            baseline_runtime = runtime
        else:
            if metadata_by_slot != baseline_policies:
                raise ValueError("session manifests contain different policy configurations")
            if (rom_hash, save_hash) != baseline_hashes:
                raise ValueError("session manifests contain different ROM/save hashes")
            if runtime != baseline_runtime:
                raise ValueError("session manifests contain different runtime or emulator provenance")
            if schedule != baseline_policy or (seed if alternate else None) != baseline_seed:
                raise ValueError("session manifests mix seat-schedule modes or seeds")
            # Every completed pair must swap slots; a single-runner seat change
            # is a malformed study schedule, not an extra observation.
            if alternate:
                prior_assignment = next((
                    previous["seat_assignment"] for previous in sessions.values()
                    if previous is not session
                    and isinstance(previous.get("seat_assignment"), dict)
                    and previous["seat_assignment"].get("pair_block") == assignment.get("pair_block")
                    and previous["seat_assignment"].get("match_in_pair") != assignment.get("match_in_pair")
                ), None)
                if prior_assignment is not None and prior_assignment.get("seat_swapped") == assignment.get("seat_swapped"):
                    raise ValueError(f"match {match_id} does not swap seats with its paired match")
    assert baseline_policies is not None and baseline_slots is not None and baseline_runtime is not None
    return baseline_slots, baseline_policies, str(baseline_policy), baseline_seed, baseline_runtime


def analyze(
    data_dir: Path, *, bootstrap_seed: int = 20260928, bootstrap_resamples: int = 10_000,
) -> dict[str, Any]:
    root = data_dir.expanduser().resolve()
    results_path = root / "series" / "results.jsonl"
    decisions_path = root / "series" / "decisions.jsonl"
    if not results_path.is_file() or not decisions_path.is_file():
        raise ValueError("DataDir must contain series/results.jsonl and series/decisions.jsonl")

    sessions, malformed_sessions = _read_sessions(root)
    baseline_slots, policy_metadata, schedule, seat_order_seed, runtime_provenance = _validate_study_manifests(sessions)
    results, malformed_results, invalid_result_rows, duplicate_result_ids = _load_results(results_path)
    result_ids = set(results)
    session_ids = set(sessions)
    missing_manifests = sorted(result_ids - session_ids)
    if missing_manifests:
        raise ValueError(f"completed results lack match manifests: {missing_manifests[:5]}")

    with _exclusive_file_lock(decisions_path.with_name(".decisions.lock")):
        audit, events = audit_ledger(decisions_path)
    severe_audit_issues = any((
        audit["duplicate_event_id_count"],
        audit["event_id_hash_mismatch_lines"],
        audit["missing_common_field_lines"],
        audit["unknown_event_types"],
        audit["unlinked_actions_and_exchanges"],
        audit["private_reasoning_key_occurrences"],
    ))
    if severe_audit_issues:
        raise ValueError("decision ledger has integrity/privacy issues; run tools/audit_link_arena_ledger.py")

    outcome = {
        slot: {"wins": 0, "losses": 0, "draws": 0, "by_runner_seat": {
            "1P": {"wins": 0, "losses": 0, "draws": 0},
            "2P": {"wins": 0, "losses": 0, "draws": 0},
        }}
        for slot in _POLICY_SLOTS
    }
    points: dict[str, list[float]] = {slot: [] for slot in _POLICY_SLOTS}
    match_scores_by_pair: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    for match_id, result in results.items():
        session = sessions[match_id]
        slot_by_side, _ = _manifest_policy_slots(session)
        winner_side = result["winner"]
        for side in _SIDES:
            slot = slot_by_side[side]
            seat = _SEAT_BY_SIDE[side]
            if winner_side == "draw":
                outcome[slot]["draws"] += 1
                outcome[slot]["by_runner_seat"][seat]["draws"] += 1
            elif winner_side == side:
                outcome[slot]["wins"] += 1
                outcome[slot]["by_runner_seat"][seat]["wins"] += 1
            else:
                outcome[slot]["losses"] += 1
                outcome[slot]["by_runner_seat"][seat]["losses"] += 1

        score = result.get("official_score")
        point_by_seat = score.get("points_by_seat") if isinstance(score, dict) else None
        if isinstance(point_by_seat, dict):
            for side in _SIDES:
                value = point_by_seat.get(_SEAT_BY_SIDE[side])
                if isinstance(value, int) and not isinstance(value, bool):
                    points[slot_by_side[side]].append(float(value))

        assignment = session["seat_assignment"]
        if assignment.get("policy") == "deterministic_randomized_seat_swapped_pairs_v1":
            block = assignment["pair_block"]
            match_in_pair = assignment["match_in_pair"]
            pair_match: dict[str, Any] = {
                "winner_slot": None if winner_side == "draw" else slot_by_side[winner_side],
                "seat_swapped": assignment["seat_swapped"],
            }
            if isinstance(point_by_seat, dict):
                pair_match["points_by_slot"] = {
                    slot_by_side[side]: point_by_seat[_SEAT_BY_SIDE[side]]
                    for side in _SIDES
                }
            match_scores_by_pair[block][match_in_pair] = pair_match

    decision_metrics = {
        slot: {
            "decisions": 0,
            "policy_call_failures": 0,
            "replans": 0,
            "interruptions": 0,
            "submitted_exchanges": 0,
            "verified_button_actions": 0,
            "verified_button_pulses": 0,
            "rationales": 0,
            "latency_ms": [],
            "input_tokens": 0,
            "input_token_observations": 0,
            "output_tokens": 0,
            "output_token_observations": 0,
            "reported_reasoning_tokens": 0,
            "reasoning_token_observations": 0,
        }
        for slot in _POLICY_SLOTS
    }
    orphan_ledger_matches: set[str] = set()
    for event in events:
        match_id = event.get("match_id")
        if not isinstance(match_id, str) or match_id not in sessions:
            if isinstance(match_id, str):
                orphan_ledger_matches.add(match_id)
            continue
        session = sessions[match_id]
        slot_by_side, _ = _manifest_policy_slots(session)
        event_type = event.get("event_type")
        side = event.get("side")
        if event_type == "action":
            side = event.get("agent_side") or side
        if side not in _SIDES:
            seat = event.get("seat")
            side = "A" if seat == "1P" else "B" if seat == "2P" else None
        if side not in _SIDES:
            continue
        metric = decision_metrics[slot_by_side[side]]
        if event_type == "decision":
            metric["decisions"] += 1
            inference = event.get("inference")
            _collect_inference_metrics(metric, inference)
            inference = inference if isinstance(inference, dict) else {}
            if isinstance(inference.get("rationale"), str) and inference["rationale"].strip():
                metric["rationales"] += 1
        elif event_type == "policy_call_failed":
            metric["policy_call_failures"] += 1
            _collect_inference_metrics(metric, event.get("inference"))
        elif event_type == "decision_replanned":
            metric["replans"] += 1
        elif event_type == "decision_interrupted":
            metric["interruptions"] += 1
        elif event_type == "exchange_submitted":
            metric["submitted_exchanges"] += 1
        elif event_type == "action":
            metric["verified_button_actions"] += 1
            buttons = event.get("completed_buttons")
            if isinstance(buttons, list):
                metric["verified_button_pulses"] += len(buttons)

    if orphan_ledger_matches:
        raise ValueError(
            "decision ledger contains match IDs without session manifests: "
            + ", ".join(sorted(orphan_ledger_matches)[:5])
        )

    paired_scores: list[float] = []
    paired_point_differences: list[float] = []
    complete_pair_blocks: list[int] = []
    for block, matches in sorted(match_scores_by_pair.items()):
        first = matches.get(1)
        second = matches.get(2)
        if first is None or second is None or first["seat_swapped"] == second["seat_swapped"]:
            continue
        score_a = 0.0
        for match in (first, second):
            if match["winner_slot"] == "A":
                score_a += 1.0
            elif match["winner_slot"] is None:
                score_a += 0.5
        paired_scores.append(score_a / 2)
        complete_pair_blocks.append(block)
        first_points = first.get("points_by_slot")
        second_points = second.get("points_by_slot")
        if isinstance(first_points, dict) and isinstance(second_points, dict):
            difference = (
                first_points["A"] + second_points["A"]
                - first_points["B"] - second_points["B"]
            ) / 2
            paired_point_differences.append(float(difference))

    slot_summary: dict[str, Any] = {}
    for slot in _POLICY_SLOTS:
        record = outcome[slot]
        decisive = _wilson_interval(record["wins"], record["losses"])
        points_ci = _bootstrap_mean_interval(
            points[slot], seed=bootstrap_seed + (0 if slot == "A" else 1),
            resamples=bootstrap_resamples,
        )
        raw_decisions = decision_metrics[slot]
        metric = dict(raw_decisions)
        latency_ms = metric.pop("latency_ms")
        metric["latency_ms"] = _summarize(latency_ms)
        total_tokens = metric["input_tokens"] + metric["output_tokens"]
        metric["total_observed_input_output_tokens"] = total_tokens
        metric["cost"] = None
        metric["cost_note"] = "not computed: no versioned provider price schedule is recorded"
        descriptor = policy_metadata[slot]
        slot_summary[slot] = {
            "policy": {
                "name": descriptor.get("name"),
                "kind": descriptor.get("kind"),
                "provider": descriptor.get("provider"),
                "model_requested": descriptor.get("model_requested"),
                "base_url": descriptor.get("base_url"),
                "prompt_template": descriptor.get("prompt_template"),
                "prompt_template_sha256": descriptor.get("prompt_template_sha256"),
            },
            "outcomes": {
                "wins": record["wins"],
                "losses": record["losses"],
                "draws": record["draws"],
                "decisive_win_rate_wilson_95": decisive,
                "by_runner_seat": record["by_runner_seat"],
            },
            "official_points": {
                "n": len(points[slot]),
                "mean_and_match_bootstrap_95": points_ci,
            },
            "decisions": metric,
        }

    warnings = []
    if malformed_results or invalid_result_rows or duplicate_result_ids:
        warnings.append("invalid, malformed, or duplicate result rows are excluded")
    if audit["malformed_lines"]:
        warnings.append("malformed decision-ledger lines were excluded; inspect decision_ledger_audit")
    if malformed_sessions:
        warnings.append("malformed session directories were excluded")
    fatal_audit_summary = {
        "valid_events": audit["valid_rows"],
        "event_types": audit["event_types"],
        "trace_origins": audit["trace_origins"],
        "malformed_lines": audit["malformed_lines"],
        "duplicate_event_ids": audit["duplicate_event_id_count"],
        "event_id_hash_mismatch_lines": audit["event_id_hash_mismatch_lines"],
        "missing_common_field_lines": audit["missing_common_field_lines"],
        "unknown_event_types": audit["unknown_event_types"],
        "unlinked_actions_and_exchanges": audit["unlinked_actions_and_exchanges"],
        "private_reasoning_key_occurrences": audit["private_reasoning_key_occurrences"],
        "hosted_decisions_with_visible_rationale": audit["hosted_decisions_with_visible_rationale"],
    }
    incomplete_match_ids = sorted(session_ids - result_ids)
    return {
        "analysis_schema_version": 1,
        "analysis_status": "descriptive; exploratory unless separately preregistered",
        "frozen_condition": {
            "seat_schedule": schedule,
            "seat_order_seed": seat_order_seed,
            "rom_sha256": next(iter(sessions.values())).get("rom_sha256"),
            "seed_save_sha256": next(iter(sessions.values())).get("seed_save_sha256"),
            "policy_slots": {
                slot: {
                    "provider": policy_metadata[slot].get("provider"),
                    "model_requested": policy_metadata[slot].get("model_requested"),
                    "name": policy_metadata[slot].get("name"),
                }
                for slot in _POLICY_SLOTS
            },
        },
        "runtime_provenance": runtime_provenance,
        "sample": {
            "started_match_manifests": len(sessions),
            "completed_matches": len(results),
            "incomplete_match_count": len(incomplete_match_ids),
            "incomplete_match_ids": incomplete_match_ids,
            "complete_seat_swapped_pair_blocks": len(complete_pair_blocks),
            "complete_pair_block_ids": complete_pair_blocks,
        },
        "policy_slots": slot_summary,
        "paired_seat_swap_analysis": {
            "estimand": "policy-slot A match score across two games with opposite seat assignments",
            "unit": "two-match seat-swapped block",
            "score_per_match": "win=1, draw=0.5, loss=0; averaged within block",
            "bootstrap_seed": bootstrap_seed,
            "bootstrap_resamples": bootstrap_resamples,
            "policy_slot_A_mean_score_per_match_bootstrap_95": _bootstrap_mean_interval(
                paired_scores, seed=bootstrap_seed + 2, resamples=bootstrap_resamples,
            ),
            "policy_slot_A_minus_B_official_point_difference_bootstrap_95": _bootstrap_mean_interval(
                paired_point_differences, seed=bootstrap_seed + 3,
                resamples=bootstrap_resamples,
            ),
            "complete_pair_blocks_with_two_verified_point_scores": len(paired_point_differences),
            "block_scores_for_policy_slot_A": paired_scores,
            "interpretation_limit": "seat swapping does not control FE7 combat RNG; incomplete blocks are omitted",
        },
        "decision_ledger_audit": fatal_audit_summary,
        "result_quality": {
            "malformed_lines": malformed_results,
            "invalid_rows": invalid_result_rows,
            "duplicate_match_ids": duplicate_result_ids,
            "malformed_session_directories": malformed_sessions,
            "ledger_match_ids_without_session": sorted(orphan_ledger_matches),
            "warnings": warnings,
        },
        "methods": {
            "decisive_win_interval": "Wilson score 95% interval; draws reported separately",
            "points_interval": "percentile bootstrap across matches; descriptive only",
            "paired_interval": "percentile bootstrap across complete two-match seat-swap blocks",
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": bootstrap_seed,
            "hidden_chain_of_thought": "not collected; only constrained visible rationale and provider-reported usage are analyzed",
            "inference_cost": "not calculated without a versioned provider pricing manifest",
            "privacy": "analysis output contains aggregate metrics and hashes, not prompts, responses, rationales, API keys, screenshots, or machine paths",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path, help="one frozen experiment DataDir")
    parser.add_argument("--output", type=Path, help="write JSON to this path instead of stdout")
    parser.add_argument("--bootstrap-seed", type=int, default=20260928)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    args = parser.parse_args()
    if args.bootstrap_resamples < 100:
        parser.error("--bootstrap-resamples must be at least 100")
    try:
        result = analyze(
            args.data_dir,
            bootstrap_seed=args.bootstrap_seed,
            bootstrap_resamples=args.bootstrap_resamples,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
