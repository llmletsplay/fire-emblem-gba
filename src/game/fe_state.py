"""
Fire Emblem GBA - Game State Management
Prepares game state from emulator memory for LLM context.
Supports FE7 (Blazing Blade) and FE8 (Sacred Stones) via auto-detection.
"""

import logging
from typing import Dict, Any, Set, Tuple, List
from src.core import config

log = logging.getLogger(__name__)


def _get_weapon_types(lookup):
    """Get the weapon types list from whichever lookup module is active."""
    for attr in ('FE8_WEAPON_TYPES', 'FE7_WEAPON_TYPES'):
        types = getattr(lookup, attr, None)
        if types:
            return types
    return ["Sword", "Lance", "Axe", "Bow", "Staff", "Anima", "Light", "Dark"]


def prep_fe_llm(sock) -> Dict[str, Any]:
    """Prepare Fire Emblem game state for LLM context.

    Auto-detects the running game (FE7/FE8) and uses the correct
    lookup tables and chapter data.
    """
    from src.utils.memory_reader import get_memory_reader
    from src.data import get_lookup_module, get_chapters_module

    reader = get_memory_reader(sock)
    if not reader:
        raise RuntimeError("Could not initialize FE7/FE8 memory reader")

    game_id = reader.game.game_id
    lookup = get_lookup_module(game_id)
    chapters = get_chapters_module(game_id)

    log.debug(f"Using {reader.game.title} memory reader...")
    log.debug("Reading game state...")
    game_state = reader.read_game_state()

    if not game_state:
        log.warning("Game state is None")
        return {"error": "Could not read game state"}

    log.debug(f"Game state: {len(game_state.player_units)} players, "
               f"{len(game_state.enemy_units)} enemies, "
               f"{len(game_state.npc_units)} NPCs")
    log.debug(f"Phase: {game_state.phase}, Chapter: {game_state.chapter}, Turn: {game_state.turn}")

    # Validate game state is sensible
    if game_state.chapter < 0 or game_state.chapter > 50:
        log.warning(f"Invalid chapter number: {game_state.chapter}")
    if game_state.turn < 0 or game_state.turn > 100:
        log.warning(f"Invalid turn number: {game_state.turn}")

    phase = game_state.phase
    cursor_reliable = phase not in ["start_screen", "story", "unknown"]
    
    # Log cursor reliability
    if not cursor_reliable:
        log.debug(f"Cursor not reliable (phase={phase}), skipping navigation hints")
    
    # Validate cursor coordinates
    if game_state.cursor_x < 0 or game_state.cursor_x > 100 or game_state.cursor_y < 0 or game_state.cursor_y > 100:
        log.warning(f"Invalid cursor coordinates: ({game_state.cursor_x}, {game_state.cursor_y})")
        cursor_reliable = False

    context = {
        "game": game_id,
        "game_title": reader.game.title,
        "chapter": game_state.chapter,
        "turn": game_state.turn,
        "phase": phase,
        "player_units": len(game_state.player_units),
        "enemy_units": len(game_state.enemy_units),
        "npc_units": len(game_state.npc_units),
    }

    map_size = reader.read_map_size()
    if map_size:
        context["map_width"] = map_size[0]
        context["map_height"] = map_size[1]

    # Inject chapter objective data for LLM context
    chapter_data = chapters.get_chapter_objective(game_state.chapter)
    if chapter_data:
        context["objective"] = chapter_data["objective"]
        context["objective_type"] = chapter_data["objective_type"]
        if chapter_data.get("boss_name"):
            context["boss_target"] = chapter_data["boss_name"]
        if chapter_data.get("seize_position"):
            context["seize_position"] = chapter_data["seize_position"]
        if chapter_data.get("turn_limit"):
            context["turn_limit"] = chapter_data["turn_limit"]
        if chapter_data.get("notes"):
            context["chapter_notes"] = chapter_data["notes"]

    # Read Battle Map State (camera, lock, display cursor)
    if game_state.input_locked:
        context["input_locked"] = True
    if game_state.camera_x != 0 or game_state.camera_y != 0:
        context["camera"] = (game_state.camera_x, game_state.camera_y)
    if game_state.display_cursor_x >= 0:
        context["display_cursor"] = (game_state.display_cursor_x, game_state.display_cursor_y)

    # Tutorial target from event slots (IWRAM) - only if tutorial mode enabled
    if config.TUTORIAL_MODE and game_state.tutorial_target_x >= 0:
        context["tutorial_target"] = (game_state.tutorial_target_x, game_state.tutorial_target_y)

    # Get tutorial sequence for chapter (all tutorial steps) - only if tutorial mode enabled
    if config.TUTORIAL_MODE and game_state.chapter in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9) and reader.game.game_id == "fe7":
        from src.data import fe7_chapters
        chapter_data = fe7_chapters.get_chapter_objective(game_state.chapter)
        if chapter_data and chapter_data.get("tutorial_sequence"):
            context["tutorial_sequence"] = chapter_data["tutorial_sequence"]

    # Query UI state from Lua (phase-level detection using FE addresses)
    ui_state = "unknown"
    detailed_ui = {"ui_type": "unknown", "phase": None, "menu_selection": -1}
    
    try:
        ui_state = reader.get_ui_state()
        if ui_state is None:
            log.warning(f"Lua get_ui_state() returned None")
            ui_state = "unknown"
    except Exception as e:
        log.warning(f"Failed to query UI state from Lua: {e}")
        ui_state = "unknown"
    
    try:
        detailed_ui = reader.get_detailed_ui_state()
        if detailed_ui is None:
            log.warning(f"Lua get_detailed_ui_state() returned None")
            detailed_ui = {"ui_type": "unknown", "phase": None, "menu_selection": -1}
    except Exception as e:
        log.warning(f"Failed to query detailed UI state from Lua: {e}")
        detailed_ui = {"ui_type": "unknown", "phase": None, "menu_selection": -1}
    context["ui_state"] = ui_state

    # Expose detailed menu state for item selection etc.
    # Action menu options for FE7: Rescue, Item, Trade, Wait (indices 0-3)
    ACTION_MENU_OPTIONS = ["Rescue", "Item", "Trade", "Wait"]
    
    if detailed_ui["ui_type"] == "menu":
        context["in_menu"] = True
        context["menu_selection"] = detailed_ui["menu_selection"]
        if detailed_ui.get("menu_type"):
            context["menu_type"] = detailed_ui["menu_type"]
        
        # For unit action menu, expose the options and current selection
        menu_sel = detailed_ui["menu_selection"]
        if detailed_ui.get("menu_type") == "unit" and menu_sel >= 0:
            context["menu_options"] = ACTION_MENU_OPTIONS
            context["menu_selection_label"] = ACTION_MENU_OPTIONS[menu_sel] if menu_sel < len(ACTION_MENU_OPTIONS) else "Unknown"
            log.info(f"Action menu: selection={menu_sel} ({context['menu_selection_label']}) of {ACTION_MENU_OPTIONS}")
    if detailed_ui["ui_type"] == "battle":
        context["in_battle"] = True
    if detailed_ui["ui_type"] == "dialogue":
        context["in_dialogue"] = True

    # FE7-specific: During cutscenes/dialogue, phase may still read as player_phase
    # Check multiple indicators: input_locked + dialogue flag + text box visibility
    fe7_mode = reader.game.game_id == "fe7"
    if fe7_mode and game_state.input_locked:
        log.debug(f"FE7 detection: input_locked=True, phase={phase}, detailed_ui_type={detailed_ui.get('ui_type')}")
        # If locked but phase says player_phase, likely in tutorial dialogue
        if phase == "player_phase" and detailed_ui.get("ui_type") in ("dialogue", "unknown"):
            log.debug("FE7: Detected tutorial dialogue (input_locked but phase=player_phase)")
            context["in_dialogue"] = True

    # For FE7 chapters 0-9 (tutorial), BmSt lock is a strong indicator of dialogue/tutorial
    if fe7_mode and config.TUTORIAL_MODE and game_state.chapter in range(10):
        if game_state.input_locked:
            log.debug(f"FE7 tutorial chapter {game_state.chapter}: input_locked indicates active dialogue/tutorial")
        if game_state.game_state_bits != 0:
            log.debug(f"FE7 tutorial chapter {game_state.chapter}: game_state_bits=0x{game_state.game_state_bits:08X}")

    # Turn/phase change detection
    if game_state.turn_changed:
        context["turn_changed"] = True
    if game_state.phase_changed:
        context["phase_changed"] = True

    # Terrain at cursor position
    terrain_at_cursor = reader.read_terrain(game_state.cursor_x, game_state.cursor_y)
    if terrain_at_cursor:
        context["terrain_at_cursor"] = terrain_at_cursor

    # Deterministic unit status summary: ground-truth from memory, not heuristics.
    # Gives the LLM an authoritative view of who can still act this turn.
    unit_status = {}
    unmoved_count = 0
    for unit in game_state.player_units:
        if not unit.is_alive or unit.current_hp <= 0:
            continue
        name = lookup.get_character_name(unit.char_id)
        if unit.has_moved:
            unit_status[name] = "already_acted"
        elif unit.is_rescued:
            unit_status[name] = "rescued"
        else:
            unit_status[name] = "available"
            unmoved_count += 1
    if unit_status:
        context["unit_status"] = unit_status
        context["unmoved_count"] = unmoved_count
        log.debug(f"unit_status: {unit_status}, unmoved_count: {unmoved_count}")

    # Expose BmSt game state bits and taken_action for downstream inference
    if game_state.game_state_bits != 0:
        context["game_state_bits"] = game_state.game_state_bits
    if game_state.taken_action != 0:
        context["taken_action"] = game_state.taken_action

    # Detect if cursor is on a player unit - MUST happen AFTER cursor override logic
    # This ensures we use display_cursor (not stale PlaySt cursor) for accurate unit detection
    if cursor_reliable:
        # Use the same cursor position logic as navigation
        cx, cy = game_state.cursor_x, game_state.cursor_y

        # Prefer BmSt display_cursor when it differs from PlaySt cursor.
        # During tutorials and unit movement, PlaySt cursor freezes at the
        # unit's original position while display_cursor tracks the real
        # on-screen cursor.  Using the stale value produces wrong navigation.
        if game_state.display_cursor_x >= 0:
            dcx, dcy = game_state.display_cursor_x, game_state.display_cursor_y
            if (dcx, dcy) != (cx, cy):
                log.info(f"Cursor override: PlaySt ({cx},{cy}) → display ({dcx},{dcy})")
                context["cursor_memory"] = (cx, cy)  # keep stale value for reference
                cx, cy = dcx, dcy

        context["cursor"] = (cx, cy)

        # Now detect which unit is at the CORRECT cursor position (display cursor)
        # Use cx, cy which already has the overridden display cursor position
        cursor_unit = None
        for unit in game_state.player_units:
            if unit.is_alive and unit.x == cx and unit.y == cy:
                cursor_unit = unit
                break
        
        if cursor_unit:
            context["cursor_on_player"] = lookup.get_character_name(cursor_unit.char_id)
            context["cursor_on_player_moved"] = cursor_unit.has_moved
            log.info(f"Cursor on player: {context['cursor_on_player']} at ({cx},{cy}), hasMoved={cursor_unit.has_moved}")
            
            # Calculate movement tiles using memory-based calculator
            if not cursor_unit.has_moved:
                try:
                    from src.utils.movement_calculator import get_unit_movement, calculate_movement_tiles
                    
                    # Get unit's class and movement
                    class_name = lookup.get_class_name(cursor_unit.class_id) if hasattr(cursor_unit, 'class_id') else "Fighter"
                    # Extract base class name (remove gender suffix if present)
                    base_class = class_name.split(" (")[0] if "(" in class_name else class_name
                    
                    movement = get_unit_movement(base_class, cursor_unit.mov_bonus)
                    
                    # Get occupied tiles (all units except current one)
                    occupied: Set[Tuple[int, int]] = set()
                    for u in game_state.player_units + game_state.enemy_units + game_state.npc_units:
                        if u.is_alive and u.current_hp > 0 and (u.x, u.y) != (cx, cy):
                            occupied.add((u.x, u.y))
                    
                    movement_map_size = map_size or (16, 16)

                    # Calculate reachable tiles
                    reachable = calculate_movement_tiles(
                        unit_x=cx,
                        unit_y=cy,
                        movement=movement,
                        map_width=movement_map_size[0],
                        map_height=movement_map_size[1],
                        occupied_tiles=occupied,
                    )
                    
                    if reachable:
                        # Preview only — do NOT set movement_tiles / unit_is_selected.
                        # Those flags mean "blue squares are up in-game." Faking them
                        # makes legal_moves offer MOVE before SELECT lands.
                        context["reachable_tiles"] = [list(t) for t in reachable]
                        log.info(
                            f"Reachable preview for {context['cursor_on_player']}: "
                            f"{len(reachable)} tiles, movement={movement} "
                            f"(not marking selected)"
                        )
                except Exception as e:
                    log.warning(f"Failed to calculate movement tiles: {e}")
        else:
            context["cursor_on_player"] = None
            log.info(f"Cursor at ({cx},{cy}) - no player unit")

        # Compute navigation hints: direction & distance from cursor to each unit
        all_units = (
            [(u, "player") for u in game_state.player_units if u.is_alive and u.current_hp > 0]
            + [(u, "enemy") for u in game_state.enemy_units if u.is_alive and u.current_hp > 0]
            + [(u, "npc") for u in game_state.npc_units if u.is_alive and u.current_hp > 0]
        )
        hints = []
        for u, affil in all_units:
            dx, dy = u.x - cx, u.y - cy
            if dx == 0 and dy == 0:
                direction = "AT cursor"
            else:
                parts = []
                if dx > 0:
                    parts.append(f"{dx}R")
                elif dx < 0:
                    parts.append(f"{-dx}L")
                if dy > 0:
                    parts.append(f"{dy}D")
                elif dy < 0:
                    parts.append(f"{-dy}U")
                direction = ",".join(parts) + " from cursor"
            name = lookup.get_character_name(u.char_id)
            hints.append(f"{name}({affil}) at ({u.x},{u.y}) = {direction}")
        context["navigation"] = hints

    # Build player party list
    weapon_types = _get_weapon_types(lookup)
    party_list = []
    for unit in game_state.player_units:
        if not unit.is_alive or unit.current_hp <= 0:
            continue
        entry = _build_unit_dict_with_types(unit, "player", lookup, weapon_types)
        party_list.append(entry)
    context["party"] = party_list

    # Build enemy list
    enemy_list = []
    for unit in game_state.enemy_units:
        if not unit.is_alive or unit.current_hp <= 0:
            continue
        entry = _build_unit_dict_with_types(unit, "enemy", lookup, weapon_types)
        enemy_list.append(entry)
    context["enemies"] = enemy_list

    # Build NPC/ally list
    ally_list = []
    for unit in game_state.npc_units:
        if not unit.is_alive or unit.current_hp <= 0:
            continue
        entry = _build_unit_dict_with_types(unit, "ally", lookup, weapon_types)
        ally_list.append(entry)
    if ally_list:
        context["allies"] = ally_list

    return context


