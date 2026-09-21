"""
Tutorial sequence progress for FE7 Lyn's Tale (FE_TUTORIAL / TUTORIAL_MODE).

FE7 does NOT store tutorial destinations in RAM (see docs/FE7_MEMORY_MAP.md).
Chapter data in fe7_chapters.tutorial_sequence is the authoritative fallback.

Progress heuristic (intentionally simple):
  Walk the sequence in order. Skip steps whose ``coords`` are not a list of
  (x, y) tiles (e.g. string placeholders like ``"defeat_all"``).

  A **move/seize/wait** step is **met** when the acting unit stands on any of
  its coords. An **attack** step is only met by occupancy if the unit has
  already moved/acted (hasMoved); otherwise approach tiles that overlap the
  start square do not skip the step.

  Primary destination = the first (x, y) in that step's coords list. Callers
  (legal_moves / validator) may further prefer a tile inside movement range.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

Coord = Tuple[int, int]


def _as_coord(value: Any) -> Optional[Coord]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    if isinstance(value, dict) and "x" in value and "y" in value:
        try:
            return (int(value["x"]), int(value["y"]))
        except (TypeError, ValueError):
            return None
    return None


def _coords_list(step: dict) -> List[Coord]:
    raw = step.get("coords")
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[Coord] = []
    for item in raw:
        c = _as_coord(item)
        if c is not None:
            out.append(c)
    return out


def _unit_xy(unit: Optional[dict]) -> Optional[Coord]:
    if not unit:
        return None
    return _as_coord([unit.get("x"), unit.get("y")])


def resolve_acting_unit(
    party: Sequence[dict],
    step: Optional[dict] = None,
    preferred_name: Optional[str] = None,
) -> Optional[dict]:
    """Pick the unit the current tutorial step refers to."""
    if preferred_name:
        for u in party:
            if u.get("name") == preferred_name:
                return u
    if step and step.get("unit"):
        name = step["unit"]
        for u in party:
            if u.get("name") == name:
                return u
    # Default: first available (not hasMoved) party member, else first
    for u in party:
        if not u.get("hasMoved"):
            return u
    return party[0] if party else None


def infer_active_tutorial_step(
    sequence: Sequence[dict],
    party: Sequence[dict],
    *,
    acting_unit_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return info about the first unmet tutorial step.

    Keys:
      index: int index into sequence, or -1 if none
      step: the step dict, or None
      target: primary (x, y) destination, or None
      kind: step type string (move/attack/seize/...), or None
      description: step description, or None
      acting_unit: unit name used for progress, or None
    """
    empty = {
        "index": -1,
        "step": None,
        "target": None,
        "kind": None,
        "description": None,
        "acting_unit": None,
    }
    if not sequence:
        return empty

    # Pre-resolve acting unit without a step (name hint / first available)
    hint_unit = resolve_acting_unit(party, None, acting_unit_name)
    hint_name = (hint_unit or {}).get("name") if hint_unit else acting_unit_name

    for idx, step in enumerate(sequence):
        if not isinstance(step, dict):
            continue
        kind = (step.get("step") or "").lower()
        coords = _coords_list(step)
        if not coords:
            # Non-tile steps (e.g. coords="defeat_all") are skipped
            continue
        # Only actionable map destinations
        if kind and kind not in ("move", "attack", "seize", "wait"):
            continue

        unit = resolve_acting_unit(party, step, hint_name)
        unit_xy = _unit_xy(unit)
        # Attack approach tiles often include the unit's starting square (Ch0
        # listed (7,7) while Lyn still had to MOVE to (5,4)). Only MOVE/SEIZE/
        # WAIT occupancy marks a step complete; attack needs hasMoved if known.
        if unit_xy is not None and unit_xy in coords:
            if kind in ("move", "seize", "wait", ""):
                continue
            if kind == "attack":
                if bool(unit.get("hasMoved") or unit.get("moved")):
                    continue
                # else: still the active attack approach — fall through

        return {
            "index": idx,
            "step": step,
            "target": coords[0],
            "kind": step.get("step"),
            "description": step.get("description"),
            "acting_unit": (unit or {}).get("name"),
            "coords": coords,
        }

    return empty


def derive_tutorial_target(
    sequence: Sequence[dict],
    party: Sequence[dict],
    *,
    acting_unit_name: Optional[str] = None,
) -> Optional[Coord]:
    """Primary destination of the active unmet tutorial step, or None."""
    info = infer_active_tutorial_step(
        sequence, party, acting_unit_name=acting_unit_name
    )
    return info.get("target")


def prefer_tutorial_tile(
    target: Optional[Coord],
    movement_tiles: Sequence[Any],
    step_coords: Optional[Sequence[Coord]] = None,
) -> Optional[Coord]:
    """
    Prefer ``target`` if reachable; else first step coord in movement range;
    else the original target (caller may still navigate toward it).
    """
    if target is None and not step_coords:
        return None
    reachable = set()
    for t in movement_tiles or []:
        c = _as_coord(t)
        if c:
            reachable.add(c)
    if target and (not reachable or target in reachable):
        return target
    if step_coords and reachable:
        for c in step_coords:
            if c in reachable:
                return c
    return target
