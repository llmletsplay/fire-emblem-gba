"""
Command Executor for Fire Emblem GBA AI Agent.

Translates validated semantic commands into deterministic button sequences.
Uses actual game state from memory to calculate paths, eliminating LLM hallucinations.

The executor receives:
  - CommandSequence with validated Command objects
  - Current game state from memory (cursor position, unit positions, etc.)

And produces:
  - Button sequence string like "LEFT;LEFT;UP;A;" to send to the emulator
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from src.game.command_parser import Command, CommandSequence
from src.game.command_validator import ValidationResult, manhattan_distance
from src.game.button_mapping import BUTTONS, normalize_button

log = logging.getLogger(__name__)

# Menu indices for common action menu options (vertical list)
# Standard Fire Emblem action menu after moving:
# 0: Attack
# 1: Wait
# 2: Item
# 3: Trade (if applicable)
# 4: Rescue (if applicable)
# 5: Dismiss
ACTION_MENU_INDICES = {
    "attack": 0,
    "wait": 1,
    "item": 2,
    "trade": 3,
    "rescue": 4,
    "dismiss": 5,
}

# Unit action menu (Rescue/Item/Trade/Wait) - appears when pressing A on unit
# These are indices in the vertical menu: Rescue(0), Item(1), Trade(2), Wait(3)
UNIT_ACTION_MENU = {
    "rescue": 0,
    "item": 1,
    "trade": 2,
    "wait": 3,
}

# Attack menu (after selecting attack from action menu)
# Options: Attack(0), Wait(1) - appears when adjacent to enemy
ATTACK_MENU = {
    "attack": 0,
    "wait": 1,
}


def calculate_menu_navigation(current_selection: int, target_index: int) -> List[str]:
    """Calculate D-pad presses needed to navigate from current selection to target.
    
    Args:
        current_selection: Current menu cursor position (0 = top)
        target_index: Desired menu item index
        
    Returns:
        List of button strings (["D", "D"] for down twice)
    """
    if current_selection < 0 or target_index < 0:
        return []
    
    diff = target_index - current_selection
    if diff == 0:
        return []  # Already on target
    
    buttons = []
    if diff > 0:
        buttons = [BUTTONS["DOWN"]] * diff
    elif diff < 0:
        buttons = [BUTTONS["UP"]] * (-diff)
    
    log.info(f"Menu navigation: from {current_selection} to {target_index} = {buttons}")
    return buttons


def calculate_path(cursor: Tuple[int, int], target: Tuple[int, int]) -> List[str]:
    """Calculate button presses to navigate from cursor to target.

    Uses simple Manhattan pathfinding: move horizontally, then vertically.
    This matches how Fire Emblem cursor movement works.

    Args:
        cursor: (x, y) current cursor position from memory
        target: (x, y) destination position

    Returns:
        List of button presses ["L", "L", "U", "D", ...]
    """
    cx, cy = cursor
    tx, ty = target
    buttons = []

    dx = tx - cx
    dy = ty - cy

    if dx < 0:
        buttons.extend([BUTTONS["LEFT"]] * (-dx))
    elif dx > 0:
        buttons.extend([BUTTONS["RIGHT"]] * dx)

    if dy < 0:
        buttons.extend([BUTTONS["UP"]] * (-dy))
    elif dy > 0:
        buttons.extend([BUTTONS["DOWN"]] * dy)

    return buttons


def calculate_unit_menu_sequence(unit_name: Optional[str], party: List[Dict]) -> List[str]:
    """Calculate button presses to open Unit menu and select a unit.

    Sequence:
    1. Press A on empty tile → opens map menu
    2. Navigate to "Unit" option → press A
    3. Navigate to unit name in list → press A
    4. Press A again to select unit for movement

    Note: The Unit menu places cursor on unit but doesn't select them.
    Must press A one more time to confirm selection.

    Args:
        unit_name: Name of the unit to select
        party: List of unit dicts with name, x, y, hasMoved fields

    Returns:
        Complete button sequence for selecting the unit
    """
    if not unit_name:
        log.warning("calculate_unit_menu_sequence called with empty unit_name")
        return ["A"]  # Press A on current tile as fallback

    buttons = []

    # Step 1: Open map menu (A on empty tile - assume current position is empty or we're cancelling)
    buttons.append("A")

    # Step 2: Navigate to "Unit" option
    # Map menu options: Unit, Attack, Item, Save, etc. - Unit is usually first
    buttons.append("A")  # Select "Unit"

    # Step 3: Navigate to unit in the list and select
    # Unit list: sorted alphabetically, grayed out = already moved
    # We need to find the unit's position in the list
    unit_list = sorted([u["name"] for u in party if not u.get("hasMoved", False)])

    if not unit_list:
        # No unmoved units - try including moved ones
        unit_list = sorted([u["name"] for u in party])

    if unit_list:
        try:
            unit_idx = unit_list.index(unit_name)
        except ValueError:
            log.warning(f"Unit '{unit_name}' not found in unit list: {unit_list}")
            unit_idx = 0  # Default to first unit

        # Navigate down to the unit (0 down presses for first unit)
        buttons.extend([BUTTONS["DOWN"]] * unit_idx)
        buttons.append("A")  # Select the unit from list

    # Step 4: The unit is now under cursor but NOT selected yet
    # Must press A again to actually select for movement
    buttons.append("A")

    return buttons


def calculate_direction_to_target(cursor: Tuple[int, int], target: Tuple[int, int]) -> str:
    """Get cardinal direction from cursor to target position."""
    cx, cy = cursor
    tx, ty = target

    dx = tx - cx
    dy = ty - cy

    if abs(dx) > abs(dy):
        return "RIGHT" if dx > 0 else "LEFT"
    else:
        return "DOWN" if dy > 0 else "UP"


def _name_match_score(entity: Dict, name: str) -> int:
    """Score how well an entity matches a target name/id. Higher is better."""
    if not name:
        return 0
    needle = str(name).strip().lower()
    ename = str(entity.get("name") or "").strip().lower()
    eid = entity.get("id")
    eid_s = str(eid).lower() if eid is not None else ""
    # Exact name
    if ename and ename == needle:
        return 100
    # Hex/id forms: "0x3e", "unit 0x3e", "62"
    needle_hex = needle.replace("unit ", "").replace("unit_", "").strip()
    if needle_hex.startswith("0x"):
        try:
            want = int(needle_hex, 16)
            if eid is not None and int(eid) == want:
                return 95
            if ename.endswith(needle_hex) or needle_hex in ename:
                return 90
        except ValueError:
            pass
    else:
        try:
            want = int(needle_hex)
            if eid is not None and int(eid) == want:
                return 95
        except ValueError:
            pass
    if eid_s and (eid_s == needle or eid_s == needle_hex):
        return 92
    # Prefer exact token containment over weak substring
    if ename and needle == ename:
        return 100
    if ename and (ename.startswith(needle) or needle.startswith(ename)) and min(len(ename), len(needle)) >= 4:
        return 70
    # Weak substring — keep low so adjacency/cursor can override duplicates
    if ename and needle in ename and len(needle) >= 4:
        return 40
    if ename and ename in needle and len(ename) >= 4:
        return 35
    return 0


def get_enemy_by_name(
    enemies: List[Dict],
    name: str,
    cursor: Optional[Tuple[int, int]] = None,
) -> Optional[Dict]:
    """Find enemy by exact/id match; break ties by proximity to cursor."""
    if not enemies or not name:
        return None
    scored = []
    for e in enemies:
        score = _name_match_score(e, name)
        if score <= 0:
            continue
        ex, ey = int(e.get("x", 0) or 0), int(e.get("y", 0) or 0)
        dist = 10**9
        if cursor is not None:
            dist = abs(ex - cursor[0]) + abs(ey - cursor[1])
        scored.append((score, dist, e))
    if not scored:
        return None
    scored.sort(key=lambda t: (-t[0], t[1]))
    best = scored[0]
    if cursor is not None and best[0] < 90:
        adjacent = [t for t in scored if t[1] == 1]
        if adjacent:
            adjacent.sort(key=lambda t: (-t[0], t[1]))
            return adjacent[0][2]
    return best[2]


def resolve_attack_target_tile(
    game_state: Dict[str, Any],
    target_name: Optional[str],
    cursor: Tuple[int, int],
):
    """Prefer attack_opportunities at cursor, else adjacent name match, else raw xy."""
    enemies = game_state.get("enemies", []) or []
    opps = game_state.get("attack_opportunities", []) or []
    cx, cy = cursor

    def _opp_target_name(opp):
        return str(opp.get("target") or opp.get("enemy") or opp.get("name") or "")

    def _opp_enemy_at(opp):
        ea = opp.get("enemy_at") or opp.get("enemy_pos") or opp.get("target_pos") or opp.get("at")
        if isinstance(ea, (list, tuple)) and len(ea) >= 2:
            return int(ea[0]), int(ea[1])
        return None

    def _opp_move_to(opp):
        mt = opp.get("move_to") or opp.get("from") or opp.get("tile") or opp.get("move_tile")
        if isinstance(mt, (list, tuple)) and len(mt) >= 2:
            return int(mt[0]), int(mt[1])
        return None

    matching = []
    for opp in opps:
        mt = _opp_move_to(opp)
        if mt != (cx, cy):
            continue
        if target_name:
            if _name_match_score({"name": _opp_target_name(opp), "id": opp.get("target_id")}, target_name) <= 0:
                ea = _opp_enemy_at(opp)
                if ea is None:
                    continue
                hit = any(
                    _name_match_score(e, target_name) > 0 and (int(e.get("x", -1)), int(e.get("y", -1))) == ea
                    for e in enemies
                )
                if not hit:
                    continue
        ea = _opp_enemy_at(opp)
        if ea:
            matching.append((opp, ea))
    if matching:
        opp, ea = matching[0]
        enemy = next((e for e in enemies if (int(e.get("x", -1)), int(e.get("y", -1))) == ea), None)
        if enemy is None and target_name:
            enemy = get_enemy_by_name(enemies, target_name, cursor=cursor)
        return ea, "attack_opportunities", enemy

    if target_name:
        adjacent = []
        for e in enemies:
            if _name_match_score(e, target_name) <= 0:
                continue
            ex, ey = int(e.get("x", 0) or 0), int(e.get("y", 0) or 0)
            if abs(ex - cx) + abs(ey - cy) == 1:
                adjacent.append((e, (ex, ey)))
        if adjacent:
            adjacent.sort(key=lambda t: -_name_match_score(t[0], target_name))
            e, tile = adjacent[0]
            return tile, "adjacent_to_cursor", e
        enemy = get_enemy_by_name(enemies, target_name, cursor=cursor)
        if enemy:
            tile = (int(enemy.get("x", 0) or 0), int(enemy.get("y", 0) or 0))
            return tile, "raw", enemy

    for opp in opps:
        if _opp_move_to(opp) == (cx, cy):
            ea = _opp_enemy_at(opp)
            if ea:
                return ea, "attack_opportunities", None
    for e in enemies:
        ex, ey = int(e.get("x", 0) or 0), int(e.get("y", 0) or 0)
        if abs(ex - cx) + abs(ey - cy) == 1:
            return (ex, ey), "adjacent_to_cursor", e
    return None, "unresolved", None


def execute_command_sequence(
    commands: List[Command],
    game_state: Dict[str, Any],
) -> Tuple[str, str]:
    """Execute a command sequence and return button string + action description.

    Args:
        commands: Validated command objects to execute
        game_state: Current game state with cursor, units, etc.

    Returns:
        Tuple of (button_sequence, action_description)
        button_sequence: String like "L;L;U;A;" to send to emulator
        action_description: Human-readable description for logging
    """
    if not commands:
        return "", "No commands to execute"

    # Auto-detect and handle dialogue advancement
    # If text_box_visible or in_dialogue, we should advance dialogue instead of executing other commands
    text_box_visible = game_state.get("text_box_visible", False)
    in_dialogue = game_state.get("in_dialogue", False)
    input_locked = game_state.get("input_locked", False)
    
    if (text_box_visible or in_dialogue) and input_locked:
        # Dialogue is active - auto-inject A to advance, ignoring other commands
        log.info("Dialogue detected - auto-advancing with A")
        return "A;", "DIALOGUE_ADVANCE (auto-injected)"

    phase = (game_state.get("phase") or "unknown")
    phase_l = str(phase).lower()
    if phase_l == "start_screen":
        # Title / chapter splash — Start then A are the usual clears
        log.info("start_screen detected - auto-advancing with START;A")
        return "START;A;", "START_SCREEN_ADVANCE (auto-injected)"
    
    # Phase validation - check if commands are valid for current phase
    player_actions = {"SELECT", "MOVE", "ATTACK", "WAIT", "SEIZE", "VISIT", "TALK", "TRADE", "RESCUE", "ITEM", "DISMISS", "END_TURN"}
    
    if phase in ("enemy_phase", "npc_phase"):
        # During enemy/npc phase, only B button or waiting is valid
        cmd_types = {cmd.type for cmd in commands}
        non_player_actions = cmd_types - {"BUTTON", "PRESS"}
        
        if non_player_actions:
            log.warning(f"Phase is {phase}, ignoring player actions: {non_player_actions}. Auto-waiting.")
            return "", f"BLOCKED: Cannot execute {non_player_actions} during {phase} - auto-waiting"

    # Live FE7 on mGBA: PlaySt cursor often freezes while BmSt display_cursor
    # tracks the real on-screen cursor (opposite of the old tutorial comment).
    # Prefer display / overridden context cursor for pathing; keep PlaySt only
    # as a fallback when display is missing.
    display_cursor = game_state.get("display_cursor")
    context_cursor = game_state.get("cursor")
    playst_cursor = game_state.get("cursor_memory")
    cursor = display_cursor or context_cursor or playst_cursor or (0, 0)
    if isinstance(cursor, list):
        cursor = tuple(cursor)
    nav_cursor = (int(cursor[0]), int(cursor[1]))
    log.info(
        f"Nav cursor={nav_cursor} (display={display_cursor}, "
        f"context={context_cursor}, playst={playst_cursor})"
    )
    cursor_on_player = game_state.get("cursor_on_player")
    party = game_state.get("party", [])
    enemies = game_state.get("enemies", [])
    movement_tiles = game_state.get("movement_tiles", [])

    button_sequence = []
    action_descriptions = []

    def _party_unit_pos(name: str):
        for u in party:
            if str(u.get("name") or "").lower() == name.lower():
                try:
                    return (int(u["x"]), int(u["y"]))
                except (KeyError, TypeError, ValueError):
                    return None
        return None

    for cmd in commands:
        cmd_desc = ""

        if cmd.type == "SELECT":
            unit_name = cmd.unit
            if not unit_name:
                log.warning("SELECT command with no unit name, skipping")
                continue
            unit_pos = _party_unit_pos(unit_name)
            # Only bare-A when the PATHING cursor is actually on the unit.
            # cursor_on_player can be true from a stale display_cursor override.
            on_unit = bool(unit_pos and nav_cursor == unit_pos)
            if on_unit:
                log.info(
                    f"Pathing cursor already on {unit_name} at {nav_cursor}, pressing A once"
                )
                button_sequence.append("A")
                cmd_desc = f"SELECT {unit_name}"
            else:
                use_map = False
                if unit_pos and nav_cursor:
                    dist = abs(nav_cursor[0] - unit_pos[0]) + abs(nav_cursor[1] - unit_pos[1])
                    if dist <= 12:
                        use_map = True
                if use_map:
                    seq = calculate_map_to_unit_buttons(unit_name, party, nav_cursor)
                    button_sequence.extend(seq)
                    cmd_desc = f"SELECT {unit_name} (via map path)"
                    log.info(
                        f"SELECT map path {nav_cursor}→{unit_pos} {unit_name}: {seq}"
                    )
                    nav_cursor = unit_pos
                else:
                    seq = calculate_l_button_cycling_buttons(
                        unit_name, party, cursor_on_player, game_state
                    )
                    button_sequence.extend(seq)
                    cmd_desc = f"SELECT {unit_name} (via L-button)"
                    log.info(f"SELECT L-cycle sequence: {seq}")
                    if unit_pos:
                        nav_cursor = unit_pos

        elif cmd.type == "MOVE":
            target = cmd.coord
            if target:
                tx, ty = target

                # Validate against movement_tiles - if not valid, find nearest valid
                if movement_tiles:
                    valid_set = set(tuple(t) for t in movement_tiles)
                    if (tx, ty) not in valid_set:
                        # Find nearest valid tile
                        nearest = None
                        nearest_dist = float('inf')
                        for vt in movement_tiles:
                            dist = abs(vt[0] - tx) + abs(vt[1] - ty)
                            if dist < nearest_dist:
                                nearest_dist = dist
                                nearest = (vt[0], vt[1])
                        if nearest:
                            log.info(f"Tile {target} not valid, auto-correcting to nearest {nearest}")
                            tx, ty = nearest
                            target = nearest

                path = calculate_path(nav_cursor, target)
                button_sequence.extend(path)
                button_sequence.append("A")  # Confirm move
                nav_cursor = (int(tx), int(ty))
                cursor = target  # Update cursor position
                cmd_desc = f"MOVE to {target}"
                log.info(f"MOVE path: {path} → {target}")

        elif cmd.type == "ATTACK":
            target_name = cmd.target
            direction = cmd.target if cmd.target in {"north", "south", "east", "west"} else None

            if direction:
                dir_btn = BUTTONS.get(direction.upper())
                if dir_btn:
                    button_sequence.append(dir_btn)
                    button_sequence.append("A")  # Confirm direction
                    cmd_desc = f"ATTACK {direction}"
                    log.info(f"ATTACK direction: {direction}")
                else:
                    cmd_desc = f"ATTACK {direction} (invalid direction)"
            else:
                # Check what menu type we're in to determine correct navigation
                menu_type = game_state.get("menu_type", "")
                current_menu_sel = game_state.get("menu_selection", -1)
                
                if menu_type == "attack":
                    # We're in attack menu (Attack/Wait) - navigate to Attack option
                    nav_buttons = calculate_menu_navigation(current_menu_sel, ATTACK_MENU["attack"])
                    button_sequence.extend(nav_buttons)
                    button_sequence.append("A")  # Confirm Attack
                    cmd_desc = "ATTACK (from attack menu)"
                    log.info(f"ATTACK: in attack menu, navigating to Attack")
                else:
                    # We're in unit action menu - select Attack (index 0)
                    # But first check if we need to navigate to Attack option
                    if current_menu_sel >= 0 and current_menu_sel != 0:
                        nav_buttons = calculate_menu_navigation(current_menu_sel, 0)
                        button_sequence.extend(nav_buttons)
                    button_sequence.append("A")  # Select Attack from menu
                    
                    if target_name:
                        tile, src, enemy = resolve_attack_target_tile(game_state, target_name, cursor)
                        if tile:
                            ex, ey = tile
                            dir_btn = calculate_direction_to_target(cursor, (ex, ey))
                            button_sequence.append(BUTTONS.get(dir_btn, "A"))
                            button_sequence.append("A")  # Confirm target
                            cmd_desc = f"ATTACK {target_name}"
                            log.info(
                                f"ATTACK target: {target_name} from-cursor={cursor} to-tile={tile} source={src}"
                            )
                        else:
                            cmd_desc = f"ATTACK {target_name} (target not found)"
                    else:
                        button_sequence.append("A")  # Confirm attack
                        cmd_desc = "ATTACK (no target specified)"

        elif cmd.type == "WAIT":
            # Check if we're in a menu and navigate to Wait (index 3)
            current_menu_sel = game_state.get("menu_selection", -1)
            if current_menu_sel >= 0:
                # Calculate navigation from current position to Wait (index 3)
                nav_buttons = calculate_menu_navigation(current_menu_sel, UNIT_ACTION_MENU["wait"])
                button_sequence.extend(nav_buttons)
            else:
                # Fallback: navigate to Wait (index 3 in Rescue/Item/Trade/Wait menu)
                button_sequence.extend([BUTTONS["DOWN"], BUTTONS["DOWN"]])  # 0->1->2->3 = 3 downs from Rescue
            button_sequence.append("A")  # Confirm Wait
            cmd_desc = "WAIT"

        elif cmd.type == "SEIZE":
            # Navigate to Seize option (typically at bottom of action menu)
            # Check menu_type to see if we're in appropriate menu
            menu_type = game_state.get("menu_type", "")
            current_menu_sel = game_state.get("menu_selection", -1)
            
            if menu_type in ("unit", "action"):
                # In unit action menu - navigate to Seize
                # Seize is typically after Attack/Wait, depends on game/chapter
                # For now, navigate to index 4 (after Attack/Wait/Item/Trade/Rescue)
                if current_menu_sel >= 0 and current_menu_sel != 4:
                    nav_buttons = calculate_menu_navigation(current_menu_sel, 4)
                    button_sequence.extend(nav_buttons)
            button_sequence.append("A")  # Confirm Seize
            button_sequence.append("A")  # Final confirm
            cmd_desc = "SEIZE"

        elif cmd.type == "END_TURN":
            button_sequence.append("Select")
            cmd_desc = "END_TURN"

        elif cmd.type == "DISMISS":
            # Navigate to Dismiss option in menu
            menu_type = game_state.get("menu_type", "")
            current_menu_sel = game_state.get("menu_selection", -1)
            
            if menu_type in ("unit", "action"):
                if current_menu_sel >= 0 and current_menu_sel != 5:
                    nav_buttons = calculate_menu_navigation(current_menu_sel, 5)
                    button_sequence.extend(nav_buttons)
            button_sequence.append("A")
            cmd_desc = "DISMISS"

        elif cmd.type == "BUTTON":
            # Single button command (A, B, etc.)
            btn = cmd.button
            if btn:
                button_sequence.append(btn)
                cmd_desc = f"BUTTON {btn}"
                log.info(f"Single button: {btn}")

        elif cmd.type == "TALK":
            target_name = cmd.target
            enemy = get_enemy_by_name(enemies, target_name) if target_name else None
            if enemy:
                ex, ey = enemy.get("x", 0), enemy.get("y", 0)
                dir_btn = calculate_direction_to_target(cursor, (ex, ey))
                button_sequence.append(BUTTONS.get(dir_btn, "A"))
                button_sequence.append("A")  # Select to talk
                cmd_desc = f"TALK {target_name}"
            else:
                button_sequence.append("A")
                cmd_desc = f"TALK (target not found)"

        elif cmd.type == "VISIT":
            # Navigate to Visit option in menu (village/treasure)
            menu_type = game_state.get("menu_type", "")
            current_menu_sel = game_state.get("menu_selection", -1)
            
            if menu_type in ("unit", "action"):
                # Visit is typically an option in the action menu
                # Navigate to appropriate index (usually 3-4 depending on game)
                if current_menu_sel >= 0:
                    nav_buttons = calculate_menu_navigation(current_menu_sel, 3)
                    button_sequence.extend(nav_buttons)
            button_sequence.append("A")
            cmd_desc = "VISIT"

        elif cmd.type == "TRADE":
            # Navigate to Trade (index 2) in action menu
            current_menu_sel = game_state.get("menu_selection", -1)
            if current_menu_sel >= 0:
                nav_buttons = calculate_menu_navigation(current_menu_sel, UNIT_ACTION_MENU["trade"])
                button_sequence.extend(nav_buttons)
            else:
                button_sequence.extend([BUTTONS["DOWN"], BUTTONS["DOWN"]])  # 0->1->2 = 2 downs from Rescue
            button_sequence.append("A")  # Confirm
            cmd_desc = f"TRADE {cmd.target if cmd.target else ''}"

        elif cmd.type == "RESCUE":
            # Navigate to Rescue (index 0) - usually first, but handle anyway
            current_menu_sel = game_state.get("menu_selection", -1)
            if current_menu_sel >= 0:
                nav_buttons = calculate_menu_navigation(current_menu_sel, UNIT_ACTION_MENU["rescue"])
                button_sequence.extend(nav_buttons)
            # Rescue is typically index 0, so usually no navigation needed
            button_sequence.append("A")  # Confirm
            cmd_desc = f"RESCUE {cmd.target if cmd.target else ''}"

        elif cmd.type == "DROP":
            # When cursor is on a rescued unit and you press A, you get a menu:
            # "Drop", "Item", "Trade", "Wait" - Drop is at index 0
            # First A selects "Drop", then navigate to position if needed, then A to confirm
            button_sequence.append("A")  # Select "Drop" option (first in menu)
            if cmd.coord:
                path = calculate_path(cursor, cmd.coord)
                button_sequence.extend(path)
                button_sequence.append("A")  # Confirm drop location
                cursor = cmd.coord
            cmd_desc = f"DROP at {cmd.coord if cmd.coord else 'current position'}"

        elif cmd.type == "ITEM":
            # Navigate to Item (index 1) in action menu
            current_menu_sel = game_state.get("menu_selection", -1)
            if current_menu_sel >= 0:
                nav_buttons = calculate_menu_navigation(current_menu_sel, UNIT_ACTION_MENU["item"])
                button_sequence.extend(nav_buttons)
            else:
                button_sequence.append(BUTTONS["DOWN"])  # 0->1 = 1 down from Rescue
            if cmd.menu_option:
                button_sequence.append("A")
            cmd_desc = f"ITEM {cmd.menu_option if cmd.menu_option else ''}"

        elif cmd.type == "PRESS":
            if cmd.raw:
                raw = cmd.raw.replace(";", ";").rstrip(";").rstrip(";")
                for btn in raw.split(";"):
                    btn = btn.strip()
                    if btn:
                        button_sequence.append(btn)
            cmd_desc = f"PRESS {cmd.raw}"

        if cmd_desc:
            action_descriptions.append(cmd_desc)

    # Format button sequence with semicolons
    if button_sequence:
        button_str = ";".join(button_sequence) + ";"
    else:
        button_str = ""

    action_desc = " → ".join(action_descriptions) if action_descriptions else "No action"

    log.info(f"Generated button sequence: {button_str}")
    log.info(f"Action description: {action_desc}")

    return button_str, action_desc


def execute_with_validation(
    command_seq: CommandSequence,
    game_state: Dict[str, Any],
) -> Tuple[str, str, bool]:
    """Execute a command sequence with full validation.

    Args:
        command_seq: Parsed command sequence
        game_state: Current game state

    Returns:
        Tuple of (button_sequence, description, success)
    """
    if command_seq.is_empty:
        return "", "No commands", False

    from src.game.command_validator import validate_command_sequence

    result = validate_command_sequence(command_seq.commands, game_state)

    if not result.valid:
        error_msg = " | ".join(result.errors) if result.errors else "Unknown validation error"
        # Log key game state info for debugging validation failures
        phase = game_state.get("phase", "unknown")
        cursor = game_state.get("cursor", "unknown")
        menu = game_state.get("in_menu", False)
        menu_sel = game_state.get("menu_selection", -1)
        log.warning(f"Validation failed: {error_msg} | Phase: {phase}, Cursor: {cursor}, InMenu: {menu}, MenuSel: {menu_sel}")
        if result.corrections:
            log.info(f"Corrections applied: {result.corrections}")
        return "", error_msg, False

    buttons, desc = execute_command_sequence(result.commands, game_state)

    return buttons, desc, bool(buttons)


def check_preconditions(
    action_type: str,
    unit_name: Optional[str],
    game_state: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Check if action preconditions are met.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    unit_status = game_state.get("unit_status", {})
    party = game_state.get("party", [])
    
    if action_type == "SELECT":
        if not unit_name:
            return False, "No unit specified for SELECT"
        
        if unit_name not in unit_status:
            return False, f"Unit '{unit_name}' not found in party"
        
        status = unit_status.get(unit_name, "unknown")
        if status == "already_acted":
            return False, f"Unit '{unit_name}' has already acted this turn (grayed out)"
        elif status == "rescued":
            return False, f"Unit '{unit_name}' is being rescued and cannot act"
        elif status != "available":
            return False, f"Unit '{unit_name}' is not available (status: {status})"
        
        return True, ""
    
    elif action_type == "MOVE":
        # Check if a unit is selected (movement tiles should be present)
        movement_tiles = game_state.get("movement_tiles", [])
        unit_is_selected = game_state.get("unit_is_selected", False)
        
        if not movement_tiles and not unit_is_selected:
            return False, "No unit selected - cannot move. Select a unit first."
        
        return True, ""
    
    elif action_type == "ATTACK":
        attack_opportunities = game_state.get("attack_opportunities", [])
        if not attack_opportunities:
            return False, "No attack opportunities available - move next to an enemy first"
        
        return True, ""
    
    return True, ""


def verify_select_result(
    game_state: Dict[str, Any],
    expected_unit: str,
) -> Tuple[bool, str]:
    """
    Verify that SELECT action succeeded.
    
    Returns:
        Tuple of (success, message)
    """
    movement_tiles = game_state.get("movement_tiles", [])
    unit_is_selected = game_state.get("unit_is_selected", False)
    cursor_on_player = game_state.get("cursor_on_player")
    
    if movement_tiles or unit_is_selected:
        return True, f"Unit '{expected_unit}' selected successfully"
    
    if cursor_on_player and cursor_on_player.lower() == expected_unit.lower():
        return True, f"Cursor on '{cursor_on_player}' but movement tiles not detected"
    
    return False, f"SELECT may have failed - no movement tiles detected"


def verify_move_result(
    game_state: Dict[str, Any],
    target: Tuple[int, int],
    unit_name: str,
) -> Tuple[bool, str]:
    """
    Verify that MOVE action succeeded.
    
    Returns:
        Tuple of (success, message)
    """
    cursor = game_state.get("cursor")
    unit_status = game_state.get("unit_status", {})
    
    if cursor and tuple(cursor) == target:
        return True, f"Moved {unit_name} to {target}"
    
    if cursor:
        return False, f"Cursor at {cursor}, expected {target}"
    
    return False, "Could not verify move result"


def calculate_unit_menu_buttons(
    unit_name: str,
    party: List[Dict],
    current_cursor: Optional[Tuple[int, int]] = None,
) -> List[str]:
    """
    Calculate button sequence to select a unit via Unit menu.
    
    Handles different starting states:
    - On map (normal): A → A → navigate → A → A
    - From map menu: navigate to Unit → A → navigate → A → A
    """
    buttons = []
    
    # Find unit position in party list
    party_names = [u.get("name", "") for u in party]
    try:
        unit_idx = party_names.index(unit_name)
    except ValueError:
        # Unit not found - try to find by partial match
        unit_idx = -1
        for i, name in enumerate(party_names):
            if unit_name.lower() in name.lower():
                unit_idx = i
                break
        if unit_idx == -1:
            log.warning(f"Unit '{unit_name}' not found in party")
            return ["A"]  # Fallback
    
    # If we're not already in the Unit menu, we need to open it
    # Start from map: press A to open menu
    buttons.append("A")  # Open map menu
    
    # Navigate to "Unit" (usually first option)
    buttons.append("A")  # Select Unit
    
    # Navigate to unit in list
    if unit_idx > 0:
        buttons.extend([BUTTONS["DOWN"]] * unit_idx)
    
    # Select the unit from list
    buttons.append("A")
    
    # Confirm selection (press A again to enter movement mode)
    buttons.append("A")
    
    return buttons


def calculate_l_button_cycling_buttons(
    target_unit_name: str,
    party: List[Dict],
    current_cursor_on: Optional[str] = None,
    game_state: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Calculate button sequence to select a unit using L-button cycling.
    
    L-button cycles through available (unmoved) units. This is more reliable
    than navigating the unit menu or navigating on the map.
    
    Strategy:
    - If menu is open, close it with B first
    - Press L (left shoulder button) multiple times to cycle through available units
    - Stop when cursor is on target unit
    
    Args:
        target_unit_name: Name of unit to select
        party: List of unit dicts with name, hasMoved fields
        current_cursor_on: Name of unit currently under cursor (if any)
        game_state: Optional game state to check for menu state
    
    Returns:
        Button sequence with B (if needed) + L presses + final A to confirm
    """
    if not target_unit_name:
        log.warning("calculate_l_button_cycling_buttons called with empty target_unit_name")
        return ["A"]
    
    buttons = []
    
    # Check if a menu is open - if so, close it first with B
    in_menu = False
    if game_state:
        in_menu = game_state.get("in_menu", False)
    
    if in_menu:
        log.info("Menu detected open, closing with B first")
        buttons.append("B")
    
    # Get available (unmoved) units in order they appear when pressing L
    available_units = [u.get("name", "") for u in party if not u.get("hasMoved", False)]
    
    if not available_units:
        # No unmoved units - try all units
        available_units = [u.get("name", "") for u in party]
    
    if not available_units:
        log.warning("No units in party for L-button cycling")
        return ["A"]  # Fallback
    
    # If already on target, just press A
    if current_cursor_on and current_cursor_on.lower() == target_unit_name.lower():
        return ["A"]
    
    # Find target index
    try:
        target_idx = next(i for i, name in enumerate(available_units) 
                        if name.lower() == target_unit_name.lower())
    except StopIteration:
        # Unit not found in available - use unit menu instead
        log.warning(f"Unit '{target_unit_name}' not in available units, using menu")
        return calculate_unit_menu_buttons(target_unit_name, party)
    
    # Calculate how many L presses needed
    if current_cursor_on:
        try:
            current_idx = next(i for i, name in enumerate(available_units)
                            if name.lower() == current_cursor_on.lower())
        except StopIteration:
            current_idx = 0
    else:
        current_idx = 0
    
    # L cycles forward through units
    # Calculate presses needed (wrap around with modulo)
    presses_needed = (target_idx - current_idx) % len(available_units)
    
    # Add L (left shoulder) presses to cycle through units
    if presses_needed > 0:
        buttons.extend([BUTTONS["LT"]] * presses_needed)
    
    # Press A to confirm selection
    buttons.append("A")
    
    log.info(f"L-button cycling to {target_unit_name}: {buttons}")
    return buttons