def _build_unit_dict_with_types(unit, affiliation: str, lookup, weapon_types) -> Dict[str, Any]:
    """Build a unit dict with explicit weapon_types list."""
    entry = {
        "id": str(unit.char_id),
        "name": lookup.get_character_name(unit.char_id),
        "unitClass": lookup.get_class_name(unit.class_id),
        "level": unit.level,
        "hp": unit.current_hp,
        "maxHp": unit.max_hp,
        "x": unit.x,
        "y": unit.y,
        "strength": unit.strength,
        "skill": unit.skill,
        "speed": unit.speed,
        "defense": unit.defense,
        "resistance": unit.resistance,
        "luck": unit.luck,
        "affiliation": affiliation,
        "hasMoved": unit.has_moved,
    }

    # AI flags (for enemies)
    if unit.ai_flags > 0:
        entry["aiFlags"] = unit.ai_flags

    # Rescue/ballista info
    if unit.rescue_target > 0:
        entry["rescueTarget"] = unit.rescue_target
    if unit.ballista_index >= 0:
        entry["ballistaIndex"] = unit.ballista_index

    # Items
    if unit.items:
        item_names = [lookup.get_item_name(item_id) for item_id, _uses in unit.items]
        entry["equippedWeapon"] = item_names[0]
        entry["items"] = [
            {"name": lookup.get_item_name(item_id), "uses": uses}
            for item_id, uses in unit.items
        ]

    # Status effects
    if unit.status_effect != 0:
        entry["status"] = lookup.get_status_name(unit.status_effect)
        entry["statusDuration"] = unit.status_duration

    # Weapon ranks
    wranks = {}
    for i, rank_val in enumerate(unit.weapon_ranks):
        if rank_val > 0 and i < len(weapon_types):
            wranks[weapon_types[i]] = lookup.get_weapon_rank_letter(rank_val)
    if wranks:
        entry["weaponRanks"] = wranks

    return entry
