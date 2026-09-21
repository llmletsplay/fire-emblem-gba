"""
Tutorial sequence progress for FE7 Lyn's Tale (FE_TUTORIAL / TUTORIAL_MODE).

FE7 does NOT store tutorial destinations in RAM (see docs/FE7_MEMORY_MAP.md).
Chapter data in fe7_chapters.tutorial_sequence is the authoritative fallback.

Progress heuristic:
  Walk the sequence in order. Skip steps whose ``coords`` are not a list of
  (x, y) tiles (e.g. string placeholders like ``"defeat_all"``).

  Completion by step kind (important — do NOT treat occupancy alone as done
  for attack/item/seize, or the harness skips the action):

  - move:  acting unit stands on any step tile
  - wait:  acting unit on tile AND hasMoved (WAIT confirmed), OR implied
           complete (see below)
  - attack / item / seize: unit on tile AND hasMoved (action finished)
    Mere overlap with an approach tile does NOT complete these steps.

  Earlier steps are also implied complete when the unit already stands on a
  *later* step's tile (mid-chapter resume), or — for WAIT — when an enemy is
  already adjacent to the next attack tile (post-enemy-phase after WAIT).

  The first unmet actionable step is active. Primary destination = first
  (x, y) in that step's coords list.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

Coord = Tuple[int, int]

# Steps that require the unit to have acted (hasMoved) before counting complete,
# even when already standing on a destination / approach tile.
_ACTION_KINDS = frozenset({"wait", "attack", "item", "seize"})


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


def _step_complete(kind: str, unit: Optional[dict], coords: Sequence[Coord]) -> bool:
    """Return True when this tutorial step should be advanced past (local rules)."""
    unit_xy = _unit_xy(unit)
    if unit_xy is None or unit_xy not in coords:
        return False
    kind_l = (kind or "").lower()
    if kind_l in _ACTION_KINDS:
        # Occupancy alone is not enough — must have finished the action.
        return bool(unit and unit.get("hasMoved"))
    # Plain move: standing on the destination tile completes the step.
    return True


def _implied_complete(
    sequence: Sequence[dict],
    idx: int,
    unit_xy: Optional[Coord],
    enemies: Optional[Sequence[dict]] = None,
) -> bool:
    """Earlier steps are done if unit already occupies a later milestone tile,
    or WAIT is done because an enemy sits adjacent to the next attack tile
    (Ch0: brigand advanced to (7,6) after WAIT)."""
    if unit_xy is not None:
        for later in sequence[idx + 1 :]:
            if not isinstance(later, dict):
                continue
            if unit_xy in _coords_list(later):
                return True

    step = sequence[idx] if 0 <= idx < len(sequence) else None
    if not isinstance(step, dict):
        return False
    kind = (step.get("step") or "").lower()
    if kind != "wait" or not enemies:
        return False

    # Find next attack step; if any enemy is adjacent to any of its tiles,
    # enemy phase already ran → WAIT is done even if hasMoved reset.
    for later in sequence[idx + 1 :]:
        if not isinstance(later, dict):
            continue
        if (later.get("step") or "").lower() != "attack":
            continue
        attack_coords = _coords_list(later)
        for e in enemies:
            ec = _as_coord([e.get("x"), e.get("y")])
            if ec is None:
                continue
            ex, ey = ec
            for ax, ay in attack_coords:
                if abs(ex - ax) + abs(ey - ay) == 1:
                    return True
        break
    return False


def infer_active_tutorial_step(
    sequence: Sequence[dict],
    party: Sequence[dict],
    *,
    acting_unit_name: Optional[str] = None,
    enemies: Optional[Sequence[dict]] = None,
) -> Dict[str, Any]:
    """
    Return info about the first unmet tutorial step.

    Keys:
      index: int index into sequence, or -1 if none
      step: the step dict, or None
      target: primary (x, y) destination, or None
      kind: step type string (move/attack/seize/wait/item/...), or None
      description: step description, or None
      acting_unit: unit name used for progress, or None
      coords: list of step tiles
    """
    empty = {
        "index": -1,
        "step": None,
        "target": None,
        "kind": None,
        "description": None,
        "acting_unit": None,
        "coords": [],
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
        # Actionable map destinations (include wait + item for Ch0)
        if kind and kind not in ("move", "attack", "seize", "wait", "item"):
            continue

        unit = resolve_acting_unit(party, step, hint_name)
        unit_xy = _unit_xy(unit)
        if _step_complete(kind, unit, coords) or _implied_complete(
            sequence, idx, unit_xy, enemies
        ):
            continue

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
    enemies: Optional[Sequence[dict]] = None,
) -> Optional[Coord]:
    """Primary destination of the active unmet tutorial step, or None."""
    info = infer_active_tutorial_step(
        sequence,
        party,
        acting_unit_name=acting_unit_name,
        enemies=enemies,
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