def calculate_map_to_unit_buttons(
    target_unit_name: str,
    party: List[Dict],
    current_cursor: Tuple[int, int],
) -> List[str]:
    """
    Calculate button sequence to navigate directly to a unit on the map.
    
    This is faster than using the Unit menu if the unit is nearby.
    """
    # Find target unit position
    target_unit = None
    for unit in party:
        if unit.get("name", "").lower() == target_unit_name.lower():
            target_unit = unit
            break
    
    if not target_unit:
        return calculate_unit_menu_buttons(target_unit_name, party, current_cursor)
    
    tx, ty = target_unit.get("x", 0), target_unit.get("y", 0)

    # Walk to the unit, then A to select
    buttons = calculate_path(current_cursor, (tx, ty))
    buttons.append("A")
    return buttons


def execute_select_unit(
    unit_name: str,
    game_state: Dict[str, Any],
    max_attempts: int = 5,
) -> Tuple[bool, str, List[str]]:
    """
    Execute SELECT action with retry logic.
    
    Attempts multiple strategies to select a unit:
    1. If cursor already on unit, press A once
    2. Navigate directly to unit on map
    3. Open Unit menu and select from list
    
    Returns:
        Tuple of (success, message, buttons_sent)
    """
    from src.game.actions import ActionResult
    
    party = game_state.get("party", [])
    cursor = game_state.get("cursor", (0, 0))
    cursor_on_player = game_state.get("cursor_on_player")
    unit_status = game_state.get("unit_status", {})
    
    # Check preconditions
    status = unit_status.get(unit_name, "unknown")
    if status != "available":
        return False, f"Unit {unit_name} not available (status: {status})", []
    
    buttons_sent = []
    
    for attempt in range(1, max_attempts + 1):
        log.info(f"SELECT {unit_name} - Attempt {attempt}/{max_attempts}")
        
        # Strategy varies by attempt
        if attempt == 1:
            # First attempt: if cursor on unit, press A
            if cursor_on_player and cursor_on_player.lower() == unit_name.lower():
                buttons = ["A"]
                log.info(f"Cursor already on {unit_name}, pressing A")
            else:
                # Try navigating directly to unit first
                buttons = calculate_map_to_unit_buttons(unit_name, party, cursor)
                log.info(f"Navigating directly to {unit_name}: {buttons}")
        
        elif attempt == 2:
            # Second attempt: if first failed, try Unit menu
            buttons = calculate_unit_menu_buttons(unit_name, party, cursor)
            log.info(f"Using Unit menu for {unit_name}: {buttons}")
        
        elif attempt == 3:
            # Third attempt: cancel any open menu and retry Unit menu
            buttons = ["B"] + calculate_unit_menu_buttons(unit_name, party, cursor)
            log.info(f"Cancelling and retrying Unit menu: {buttons}")
        
        elif attempt == 4:
            # Fourth attempt: try direct navigation again from different approach
            buttons = calculate_map_to_unit_buttons(unit_name, party, cursor)
            log.info(f"Retry direct navigation: {buttons}")
        
        else:
            # Fifth attempt: last resort - try Unit menu with B cancel first
            buttons = ["B", "B"] + calculate_unit_menu_buttons(unit_name, party, cursor)
            log.info(f"Final attempt with double cancel: {buttons}")
        
        buttons_sent.extend(buttons)
        
        # In a real execution, we'd send these buttons and wait for state change
        # For now, return the buttons for the executor to send
        
    return False, f"Failed to select {unit_name} after {max_attempts} attempts", buttons_sent


