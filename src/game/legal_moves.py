"""
Deterministic legal-move catalog for the FE harness.

The model picks MOVE: <id>. The harness maps that id to a semantic COMMAND
string and command_executor presses the buttons. No free-form button timing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple


def _tile(t) -> Optional[Tuple[int, int]]:
    if t is None:
        return None
    if isinstance(t, (list, tuple)) and len(t) >= 2:
        try:
            return (int(t[0]), int(t[1]))
        except (TypeError, ValueError):
            return None
    if isinstance(t, dict) and "x" in t and "y" in t:
        try:
            return (int(t["x"]), int(t["y"]))
        except (TypeError, ValueError):
            return None
    return None


def _available_units(state: dict) -> List[Dict[str, Any]]:
    unit_status = state.get("unit_status") or {}
    out = []
    for u in state.get("party") or []:
        name = u.get("name")
        if not name:
            continue
        status = unit_status.get(name)
        if status == "already_acted" or status == "rescued":
            continue
        if status == "available":
            out.append(u)
            continue
        if u.get("hasMoved"):
            continue
        out.append(u)
    return out


def build_legal_moves(state: dict, max_moves: int = 28) -> List[Dict[str, Any]]:
    """Build prioritized legal high-level moves from current LLM game_state."""
    moves: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    def add(kind: str, command: str, summary: str) -> None:
        cmd = " ".join(command.split())
        if not cmd or cmd in seen:
            return
        seen.add(cmd)
        moves.append(
            {
                "id": f"m{len(moves)}",
                "kind": kind,
                "command": cmd,
                "summary": summary,
            }
        )

    text_box = bool(state.get("text_box_visible"))
    input_locked = bool(state.get("input_locked"))
    in_dialogue = bool(state.get("in_dialogue"))
    in_menu = bool(state.get("in_menu"))
    screen = (state.get("screen_context") or "") + " " + (state.get("previous_action") or "")
    screen_l = screen.lower()

    # Map-play signals: never collapse to dialogue-only when these are present.
    has_map_play = bool(
        state.get("movement_tiles")
        or state.get("attack_opportunities")
        or state.get("unit_is_selected")
        or state.get("selected_unit")
        or state.get("cursor_on_player")
    )

    # Dialogue only when clearly in a text box / cutscene AND not mid map action.
    # Match llmdriver story-dialogue rule: text_box + locked (or explicit in_dialogue).
    dialogue_mode = (
        not has_map_play
        and (
            in_dialogue
            or (text_box and input_locked)
            or (text_box and ("dialogue" in screen_l or "text box" in screen_l))
        )
    )
    if dialogue_mode:
        add("dismiss", "DISMISS", "Dismiss dialogue / advance text")
        add("ui_a", "A", "Press A once")
        add("ui_b", "B", "Press B / cancel")
        return moves[:max_moves]

    # Title / start screen: only UI buttons; no END_TURN / map tactics.
    phase = (state.get("phase") or "").lower()
    if phase == "start_screen":
        add("ui_start", "START", "Press Start to begin / advance title")
        add("ui_a", "A", "Press A to confirm / advance")
        add("ui_b", "B", "Press B / cancel")
        return moves[:max_moves]

    # Action / map menus
    if in_menu:
        for opp in (state.get("attack_opportunities") or [])[:6]:
            target = opp.get("target") or "Enemy"
            add("attack", f'ATTACK target="{target}"', f"Attack {target}")
        add("wait", "WAIT", "Wait (end this unit's turn)")
        add("ui_a", "A", "Confirm highlighted menu option")
        add("ui_b", "B", "Cancel / leave menu")
        if "seize" in screen_l:
            add("seize", "SEIZE", "Seize objective")
        return moves[:max_moves]

    available = _available_units(state)
    selected = state.get("selected_unit") or state.get("cursor_on_player")
    unit_selected = bool(
        state.get("unit_is_selected")
        or state.get("movement_tiles")
        or (selected and state.get("cursor_on_player") and not state.get("cursor_on_player_moved"))
    )
    movement = [_tile(t) for t in (state.get("movement_tiles") or [])]
    movement = [t for t in movement if t]
    movement_set = set(movement)
    attack_opps = state.get("attack_opportunities") or []
    enemies = state.get("enemies") or []

    # --- Selected unit: attack + move options ---
    if unit_selected and selected:
        for opp in attack_opps[:10]:
            dest = _tile(opp.get("move_to") or opp.get("tile"))
            target = opp.get("target") or "Enemy"
            if not dest:
                continue
            x, y = dest
            add(
                "move_attack",
                f'SELECT unit="{selected}" MOVE to=[{x},{y}] ATTACK target="{target}"',
                f"{selected} → ({x},{y}) attack {target}",
            )

        # Sample wait destinations (near enemies first)
        enemy_tiles = []
        for e in enemies:
            p = _tile([e.get("x"), e.get("y")])
            if p:
                enemy_tiles.append(p)

        def nearness(tile: Tuple[int, int]) -> Tuple[int, int, int]:
            if enemy_tiles:
                d = min(abs(tile[0] - ex) + abs(tile[1] - ey) for ex, ey in enemy_tiles)
            else:
                d = 50
            return (d, tile[0], tile[1])

        ranked = sorted(movement_set, key=nearness)
        cursor = _tile(state.get("cursor") or state.get("display_cursor"))
        if cursor and cursor in movement_set:
            add(
                "move_wait",
                f'SELECT unit="{selected}" MOVE to=[{cursor[0]},{cursor[1]}] WAIT',
                f"{selected} wait at ({cursor[0]},{cursor[1]})",
            )
        for tile in ranked[:14]:
            x, y = tile
            # Skip tiles already covered by attack_opps
            if any(
                _tile(o.get("move_to") or o.get("tile")) == tile
                for o in attack_opps
            ):
                continue
            add(
                "move_wait",
                f'SELECT unit="{selected}" MOVE to=[{x},{y}] WAIT',
                f"{selected} → ({x},{y}) wait",
            )

    # --- Not selected: select available units ---
    if not unit_selected:
        for u in available[:12]:
            name = u.get("name")
            if not name:
                continue
            add(
                "select",
                f'SELECT unit="{name}"',
                f"Select {name} ({u.get('x')},{u.get('y')})",
            )

    if not available:
        add("end_turn", "END_TURN", "End player phase — all units acted")
    else:
        # Escape hatch so the model can finish the turn deliberately
        add("end_turn", "END_TURN", "End player phase early")

    add("ui_b", "B", "Cancel / deselect")
    return moves[:max_moves]


def resolve_move_id(move_id: str, legal_moves: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not move_id:
        return None
    key = str(move_id).strip().lower()
    for m in legal_moves or []:
        if str(m.get("id", "")).lower() == key:
            return m
    return None


def legal_moves_for_prompt(moves: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Compact list for the model (id + summary + kind)."""
    return [
        {"id": m["id"], "kind": m["kind"], "summary": m["summary"]}
        for m in moves
    ]