def execute_move_unit(
    target: Tuple[int, int],
    game_state: Dict[str, Any],
    max_attempts: int = 5,
) -> Tuple[bool, str, List[str]]:
    """
    Execute MOVE action with retry logic.
    
    Returns:
        Tuple of (success, message, buttons_sent)
    """
    movement_tiles = game_state.get("movement_tiles", [])
    cursor = game_state.get("cursor", (0, 0))
    
    # Validate target is in movement range
    valid_tiles = set(tuple(t) for t in movement_tiles)
    if target not in valid_tiles:
        # Find nearest valid tile
        nearest = None
        nearest_dist = float('inf')
        for tile in movement_tiles:
            dist = abs(tile[0] - target[0]) + abs(tile[1] - target[1])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = tuple(tile)
        
        if nearest:
            target = nearest
            log.info(f"Target {target} not valid, using nearest: {nearest}")
        else:
            return False, "No valid movement tiles available", []
    
    buttons_sent = []
    
    for attempt in range(1, max_attempts + 1):
        log.info(f"MOVE to {target} - Attempt {attempt}/{max_attempts}")
        
        # Calculate path to target
        path = calculate_path(cursor, target)
        
        if not path:
            # Already at target
            buttons = ["A"]  # Just confirm
        else:
            buttons = path + ["A"]  # Move then confirm
        
        buttons_sent.extend(buttons)
        return True, f"Moved to {target}", buttons_sent
    
    return False, f"Failed to move after {max_attempts} attempts", buttons_sent