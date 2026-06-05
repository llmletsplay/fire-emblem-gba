import os
import sys
import json
import time
import base64
import copy
import asyncio
import datetime
import logging
import socket
import math
import re
import concurrent.futures
import functools

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from PIL import Image
from tools.token_counter import count_tokens, calculate_prompt_tokens

from src.core import config
from src.game.fe_state import prep_fe_llm as prep_llm
from src.game.button_mapping import normalize_button_sequence
from src.utils.json_parser import parse_optional_fenced_json
from src.utils.screen_tracker import get_tracker as get_screen_tracker

# Import knowledge base if persistent learning is enabled
if config.PERSISTENT_LEARNING:
    from src.utils.knowledge_base import FEKnowledgeBase, BattleUnderstandingModule
    knowledge_base = FEKnowledgeBase()
    battle_module = BattleUnderstandingModule(knowledge_base)
else:
    knowledge_base = None
    battle_module = None

# All prompts consolidated in prompts.py
from src.llm.prompts import (
    build_memory_aware_prompt,
    build_system_prompt,
    get_summary_prompt,
    build_anti_hallucination_prompt,
    create_enhanced_prompt_system
)

# Import memory and session managers
from src.utils.memory_manager import MemoryManager, MemoryEntry
from src.utils.session_manager import SessionManager
from src.llm.client_setup import setup_llm_client, setup_vision_model
from src.services.benchmark import Benchmark
from src.llm.client_setup import DEFAULT_MODE, ONE_IMAGE_PER_PROMPT, REASONING_ENABLED, USES_DEFAULT_TEMPERATURE, REASONING_EFFORT, IMAGE_DETAIL, USES_MAX_COMPLETION_TOKENS, MAX_TOKENS, TEMPERATURE, MINIMAP_ENABLED, MINIMAP_2D, SYSTEM_PROMPT_UNSUPPORTED
from src.game.feature_config import (
    USE_VISION_MODEL, TRUST_VISION_DESCRIPTIONS, VISION_OVERRIDE_MAIN_MODEL,
    PATHFINDING_ENABLED, LOG_VISION_DESCRIPTIONS, LOG_LLM_RAW_OUTPUT,
    SAVE_SCREENSHOTS, VISION_MAX_TOKENS, USE_INTERNAL_MAPPING,
    MINIMAP_ENABLED as FEATURE_MINIMAP_ENABLED
)

from src.game.command_parser import parse_command_from_llm_output, extract_command_text
from src.game.command_executor import execute_with_validation, execute_command_sequence
from src.game.command_validator import validate_command_sequence, get_validation_feedback
from src.game.actions import ActionResult
from src.game.tile_tracker import record_tile_failure, check_tile_known_bad, clear_failed_tiles_on_progress, tile_tracker
from src.llm.token_compactor import compact_context_to_budget
from src.llm.action_processor import capture_action_result, encode_image_base64, detect_game_phase, get_image_description
from src.llm.dialogue_processor import extract_dialogue_instruction

_record_tile_failure = record_tile_failure
_check_tile_known_bad = check_tile_known_bad
_clear_failed_tiles_on_progress = clear_failed_tiles_on_progress


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('llmdriver')


# Updated regex to accept full button names
ACTION_RE = re.compile(r'^(?:[LRUDAB]|Start|Select)(?:;(?:[LRUDAB]|Start|Select))*(?:;)?$', re.IGNORECASE)
COORD_RE = re.compile(r'^([0-9]),([0-8])$')
ANALYSIS_RE = re.compile(r"<game_analysis>([\s\S]*?)</game_analysis>", re.IGNORECASE)
# Strip model-specific wrapper tokens (GLM <|begin_of_box|>, deepseek <|tool_call|>, etc.)
_MODEL_TOKEN_RE = re.compile(r'<\|[^|]*\|>')
IS_LOCAL = DEFAULT_MODE == "LMSTUDIO" or DEFAULT_MODE == "OLLAMA"

# Use configurable timeouts from config/environment
STREAM_TIMEOUT = config.LLM_STREAM_TIMEOUT
# For local models, we might want even longer timeouts
if IS_LOCAL and STREAM_TIMEOUT < 120:
    STREAM_TIMEOUT = 120

# Use configurable cleanup window from config
CLEANUP_WINDOW = config.CLEANUP_WINDOW

SCREENSHOT_PATH = os.path.join(config.PROJECT_ROOT, "screenshots/latest.png")
# Ensure screenshots directory exists
try:
    os.makedirs(os.path.dirname(SCREENSHOT_PATH), exist_ok=True)
except Exception:
    pass
MINIMAP_PATH = "minimap.png"

SAVED_SCREENSHOT_PATH = SCREENSHOT_PATH
SAVED_MINIMAP_PATH = MINIMAP_PATH

# Setup LLM client and vision model
client, MODEL, supports_reasoning = setup_llm_client()
vision_client, vision_model = setup_vision_model()

chat_history = []
response_count = 0
action_count = 0
tokens_used_session = 0
last_input_tokens = 0  # Track last call's input token estimate for UI
start_time = datetime.datetime.now()

# Initialize memory and session managers
memory_manager = MemoryManager(window_size=config.MEMORY_WINDOW_SIZE)
session_manager = SessionManager(
    max_sessions=config.SESSION_MAX_COUNT,
    max_screenshots_per_session=config.SESSION_MAX_SCREENSHOTS
)


# ─── Constants ────────────────────────────────────────────────────────────────
LLM_TOTAL_TIMEOUT = config.LLM_TOTAL_TIMEOUT     # e.g. 70 s / 130 s

MAX_INPUT_TOKENS = config.MAX_INPUT_TOKENS       # Token budget for compaction

# ─── Action Tracking (for state-machine inference) ────────────────────────────
_last_action_sent = None
_last_game_state = None
_last_action_type = None  # For result capture: "SELECT", "MOVE", "ATTACK", etc.
# Tracks tiles where actions failed (cursor pos → failure info)
# Key: (x, y) tuple.  Value: {"count": int, "actions": [str], "last_cycle": int}
_failed_tiles = {}
# Key: unit name (str). Value: {"attempts": int, "last_cycle": int, "actions": [str]}
_unit_attempt_tracker = {}
_current_cycle_num = 0

# Dialogue instruction persistence
# Stores extracted instructions from tutorial/story dialogue so they survive
# across cycles after the text box is dismissed and compaction drops chat history.
_dialogue_buffer = []          # list of dicts, newest last
_DIALOGUE_BUFFER_MAX = 5
_DIALOGUE_EXPIRY_CYCLES = 12

# Tile tracking globals (delegated to tile_tracker module)
_failed_tiles = tile_tracker.failed_tiles
_unit_attempt_tracker = tile_tracker.unit_attempt_tracker


def _emergency_trim_payload(payload: dict):
    """Strip non-essential heavy fields from game state to reduce token count.

    Removes navigation hints, movement/attack tiles, flash indicators,
    memory thumbnails, and detailed unit data (items, weapon ranks).
    Keeps essential fields: name, class, hp, position, hasMoved.
    """
    payload.pop("navigation", None)
    payload.pop("memory_thumbnails", None)
    payload.pop("movement_tiles", None)
    payload.pop("attack_tiles", None)
    payload.pop("flash_indicators", None)
    payload.pop("minimap_description", None)
    payload.pop("minimap_2d", None)
    for key in ("party", "enemies", "allies"):
        for unit in payload.get(key, []):
            unit.pop("weaponRanks", None)
            unit.pop("items", None)
            unit.pop("equippedWeapon", None)
            unit.pop("strength", None)
            unit.pop("skill", None)
            unit.pop("speed", None)
            unit.pop("defense", None)
            unit.pop("resistance", None)
            unit.pop("luck", None)


def _get_next_suggested_unit(current_state: dict, exclude_unit: str = None) -> tuple[str, int, int] | None:
    """Find the best next unit to try if the current one is stuck."""
    unit_status = current_state.get("unit_status", {})
    available = [n for n, s in unit_status.items() if s == "available"]

    if not available:
        return None

    # Filter out the stuck unit
    candidates = [n for n in available if n != exclude_unit]
    if not candidates:
        return None

    # Get unit positions from party list
    party = current_state.get("party", [])
    unit_positions = {u["name"]: (u["x"], u["y"]) for u in party if u.get("name") in candidates}

    # Helper to get failure count
    def get_fail_count(name):
        return _unit_attempt_tracker.get(name, {}).get("attempts", 0)

    # Sort candidates:
    # 1. Least failures (prioritize untried units)
    # 2. Distance from current cursor (convenience)
    cursor = current_state.get("cursor", (0, 0))

    def sort_key(name):
        attempts = get_fail_count(name)
        pos = unit_positions.get(name, (99, 99))
        dist = abs(pos[0] - cursor[0]) + abs(pos[1] - cursor[1])
        return (attempts, dist)

    candidates.sort(key=sort_key)

    best_name = candidates[0]
    best_pos = unit_positions.get(best_name)

    if best_pos:
        return best_name, best_pos[0], best_pos[1]
    return None


def _infer_screen_context(current_state: dict, last_action: str, last_state: dict,
                          text_box_visible: bool = False, input_locked: bool = False) -> dict:
    """
    Combine game state signals to produce actionable screen context for the LLM.

    Returns dict with:
        previous_action: str — what was sent last cycle (or "none")
        screen_context: str — human-readable hint about current screen state
        context_hints: list[str] — directive hints for the LLM
    """
    result = {
        "previous_action": last_action or "none",
        "screen_context": "",
        "context_hints": [],
    }

    if not current_state:
        return result

    ui_state = current_state.get("ui_state", "unknown")
    cursor_on_player = current_state.get("cursor_on_player")
    cursor_on_player_moved = current_state.get("cursor_on_player_moved", False)
    phase = current_state.get("phase", "unknown")
    movement_tiles = current_state.get("movement_tiles", [])
    has_movement_tiles = bool(movement_tiles)

    # Detect action menu open: when cursor on already-moved unit AND movement tiles detected
    # This means the "Rescue/Item/Trade/Wait" menu is open (not movement selection)
    action_menu_open = cursor_on_player_moved and has_movement_tiles

    # PRIORITY: Detect STORY DIALOGUE mode - takes precedence over all other context
    # When text_box_visible AND input_locked are both true, we're in a cutscene/story
    # In this mode, there's no actual gameplay cursor or unit selection - don't report it
    is_story_dialogue = text_box_visible and input_locked

    # Build screen context based on signals
    context_parts = []
    hints = []

    # STORY DIALOGUE: Override everything else - don't report cursor/units
    if is_story_dialogue:
        context_parts.append("STORY DIALOGUE/CUTSCENE ACTIVE")
        hints.append("Dialogue box visible and game input is locked. This is a story cutscene - NOT gameplay. Press A; once to advance the dialogue.")
        result["screen_context"] = " | ".join(context_parts)
        result["context_hints"] = hints if config.CONTEXT_HINTS_ENABLED else []
        return result

    # Detect if game state is unchanged from last cycle (action had no effect)
    state_unchanged = False
    if last_state and last_action:
        # Compare fields that should change if an action worked.
        # Using unit_status (per-unit hasMoved dict) catches individual unit actions
        # that the old count-only comparison missed.
        keys_to_compare = ["cursor", "phase", "turn", "player_units", "enemy_units",
                           "unit_status", "unmoved_count"]
        unchanged_count = 0
        for key in keys_to_compare:
            if current_state.get(key) == last_state.get(key):
                unchanged_count += 1
        # If ALL tracked fields are identical, the action likely had no effect
        if unchanged_count == len(keys_to_compare):
            state_unchanged = True

    # Phase info
    if phase == "player_phase":
        context_parts.append("Player phase — your turn to command units")
    elif phase == "enemy_phase":
        context_parts.append("Enemy phase — wait for enemies to finish")
        hints.append("Enemy phase active. Press B; or wait. Do NOT move units.")
    elif phase == "start_screen":
        context_parts.append("Title/start screen")
        hints.append("Press Start; to begin the game.")

    # Cursor-on-player detection (critical for A-press loop prevention)
    # Check if the last action ended with an A press
    last_ended_with_a = False
    if last_action:
        parts = [p for p in last_action.strip().rstrip(';').split(';') if p]
        last_ended_with_a = parts and parts[-1].upper() == 'A'

    # Detect if last action was D-pad only (no A press at end)
    last_was_dpad_only = False
    if last_action:
        parts = [p for p in last_action.strip().rstrip(';').split(';') if p]
        last_was_dpad_only = parts and all(p.upper() in ('U', 'D', 'L', 'R') for p in parts)

    # Compute input_locked state for the PREVIOUS cycle (needed to guard inferences below).
    # If input was locked when we sent A, the A press did nothing — we can't infer "unit selected".
    last_was_locked = bool(last_state and last_state.get("input_locked")) if last_state else False

    # Guard: if input was locked (current or previous cycle), A presses had no effect
    a_press_effective = last_ended_with_a and not input_locked and not last_was_locked

    if cursor_on_player and phase == "player_phase":
        # CRITICAL: Check if unit has already moved FIRST — this takes absolute precedence.
        # A grayed-out unit cannot be selected, so pressing A does nothing.
        if cursor_on_player_moved:
            if action_menu_open:
                context_parts.append(f"Cursor on {cursor_on_player} (ALREADY MOVED + ACTION MENU OPEN)")
                hints.append(
                    f"*** ACTION MENU OPEN! {cursor_on_player} has ALREADY ACTED. "
                    f"The menu shows Rescue/Item/Trade/Wait. Press B; to dismiss, then select a different unit. ***"
                )
            else:
                context_parts.append(f"Cursor on {cursor_on_player} (ALREADY MOVED — grayed out, CANNOT select)")
                hints.append(
                    f"*** {cursor_on_player} has ALREADY ACTED this turn and is grayed out. "
                    f"Pressing A on this unit does NOTHING — it will NOT select them. "
                    f"You MUST move to a different unmoved BLUE unit. ***"
                )
            # Provide unmoved unit list from unit_status (authoritative, not party scan)
            unit_status = current_state.get("unit_status", {})
            available_names = [name for name, status in unit_status.items() if status == "available"]
            if available_names:
                hints.append(f"Available unmoved units (from memory): {', '.join(available_names)}")

            # Find nearest unmoved player unit and provide navigation
            party = current_state.get("party", [])
            cursor = current_state.get("cursor")
            if cursor and party:
                unmoved = [(u["name"], u["x"], u["y"]) for u in party
                           if not u.get("hasMoved") and u.get("name") != cursor_on_player]
                if unmoved:
                    nearest_unmoved = min(unmoved, key=lambda u: abs(u[1] - cursor[0]) + abs(u[2] - cursor[1]))
                    dx = nearest_unmoved[1] - cursor[0]
                    dy = nearest_unmoved[2] - cursor[1]
                    nav = []
                    if dx < 0: nav.extend(["L"] * (-dx))
                    elif dx > 0: nav.extend(["R"] * dx)
                    if dy < 0: nav.extend(["U"] * (-dy))
                    elif dy > 0: nav.extend(["D"] * dy)
                    nav_str = ";".join(nav) + ";" if nav else ""
                    hints.append(
                        f"NAVIGATE TO UNMOVED UNIT: {nearest_unmoved[0]} at ({nearest_unmoved[1]},{nearest_unmoved[2]}). "
                        f"Press B; first to clear state, then navigate: {nav_str}"
                    )
                else:
                    # All units have moved — end turn
                    hints.append("ALL units have already acted this turn. End your turn: Select;")
        elif a_press_effective:
            # We just pressed A with cursor on this unit AND input was NOT locked — unit is now SELECTED
            context_parts.append(f"UNIT SELECTED: {cursor_on_player}. Blue movement squares should be visible.")
            hints.append(f"*** STOP *** You just pressed A on {cursor_on_player}. "
                         f"The unit is NOW SELECTED. Blue squares should be visible. "
                         f"DO NOT press A again! Use D-pad to navigate to a blue tile, then press A to CONFIRM the move.")
            enemies = current_state.get("enemies", [])
            cursor = current_state.get("cursor")
            if enemies:
                # Enemy-focused navigation
                hints.append("Navigate with D-pad TOWARD THE NEAREST ENEMY, then press A as the VERY LAST button to confirm. "
                             "Example: L;L;U;A; — the trailing A; is REQUIRED to confirm the move.")
                # Tactical: compute ALL adjacent tiles to attack nearest enemy from
                if cursor:
                    nearest = min(enemies, key=lambda e: abs(e.get("x", 99) - cursor[0]) + abs(e.get("y", 99) - cursor[1]))
                    ex, ey = nearest.get("x", 99), nearest.get("y", 99)
                    dist = abs(ex - cursor[0]) + abs(ey - cursor[1])
                    if dist <= 12:
                        adj_tiles = [(ex - 1, ey), (ex + 1, ey), (ex, ey - 1), (ex, ey + 1)]
                        # Sort by distance from cursor (closest first)
                        adj_tiles.sort(key=lambda t: abs(t[0] - cursor[0]) + abs(t[1] - cursor[1]))
                        # Filter out known-bad tiles
                        untried_adj = [t for t in adj_tiles if not _check_tile_known_bad(t[0], t[1])]
                        if not untried_adj:
                            untried_adj = adj_tiles  # fallback: show all if everything failed
                        # Build hint listing ALL viable adjacent tiles in priority order
                        attack_hint = (
                            f"ATTACK TARGET: {nearest.get('name','Enemy')} is at ({ex},{ey}). "
                            f"Move NEXT TO the enemy (not onto it). Try these tiles IN ORDER:"
                        )
                        for i, t in enumerate(untried_adj):
                            dx = t[0] - cursor[0]
                            dy = t[1] - cursor[1]
                            nav = []
                            if dx < 0: nav.extend(["L"] * (-dx))
                            elif dx > 0: nav.extend(["R"] * dx)
                            if dy < 0: nav.extend(["U"] * (-dy))
                            elif dy > 0: nav.extend(["D"] * dy)
                            nav_str = ";".join(nav) + ";A;" if nav else "A;"
                            marker = " ← TRY THIS FIRST" if i == 0 else ""
                            attack_hint += f"\n  {i+1}. ({t[0]},{t[1]}) → {nav_str}{marker}"
                        hints.append(attack_hint)
            else:
                # No enemies — check for seize objective
                objective_type = current_state.get("objective_type")
                seize_pos = current_state.get("seize_position")
                if objective_type == "seize":
                    if seize_pos and cursor:
                        sx, sy = seize_pos
                        dx, dy = sx - cursor[0], sy - cursor[1]
                        nav = []
                        if dx < 0: nav.extend(["L"] * (-dx))
                        elif dx > 0: nav.extend(["R"] * dx)
                        if dy < 0: nav.extend(["U"] * (-dy))
                        elif dy > 0: nav.extend(["D"] * dy)
                        nav_str = ";".join(nav) + ";A;" if nav else "A;"
                        hints.append(
                            f"ALL ENEMIES DEFEATED! SEIZE the gate/throne at ({sx},{sy}). "
                            f"Navigate there and press A; to confirm. Suggested: {nav_str}")
                    else:
                        hints.append(
                            "ALL ENEMIES DEFEATED! Objective: SEIZE the gate/throne. "
                            "Look at the screenshot for the gate/throne tile (ornate tile, usually where the boss was). "
                            "Move there with D-pad, press A; to land on it, then select 'Seize' from the action menu.")
                else:
                    hints.append("Navigate with D-pad to your destination, then press A as the VERY LAST button to confirm. "
                                 "Example: L;L;U;A; — the trailing A; is REQUIRED to confirm the move.")
        elif last_was_dpad_only:
            # Last action was D-pad only — unit might still be selected, need to confirm
            context_parts.append(f"Cursor on {cursor_on_player} — unit may still be SELECTED (blue squares visible)")
            hints.append(f"You just navigated with D-pad but did NOT press A to confirm. "
                         f"If blue squares are visible and cursor is at your destination, press A; NOW to confirm the move. "
                         f"If you need to move further, use D-pad with A as the LAST button: e.g., L;L;A;")
        else:
            context_parts.append(f"Cursor on {cursor_on_player} (available — press A to select)")
            hints.append(f"Cursor is on {cursor_on_player} who has NOT moved yet. Press A; ONCE to select this unit. "
                         f"After selecting, blue movement squares will appear — then navigate with D-pad and end with A; to confirm.")
    elif not cursor_on_player and phase == "player_phase":
        if last_ended_with_a:
            context_parts.append("Cursor on empty tile or menu may have opened")
            hints.append("You pressed A on an empty tile — this may have opened the map menu. "
                         "If a menu is visible, press B; to close it. Then navigate to a BLUE unit.")
        elif last_was_dpad_only:
            # Navigated to an empty tile — might be confirming a move destination
            context_parts.append("Cursor on empty tile after D-pad navigation")
            hints.append("You navigated with D-pad to an empty tile. If a unit is selected (blue squares visible), "
                         "press A; to confirm the move. If no unit is selected, navigate to a BLUE unit first.")
        else:
            context_parts.append("No unit under cursor — navigate to a BLUE unit")
            # Use unit_status to suggest which units are available
            unit_status = current_state.get("unit_status", {})
            available = [n for n, s in unit_status.items() if s == "available"]
            if available:
                hints.append(f"Cursor is NOT on any unit. Available unmoved units: {', '.join(available)}. "
                             "Use the navigation hints in game_state to find the nearest one and navigate there with D-pad.")
            else:
                hints.append("Cursor is NOT on any unit. Use the navigation hints in game_state to find the nearest "
                             "unmoved BLUE unit and navigate there with D-pad. Do NOT press A on empty tiles.")

    # State unchanged warning + record the failure
    # BUT: skip if input was locked (current or previous cycle) — D-pad during
    # dialogue/animation having no effect is expected, not a tile failure.
    if state_unchanged and last_action:
        if input_locked or last_was_locked:
            hints.append("Input was locked (dialogue/animation) when your last action was sent — "
                         "it had no effect because the game was busy, not because of a bad tile.")
        else:
            hints.append(f"WARNING: Your last action '{last_action}' had no visible effect on game state. Try a DIFFERENT approach.")
            # Record the cursor position where this failure occurred
            last_cursor = last_state.get("cursor") if last_state else None
            _record_tile_failure(last_cursor, last_action, _current_cycle_num)

            # Unit-level stuck detection
            if cursor_on_player and phase == "player_phase":
                # Increment attempts for this unit
                if cursor_on_player not in _unit_attempt_tracker:
                    _unit_attempt_tracker[cursor_on_player] = {"attempts": 0, "last_cycle": 0, "actions": []}

                tracker = _unit_attempt_tracker[cursor_on_player]
                tracker["attempts"] += 1
                tracker["last_cycle"] = _current_cycle_num
                if last_action not in tracker["actions"]:
                    tracker["actions"].append(last_action)

                attempts = tracker["attempts"]
                log.info(f"Unit stuck check: {cursor_on_player} has {attempts} failed attempts")

                # Escalate hints based on attempt count
                if attempts >= 3:
                    # Find a better unit to try
                    next_unit_info = _get_next_suggested_unit(current_state, exclude_unit=cursor_on_player)

                    if next_unit_info:
                        next_name, nx, ny = next_unit_info
                        # Calculate navigation
                        cursor = current_state.get("cursor")
                        nav_str = ""
                        if cursor:
                            dx, dy = nx - cursor[0], ny - cursor[1]
                            nav = []
                            if dx < 0: nav.extend(["L"] * (-dx))
                            elif dx > 0: nav.extend(["R"] * dx)
                            if dy < 0: nav.extend(["U"] * (-dy))
                            elif dy > 0: nav.extend(["D"] * dy)
                            nav_str = ";".join(nav) + ";" if nav else ""

                        if attempts >= 7:
                            # FORCED SWITCH
                            hints.append(
                                f"FORCED UNIT SWITCH: You have failed {attempts} times with {cursor_on_player}. "
                                f"You MUST stop trying {cursor_on_player}. "
                                f"Navigate to {next_name} at ({nx},{ny}) and try them instead. "
                                f"Navigation: B;{nav_str}"
                            )
                        elif attempts >= 5:
                            # STRONG WARNING
                            hints.append(
                                f"UNIT STUCK: Stop trying {cursor_on_player} ({attempts} failures). "
                                f"Try {next_name} at ({nx},{ny}) instead. "
                                f"Navigation: B;{nav_str}"
                            )
                        else:
                            # SOFT WARNING
                            hints.append(
                                f"You've tried {cursor_on_player} {attempts} times without success. "
                                f"Consider switching to {next_name} at ({nx},{ny})."
                            )

    # Clear failed tiles on real game progress
    _clear_failed_tiles_on_progress(last_state, current_state)

    # Inject failed tile warnings so the LLM learns from mistakes
    if _failed_tiles:
        failed_list = []
        for (fx, fy), info in sorted(_failed_tiles.items(), key=lambda kv: -kv[1]["count"]):
            failed_list.append({
                "tile": [fx, fy],
                "failures": info["count"],
                "actions_tried": info["actions"][:5],  # cap for token budget
            })
        if failed_list:
            result["failed_tiles"] = failed_list[:10]  # cap at 10 entries

        # Warn if current cursor is ON a known-bad tile
        current_cursor = current_state.get("cursor")
        if current_cursor and _check_tile_known_bad(current_cursor[0], current_cursor[1]):
            bad_info = _failed_tiles[tuple(current_cursor)]
            hints.append(
                f"WARNING: Cursor is at {list(current_cursor)} which has FAILED {bad_info['count']} times "
                f"(tried: {', '.join(bad_info['actions'][:3])}). Move somewhere ELSE."
            )
            # Stuck recovery: if 3+ failures and enemies exist, suggest untried adjacent-to-enemy tiles
            enemies = current_state.get("enemies", [])
            if bad_info['count'] >= 3 and enemies:
                recovery_suggestions = []
                for enemy in enemies[:3]:  # check up to 3 nearest enemies
                    ex, ey = enemy.get("x"), enemy.get("y")
                    if ex is None or ey is None:
                        continue
                    adj = [(ex - 1, ey), (ex + 1, ey), (ex, ey - 1), (ex, ey + 1)]
                    untried = [t for t in adj if not _check_tile_known_bad(t[0], t[1])]
                    for t in untried:
                        recovery_suggestions.append((t, enemy.get("name", "Enemy")))
                if recovery_suggestions:
                    parts = [f"({t[0]},{t[1]}) next to {name}" for t, name in recovery_suggestions[:4]]
                    hints.append(
                        f"STUCK RECOVERY: Try these UNTRIED tiles to attack from: {'; '.join(parts)}. "
                        f"Or press B; to cancel and try a different unit entirely."
                    )
                else:
                    hints.append(
                        "STUCK RECOVERY: All adjacent attack tiles have been tried. "
                        "Press B; to cancel, then try selecting a DIFFERENT unit."
                    )

    # Dialogue / text box / input lock detection
    if text_box_visible and input_locked:
        context_parts.append("DIALOGUE ACTIVE (confirmed by both memory lock and screenshot)")
        hints.append("DIALOGUE CONFIRMED: Text box visible AND game input is locked. Press A; ONCE to dismiss, then STOP.")
    elif text_box_visible:
        context_parts.append("DIALOGUE/TEXT BOX detected on screen")
        hints.append("Text box visible at bottom of screen. Press A; ONCE to dismiss, then STOP.")
    elif input_locked and text_box_visible:
        context_parts.append("Game input is LOCKED (animation/cutscene/dialogue)")
        hints.append("Game input is LOCKED — likely dialogue, animation, or cutscene in progress. Wait or press A; once.")
    elif input_locked:
        context_parts.append("Game input may be busy (memory flag set)")
        hints.append("Memory indicates input_locked but no text box visible — game may be transitioning. Continue with normal gameplay.")

    # Dialogue instruction persistence — inject buffered instructions from recent dialogue
    if _dialogue_buffer:
        for entry in _dialogue_buffer:
            age = _current_cycle_num - entry.get("cycle", 0)
            if age > _DIALOGUE_EXPIRY_CYCLES:
                continue  # expired, skip
            unit_names = entry.get("unit_names", [])
            instr_type = entry.get("instruction_type", "general")
            instr_text = entry.get("text", "")[:120]

            if unit_names:
                names_str = ", ".join(unit_names)
                hints.append(
                    f"DIALOGUE INSTRUCTION (from {age} cycles ago): \"{instr_text}\" "
                    f"— Target: {names_str}. FOLLOW THIS."
                )
                # Compliance check: if cursor is on a player NOT in the instructed names
                if cursor_on_player and cursor_on_player not in unit_names:
                    hints.append(
                        f"WARNING: WRONG UNIT — Dialogue says {instr_type} {names_str}, "
                        f"but cursor is on {cursor_on_player}. Do NOT press A — "
                        f"navigate to {names_str} first."
                    )
            else:
                hints.append(
                    f"RECENT DIALOGUE (from {age} cycles ago): \"{instr_text}\" — Follow instructions."
                )

    # Display cursor vs PlaySt cursor divergence
    display_cursor = current_state.get("display_cursor")
    playst_cursor = current_state.get("cursor")
    if display_cursor and playst_cursor and tuple(display_cursor) != tuple(playst_cursor):
        hints.append(f"NOTE: Display cursor at {list(display_cursor)} differs from memory cursor at {list(playst_cursor)} "
                     f"— game may be in tutorial/guided mode. Use display_cursor for navigation.")

    # Tutorial target from event slots (authoritative when present) - only if tutorial mode enabled
    if config.TUTORIAL_MODE:
        tutorial_target = current_state.get("tutorial_target")
        if tutorial_target:
            tx, ty = tutorial_target
            cursor = current_state.get("cursor")
            if cursor:
                dx, dy = tx - cursor[0], ty - cursor[1]
                dir_parts = []
                if dx < 0:
                    dir_parts.append(f"LEFT {-dx}")
                elif dx > 0:
                    dir_parts.append(f"RIGHT {dx}")
                if dy < 0:
                    dir_parts.append(f"UP {-dy}")
                elif dy > 0:
                    dir_parts.append(f"DOWN {dy}")
                direction = ", ".join(dir_parts) if dir_parts else "ALREADY THERE"
                hints.append(f"TUTORIAL TARGET at ({tx},{ty}) — Navigate: {direction} from cursor ({cursor[0]},{cursor[1]})")
            context_parts.append(f"TUTORIAL TARGET at ({tx},{ty}) — follow this authoritative destination")
            # Move tutorial_target hint to front (after dialogue instructions) since it's authoritative
            tutorial_hint_idx = len(hints) - 1
            if tutorial_hint_idx > 0:
                hints.insert(1, hints.pop(tutorial_hint_idx))

    # Inject compact unit status summary into screen_context (always visible)
    unit_status = current_state.get("unit_status", {})
    if unit_status and phase == "player_phase":
        available = [n for n, s in unit_status.items() if s == "available"]
        acted = [n for n, s in unit_status.items() if s == "already_acted"]
        status_parts = []
        if available:
            status_parts.append(f"AVAILABLE({len(available)}): {', '.join(available)}")
        if acted:
            status_parts.append(f"ACTED({len(acted)}): {', '.join(acted)}")
        if status_parts:
            context_parts.append(" | ".join(status_parts))

    result["screen_context"] = " | ".join(context_parts) if context_parts else "Observing..."
    result["context_hints"] = hints if config.CONTEXT_HINTS_ENABLED else []
    return result


# ─── Helper ───────────────────────────────────────────────────────────────────
async def call_llm_with_timeout(state_data: dict,
                                llm_timeout: float = STREAM_TIMEOUT,
                                total_timeout: float = LLM_TOTAL_TIMEOUT,
                                benchmark: Benchmark = None):
    """
    Run `llm_stream_action` in a worker thread and abort the whole thing
    (token‑counting, API call, streaming, parsing…) after `total_timeout` s.
    """
    loop = asyncio.get_running_loop()
    fn   = functools.partial(llm_stream_action, state_data, llm_timeout, benchmark)

    try:
        # run blocking LLM code in a thread, wait with an asyncio timeout
        result = await asyncio.wait_for(loop.run_in_executor(None, fn),
                                        timeout=total_timeout)
        return result  # Propagate the 4-tuple from llm_stream_action
    except asyncio.TimeoutError:
        log.error(f"llm_stream_action exceeded {total_timeout}s – skipping cycle.")
        log.error(f"Consider increasing LLM_STREAM_TIMEOUT and LLM_TOTAL_TIMEOUT in your .env file")
        log.error(f"Current timeouts: STREAM={llm_timeout}s, TOTAL={total_timeout}s")
        return None, None, False, None

def summarize_and_reset(benchmark: Benchmark = None):
    """Condenses history, updates system prompt, resets history, accounts for tokens."""
    global chat_history, response_count, tokens_used_session

    log.info(f"Summarizing chat history ({len(chat_history)} messages)...")


    history_for_summary = []

    # we convert from 'assistant' to 'user' since many API's don't like multiple 'assistant'
    # messages and will error out.
    for msg in chat_history:
        if msg['role'] == 'assistant':
            history_for_summary.append({
                'role': 'user',
                'content': msg['content']
            })


    if not history_for_summary:
        log.info("No relevant assistant messages to summarize, skipping summarization call.")

        current_system_prompt = chat_history[0]
        chat_history = [current_system_prompt]
        response_count = 0
        log.info("History reset to system prompt without summarization.")
        return None

    summary_prompt = get_summary_prompt()
    summary_input_messages = [{"role": "system", "content": summary_prompt}] + history_for_summary

    logging.info(f"Messages: {summary_input_messages}")

    summary_input_tokens = calculate_prompt_tokens(summary_input_messages)
    log.info(f"Summarization estimated input tokens: {summary_input_tokens}")

    summary_text = "Error generating summary."
    summary_output_tokens = 0

    kwargs = {
        "model": MODEL,
        "messages": summary_input_messages,
    }

    if USES_MAX_COMPLETION_TOKENS:
        kwargs["max_completion_tokens"] = MAX_TOKENS
    else:
        kwargs["max_tokens"] = MAX_TOKENS

    if USES_DEFAULT_TEMPERATURE:
        kwargs["temperature"] = 1.0
    else:
        kwargs["temperature"] = TEMPERATURE

    try:
        summary_resp = client.chat.completions.create(**kwargs)
        if summary_resp.choices and summary_resp.choices[0].message.content:
            summary_text = summary_resp.choices[0].message.content.strip()
            summary_output_tokens = count_tokens(summary_text)
        else:
            log.warning("LLM Summary: No choices or empty content.")
            summary_text = "Summary generation failed."

        total_summary_tokens = summary_input_tokens + summary_output_tokens
        tokens_used_session += total_summary_tokens
        log.info(f"Summarization call used approx. {total_summary_tokens} tokens. Session total: {tokens_used_session}")

    except Exception as e:
        log.error(f"Error during LLM summarization call: {e}", exc_info=True)

    json_object = parse_optional_fenced_json(summary_text)
    
    log.info(f"LLM Summary generated ({summary_output_tokens} tokens): {str(json_object)}")

    benchInstructions = ""
    if benchmark is not None:
        benchInstructions = benchmark.instructions

    new_system_prompt_content = build_system_prompt(summary_text, benchInstructions)
    chat_history = [{"role": "system", "content": new_system_prompt_content}]
    response_count = 0
    log.info("Chat history summarized and reset.")
    return json_object


def next_with_timeout(iterator, timeout: float):
    """Attempt to pull the first chunk from `iterator` within `timeout` seconds."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: next(iterator))
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"No chunk received in {timeout}s")


def llm_stream_action(state_data: dict, timeout: float = STREAM_TIMEOUT, benchmark: Benchmark = None):
    """
    Determines and executes an action by querying an LLM.

    Returns:
        Tuple of (action, analysis_text, needs_summary, semantic_action)
        - action: Low-level button sequence string (for legacy support)
        - analysis_text: LLM's reasoning trace
        - needs_summary: Whether to summarize chat history
        - semantic_action: CommandSequence from new semantic command system (or None)
    """
    global response_count, tokens_used_session, chat_history, last_input_tokens

    # This function intelligently switches between streaming and non-streaming API calls.
    # - For models supporting a 'reasoning_effort', it uses a non-streaming call to
    #   avoid timeouts while the model "thinks".
    # - For other models, it streams the response for lower perceived latency.

    needs_summary = False
    payload = copy.deepcopy(state_data)
    screenshot = payload.pop("screenshot", None)
    minimap = payload.pop("minimap", None)

    if not MINIMAP_2D:
        log.debug("Minimap 2D disabled, removing minimap_2d from payload.")
        payload.pop("minimap_2d", None)

    if not isinstance(payload, dict):
        log.error(f"Invalid state_data structure: {type(state_data)}")
        return None, None, False, None

    # Build the user message with text and images
    text_segment = {"type": "text", "text": json.dumps(payload)}
    current_content = [text_segment]
    image_parts_for_api = []

    if screenshot and isinstance(screenshot.get("image_url"), dict):
        image_parts_for_api.append({"type": "image_url", "image_url": screenshot["image_url"]})
    if minimap and MINIMAP_ENABLED and isinstance(minimap.get("image_url"), dict):
        image_parts_for_api.append({"type": "image_url", "image_url": minimap["image_url"]})

    current_content.extend(image_parts_for_api)

    if(SYSTEM_PROMPT_UNSUPPORTED):
        # TODO: Handle system prompt in messages
        pass

    current_user_message_api = {"role": "user", "content": current_content}
    messages_for_api = chat_history + [current_user_message_api]

    # Token accounting
    call_input_tokens = calculate_prompt_tokens(messages_for_api)
    last_input_tokens = call_input_tokens  # Store for UI broadcast
    log.info(f"LLM call estimate: {call_input_tokens} input tokens; history turns: {len(chat_history)}")

    # Pre-flight safety: if estimate exceeds budget, emergency trim BEFORE the API call.
    # Our token estimator may undercount images, so this catches the obvious cases.
    if call_input_tokens > MAX_INPUT_TOKENS:
        log.warning(f"Pre-flight trim: {call_input_tokens} > {MAX_INPUT_TOKENS}. Emergency compaction.")
        # Drop all chat history except system prompt
        chat_history[:] = [chat_history[0]]
        # Strip heavy optional fields from payload
        _emergency_trim_payload(payload)
        # Rebuild user message with trimmed payload
        text_segment = {"type": "text", "text": json.dumps(payload)}
        current_content = [text_segment] + image_parts_for_api
        current_user_message_api = {"role": "user", "content": current_content}
        messages_for_api = chat_history + [current_user_message_api]
        call_input_tokens = calculate_prompt_tokens(messages_for_api)
        last_input_tokens = call_input_tokens
        log.info(f"After pre-flight trim: {call_input_tokens} tokens")

    full_output = ""
    action = None
    analysis_text = None
    semantic_action = None

    try:
        # --- API Call Section: Conditional Streaming ---
        kwargs = {
            "model": MODEL,
            "messages": messages_for_api,
            "temperature": TEMPERATURE,
        }

        if USES_MAX_COMPLETION_TOKENS:
            kwargs["max_completion_tokens"] = MAX_TOKENS
        else:
            kwargs["max_tokens"] = MAX_TOKENS

        if USES_DEFAULT_TEMPERATURE:
            kwargs["temperature"] = 1.0
        else:
            kwargs["temperature"] = TEMPERATURE

        if supports_reasoning and REASONING_ENABLED:
            # NON-STREAMING path for reasoning models: more robust against long "thinking" times.
            log.info("Model supports reasoning. Making a non-streaming API call.")
            log.info(f"Starting LLM request with model: {MODEL}, timeout: {timeout}s")
            request_start = time.time()
            kwargs["stream"] = False
            # CRITICAL: Only add reasoning_effort if NOT using ZAI adapter
            if not hasattr(client, 'base_url') or 'z.ai' not in str(getattr(client, 'base_url', '')):
                kwargs["reasoning_effort"] = REASONING_EFFORT
                log.info(f"Added reasoning_effort={REASONING_EFFORT} for supported model")
            else:
                log.info("Skipping reasoning_effort for ZAI adapter (not supported)")

            response = client.chat.completions.create(**kwargs)
            log.info(f"LLM request completed in {time.time() - request_start:.2f}s")
            choice = response.choices[0]
            content = choice.message.content

            if content:
                full_output = content.strip()
                print(f">>> {full_output}", end="", flush=True)
            else:
                log.warning(
                    f"LLM response content was None. Finish reason: '{choice.finish_reason}'. "
                    "This is often due to content filtering."
                )
                full_output = ""

        else:
            # STREAMING path for standard models: provides faster user feedback.
            log.info("Model does not use reasoning effort. Using streaming API call.")
            log.info(f"Starting LLM streaming request with model: {MODEL}, timeout: {timeout}s")
            request_start = time.time()
            kwargs["stream"] = True

            response = client.chat.completions.create(**kwargs)

            iterator = iter(response)
            collected_chunks = []
            stream_start = time.time()
            log.info("LLM Stream starting…")
            print(">>> ", end="", flush=True)

            # First-chunk timeout
            try:
                chunk = next_with_timeout(iterator, timeout)
            except StopIteration:
                log.warning("Stream ended immediately with no chunks.")
                chunk = None
            except TimeoutError:
                log.warning(f"TIMEOUT waiting for first chunk after {timeout}s.")
                return None, None, False, None

            if chunk:
                # Process first chunk
                delta = chunk.choices[0].delta.content
                if delta:
                    print(delta, end="", flush=True)
                    collected_chunks.append(delta)
                
                # Continue until finish or total timeout
                if not chunk.choices[0].finish_reason:
                    for chunk in iterator:
                        if time.time() - stream_start > timeout:
                            print("\n[TIMEOUT]", flush=True)
                            log.warning(f"LLM stream timed out after {timeout}s total")
                            raise TimeoutError(f"Stream timed out after {timeout}s")

                        delta = chunk.choices[0].delta.content
                        if delta:
                            print(delta, end="", flush=True)
                            collected_chunks.append(delta)

                        if chunk.choices[0].finish_reason:
                            print(f"\n[END - {chunk.choices[0].finish_reason}]", flush=True)
                            log.info(f"LLM stream finished: {chunk.choices[0].finish_reason}")
                            break
            
            # Assemble final output from chunks
            full_output = "".join(collected_chunks).strip()
            log.info(f"LLM streaming request completed in {time.time() - request_start:.2f}s")

        # --- Post-processing Section (common to both paths) ---

        if not full_output:
            log.error("LLM call resulted in empty output.")
            return None, None, False, None

        log.info(f"LLM raw output length: {len(full_output)} chars")

        # Extract and log LLM reasoning/thinking
        reasoning_match = re.search(r'<\|begin_of_box\|>([\s\S]*?)<\|end_of_box\|>', full_output, re.IGNORECASE)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
            # Log first 500 chars of reasoning for visibility
            reasoning_preview = reasoning[:500] + "..." if len(reasoning) > 500 else reasoning
            log.info(f"LLM reasoning:\n{reasoning_preview}")
        
        # Token accounting for the output
        output_tokens = count_tokens(full_output)
        tokens_used_session += call_input_tokens + output_tokens
        log.info(f"Used ~{output_tokens} output tokens; session total: {tokens_used_session}")

        user_hist_content = [text_segment] # Images are not saved in history
        chat_history.append({"role": "user", "content": user_hist_content})
        chat_history.append({"role": "assistant", "content": full_output})

        # Track whether summarization is needed (deferred until after action is sent)
        response_count += 1
        needs_summary = response_count >= CLEANUP_WINDOW

        # Extract analysis section
        match = ANALYSIS_RE.search(full_output)
        if match:
            analysis_text = match.group(1).strip()

        # NEW: Try semantic COMMAND format first
        command_seq = parse_command_from_llm_output(full_output)
        if command_seq and not command_seq.is_empty:
            log.info(f"Parsed semantic command sequence: {command_seq}")
            # We have a semantic command - will execute in the main loop with game_state
            # Store in a special variable for execution later
            semantic_action = command_seq
        else:
            semantic_action = None

        # Extract action JSON or fallback
        # First strip any leading/trailing quotes and whitespace
        cleaned_output = full_output.strip().strip('"').strip()

        # Try multiple patterns to find JSON (some models format differently)
        json_patterns = [
            r'(\{[\s\S]*?\})\s*$',  # JSON at end
            r'(\{[^}]+\})',  # Simple JSON anywhere
            r'(?:^|\n)(\{[^}]+\})',  # JSON on its own line
        ]

        json_match = None
        json_str = None
        for pattern in json_patterns:
            json_match = re.search(pattern, cleaned_output)
            if json_match:
                break
        if json_match:
            try:
                json_str = json_match.group(1)
                log.debug(f"Attempting to parse JSON: {json_str[:100]}...")
                parsed = json.loads(json_str)
                act = parsed.get("action")
                if isinstance(act, str):
                    act = _MODEL_TOKEN_RE.sub('', act).strip()
                touch = parsed.get("touch")
                if isinstance(act, str) and ACTION_RE.match(act):
                    action = act
                    log.debug(f"Extracted action from JSON: {action}")
                elif isinstance(touch, str) and COORD_RE.match(touch):
                    # Touch coordinates not used in Fire Emblem
                    log.debug("Ignoring touch coordinates for Fire Emblem")
                    action = None
            except json.JSONDecodeError as e:
                log.warning(f"Failed to parse JSON for action: {e}")
                log.debug(f"JSON string was: {json_str[:200]}...")

        # Fallback: last line matching ACTION_RE or COORD_RE
        if action is None:
            lines = [line.strip() for line in full_output.splitlines() if line.strip()]

            # Look for ACTION: prefix format (new streaming format)
            # Also handles markdown heading prefixes like "## ACTION:" or "### ACTION:"
            for line in lines:
                # Strip markdown heading prefixes (##, ###, etc.)
                clean_line = line.lstrip('#').strip()
                if clean_line.startswith("ACTION:"):
                    action_candidate = _MODEL_TOKEN_RE.sub('', clean_line[7:]).strip()
                    if ACTION_RE.match(action_candidate):
                        action = action_candidate
                        log.debug(f"Extracted action from ACTION: prefix: {action}")
                        break

            # Fallback to old format (last line is action)
            if action is None and lines:
                last = lines[-1]
                # Remove markdown prefixes, quotes, and model-specific tokens
                last = _MODEL_TOKEN_RE.sub('', last.lstrip('#').strip().strip('"')).strip()
                # plain "action" string
                if ACTION_RE.match(last) and not last.startswith('{'):
                    action = last
                    log.debug(f"Extracted action from plain text (legacy): {action}")

                # plain touch coords - not used in Fire Emblem
                elif COORD_RE.match(last):
                    log.debug("Ignoring touch coordinates for Fire Emblem")
                    action = None

    except Exception as e:
        error_str = str(e)
        # Detect context-too-long errors and retry with minimal context
        if "maximum context length" in error_str or "input_tokens" in error_str:
            log.warning(f"API rejected: context too long. Emergency retry with minimal context.")
            try:
                # Keep only system prompt, strip payload
                chat_history[:] = [chat_history[0]]
                _emergency_trim_payload(payload)
                text_segment = {"type": "text", "text": json.dumps(payload)}
                # Keep only screenshot, drop other images for retry
                retry_images = image_parts_for_api[:1] if image_parts_for_api else []
                retry_content = [text_segment] + retry_images
                retry_user_msg = {"role": "user", "content": retry_content}
                kwargs["messages"] = [chat_history[0], retry_user_msg]
                kwargs["stream"] = False  # simplify retry
                log.info("Retrying API call with emergency-trimmed context...")
                response = client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                if choice.message.content:
                    full_output = choice.message.content.strip()
                    output_tokens = count_tokens(full_output)
                    tokens_used_session += calculate_prompt_tokens(kwargs["messages"]) + output_tokens
                    chat_history.append({"role": "user", "content": [text_segment]})
                    chat_history.append({"role": "assistant", "content": full_output})
                    response_count += 1
                    needs_summary = response_count >= CLEANUP_WINDOW
                    # Extract action from retry output
                    match = ANALYSIS_RE.search(full_output)
                    if match:
                        analysis_text = match.group(1).strip()
                    json_match = re.search(r'(\{[^}]+\})', full_output)
                    if json_match:
                        try:
                            parsed = json.loads(json_match.group(1))
                            act = parsed.get("action")
                            if isinstance(act, str):
                                act = _MODEL_TOKEN_RE.sub('', act).strip()
                            if isinstance(act, str) and ACTION_RE.match(act):
                                action = act
                        except json.JSONDecodeError:
                            pass
                    if action is None:
                        for line in full_output.splitlines():
                            clean = line.lstrip('#').strip()
                            if clean.startswith("ACTION:"):
                                candidate = _MODEL_TOKEN_RE.sub('', clean[7:]).strip()
                                if ACTION_RE.match(candidate):
                                    action = candidate
                                    break
                    log.info(f"Emergency retry succeeded. Action: {action}")
                else:
                    log.error("Emergency retry returned empty content.")
                    return None, None, False, None
            except Exception as retry_e:
                log.error(f"Emergency retry also failed: {retry_e}", exc_info=True)
                return None, None, False, None
        else:
            log.error(f"Error during LLM interaction: {e}", exc_info=True)
            return None, None, False, None

    # Final fallback: search for action pattern in quotes or JSON anywhere
    if action is None:
        # Look for {"action":"XXX"} pattern anywhere in output
        action_json_match = re.search(r'\{"action"\s*:\s*"([^"]+)"\}', full_output)
        if action_json_match:
            potential_action = action_json_match.group(1)
            if ACTION_RE.match(potential_action):
                action = potential_action
                log.debug(f"Extracted action from inline JSON: {action}")

    # Only log error if BOTH action AND semantic_action are None
    if action is None and (semantic_action is None or semantic_action.is_empty):
        log.error("No valid action extracted from LLM output.")
        # Check if the output was likely truncated
        if len(full_output) > 2000 or not full_output.rstrip().endswith('}'):
            log.warning("Output may have been truncated due to token limit. Consider shorter action sequences.")
        # Try to extract partial action from truncated JSON
        partial_action_match = re.search(r'"action"\s*:\s*"([LRUDABS;]+)', full_output)
        if partial_action_match:
            potential_action = partial_action_match.group(1)
            # Clean up and validate partial action
            if ';' in potential_action:
                # Take only the complete action commands (before any incomplete one)
                parts = potential_action.split(';')
                complete_parts = [p for p in parts[:-1] if p in 'LRUDABS']
                if complete_parts:
                    action = ';'.join(complete_parts) + ';'
                    log.warning(f"Extracted partial action from truncated output: {action}")

        if action is None:
            log.debug(f"Full output was: {full_output[:500]}...")
            log.debug(f"Output end: ...{full_output[-200:] if len(full_output) > 200 else full_output}")

    return action, analysis_text, needs_summary, semantic_action



async def run_auto_loop(sock, state: dict, broadcast_func, interval: float = 8.0, max_loops = math.inf, benchmark: Benchmark = None):
    """Main async loop: Get state, call LLM, send action, update/broadcast state."""
    global action_count, tokens_used_session, start_time, chat_history, SCREENSHOT_PATH, MINIMAP_PATH, SAVED_SCREENSHOT_PATH, SAVED_MINIMAP_PATH, _last_action_sent, _last_game_state, _failed_tiles, _current_cycle_num, _dialogue_buffer, _unit_attempt_tracker

    b64_mm = None

    # Reset action tracking state for new session
    _last_action_sent = None
    _last_game_state = None
    _last_action_type = None
    _failed_tiles = {}
    _unit_attempt_tracker = {}
    _dialogue_buffer = []
    _current_cycle_num = 0

    # Initialize session - clears old screenshots and creates new session ID
    session_id = session_manager.startup()
    memory_manager.start_session(session_id)
    state['session_id'] = session_id
    log.info(f"Started new session: {session_id}")

    # Broadcast session start
    await broadcast_func({
        "type": "session_start",
        "payload": {"session_id": session_id, "start_time": datetime.datetime.now().isoformat()}
    })

    # Wire up memory broadcast callback if persistent learning is enabled
    if config.PERSISTENT_LEARNING and knowledge_base:
        def memory_broadcast(text: str):
            asyncio.create_task(broadcast_func({
                "type": "memory_write",
                "payload": {"text": text}
            }))
        knowledge_base.set_memory_callback(memory_broadcast)

    benchInstructions = ""
    if benchmark is not None:
        benchInstructions = benchmark.instructions
        logging.info(f"Added bench instructions: {benchInstructions}")

    # Build initial system prompt (will be updated with memory context each turn)
    initial_prompt = create_enhanced_prompt_system(
        knowledge_base=None,
        observation="",
        game_state={"action_summary": "", "benchmark_instruction": benchInstructions}
    )

    chat_history = [{"role": "system", "content": initial_prompt}]

    while action_count < max_loops:
        loop_start_time = time.time()
        current_cycle = action_count + 1
        _current_cycle_num = current_cycle
        log.info(f"--- Loop Cycle {current_cycle} ---")

        update_payload = {}
        action_payload = {}

        try:
            log.info("Requesting game state from mGBA...")
            # Capture multiple screenshots for comparison
            from src.utils.image_utils import capture
            from src.utils.screenshot_analyzer import compare_screenshots
            import time as t

            screenshots = []
            for i in range(config.SCREENSHOT_CAPTURE_COUNT):
                screenshot_name = f"screenshot_{i}.png"
                capture(sock, screenshot_name)
                screenshots.append(screenshot_name)
                if i < config.SCREENSHOT_CAPTURE_COUNT - 1:
                    t.sleep(2.0)

            log.info(f"Captured {len(screenshots)} screenshots for analysis")

            # Analyze screenshots to detect transitions and black screens
            analysis = compare_screenshots(screenshots)

            # Use the best screenshot (non-black, stable frame)
            import shutil
            best_screenshot = screenshots[analysis["best_index"]]
            # Make sure target directory exists (defensive)
            try:
                os.makedirs(os.path.dirname(SAVED_SCREENSHOT_PATH), exist_ok=True)
            except Exception:
                pass
            shutil.copy(best_screenshot, SAVED_SCREENSHOT_PATH)

            log.info(f"Screenshot analysis: Best={analysis['best_index']}, Black screens={analysis['black_screens']}, Transitioning={analysis['is_transitioning']}")

            # Detect text box (dialogue) at bottom of screenshot
            text_box_visible = False
            if config.TEXT_BOX_DETECTION_ENABLED and not analysis["is_transitioning"]:
                from src.utils.screenshot_analyzer import detect_text_box
                try:
                    text_box_visible = detect_text_box(
                        SAVED_SCREENSHOT_PATH,
                        bottom_rows_px=config.TEXT_BOX_BOTTOM_PX,
                        dark_threshold=config.TEXT_BOX_DARK_THRESHOLD,
                        contrast_threshold=config.TEXT_BOX_CONTRAST_THRESHOLD,
                        top_min_brightness=config.TEXT_BOX_TOP_MIN_BRIGHTNESS,
                    )
                    if text_box_visible:
                        log.info("Text box detected at bottom of screenshot")
                except Exception as e:
                    log.warning(f"Text box detection failed: {e}")

            # Detect flashing/animated tiles across the captured frames
            # Only run flash detection if tutorial mode is enabled (for tutorial highlights)
            flash_indicators = []
            if config.TUTORIAL_MODE and config.FLASH_DETECTION_ENABLED and not analysis["is_transitioning"]:
                from src.utils.screenshot_analyzer import detect_flash_regions
                try:
                    flash_indicators = detect_flash_regions(
                        screenshots,
                        diff_threshold=config.FLASH_DIFF_THRESHOLD,
                        min_tile_ratio=config.FLASH_MIN_TILE_RATIO,
                        exclude_top_rows=config.FLASH_EXCLUDE_TOP_ROWS,
                    )
                    if flash_indicators:
                        log.info(f"Flash detection: {len(flash_indicators)} regions: "
                                 f"{[(f['screen_tile'], f['type']) for f in flash_indicators]}")
                except Exception as e:
                    log.warning(f"Flash detection failed: {e}")

            # Detect blue (movement) and red (attack) tile overlays
            movement_tiles = {"blue_tiles": [], "red_tiles": []}
            if config.MOVEMENT_TILE_DETECTION and not analysis["is_transitioning"]:
                from src.utils.screenshot_analyzer import detect_movement_tiles
                try:
                    movement_tiles = detect_movement_tiles(
                        screenshots,
                        blue_threshold=config.MOVEMENT_BLUE_THRESHOLD,
                        red_threshold=config.MOVEMENT_RED_THRESHOLD,
                        exclude_top_rows=config.FLASH_EXCLUDE_TOP_ROWS,
                    )
                    if movement_tiles["blue_tiles"] or movement_tiles["red_tiles"]:
                        log.info(f"Movement tile detection: {len(movement_tiles['blue_tiles'])} blue, "
                                 f"{len(movement_tiles['red_tiles'])} red")
                except Exception as e:
                    log.warning(f"Movement tile detection failed: {e}")

            # If we're in a transition, wait a bit and try again
            if analysis["is_transitioning"]:
                log.info("Detected screen transition, waiting for stable frame...")
                await asyncio.sleep(1.0)
                # Take one more screenshot after waiting
                capture(sock, SAVED_SCREENSHOT_PATH)
                log.debug("Captured post-transition screenshot")

            current_mGBA_state = prep_llm(sock)

            if benchmark is not None:
                # check if we complted the bench
                if(benchmark.validation(current_mGBA_state)):
                    break

            #print(str(current_mGBA_state))
            if not current_mGBA_state:
                log.error("Failed to get state from mGBA (prep_llm returned None). Skipping.")
                await asyncio.sleep(max(0, interval - (time.time() - loop_start_time)))
                continue
            log.info("Received game state from mGBA.")
            
            # Log key game state for visibility
            if current_mGBA_state:
                phase = current_mGBA_state.get("phase", "unknown")
                chapter = current_mGBA_state.get("chapter", "?")
                turn = current_mGBA_state.get("turn", "?")
                cursor = current_mGBA_state.get("cursor", (0, 0))
                cursor_on = current_mGBA_state.get("cursor_on_player", "none")
                menu_in = current_mGBA_state.get("in_menu", False)
                menu_sel = current_mGBA_state.get("menu_selection", -1)
                menu_lbl = current_mGBA_state.get("menu_selection_label", "")
                log.info(f"Game State: Ch{chapter} Turn{turn} Phase:{phase} Cursor:{cursor} On:{cursor_on} Menu:{menu_in}({menu_sel}{menu_lbl})")
        except socket.timeout:
             log.warning("Socket timeout getting state from mGBA (game may be in transition). Retrying next cycle.")
             await asyncio.sleep(2)
             continue
        except socket.error as se:
             log.error(f"Socket error getting state from mGBA: {se}. Stopping loop.")
             break
        except Exception as e:
            log.error(f"Error getting state from mGBA: {e}", exc_info=True)
            await asyncio.sleep(max(0, interval - (time.time() - loop_start_time)))
            continue


        llm_input_state = copy.deepcopy(current_mGBA_state)

        # Inject previous action result for LLM feedback
        if _last_action_type and _last_action_sent and _last_game_state:
            action_result = capture_action_result(
                _last_action_type,
                _last_action_sent,
                _last_game_state,
                current_mGBA_state,
            )
            llm_input_state["action_result"] = action_result
            log.info(f"Action result: success={action_result.get('success')}, msg={action_result.get('message', '')[:40]}")

        # Inject screen context from state-machine inference
        _input_locked = bool(current_mGBA_state.get("input_locked"))
        screen_context = _infer_screen_context(
            current_mGBA_state, _last_action_sent, _last_game_state,
            text_box_visible=text_box_visible, input_locked=_input_locked,
        )
        llm_input_state["previous_action"] = screen_context["previous_action"]
        llm_input_state["screen_context"] = screen_context["screen_context"]
        if config.CONTEXT_HINTS_ENABLED and screen_context["context_hints"]:
            llm_input_state["context_hints"] = screen_context["context_hints"]
        if screen_context.get("failed_tiles"):
            llm_input_state["failed_tiles"] = screen_context["failed_tiles"]

        # Inject dialogue/text detection signals
        llm_input_state["text_box_visible"] = text_box_visible
        # Only add input_locked if text_box is visible (avoid false positives)
        # This prevents confusing hints when game is actually responsive
        if _input_locked and text_box_visible:
            llm_input_state["input_locked"] = True
        if current_mGBA_state.get("display_cursor"):
            llm_input_state["display_cursor"] = current_mGBA_state["display_cursor"]
        if current_mGBA_state.get("tutorial_target"):
            llm_input_state["tutorial_target"] = current_mGBA_state["tutorial_target"]
        
        # Inject menu state for action menu navigation
        if current_mGBA_state.get("in_menu"):
            llm_input_state["in_menu"] = True
            llm_input_state["menu_selection"] = current_mGBA_state.get("menu_selection", -1)
            llm_input_state["menu_selection_label"] = current_mGBA_state.get("menu_selection_label", "Unknown")
            if current_mGBA_state.get("menu_type"):
                llm_input_state["menu_type"] = current_mGBA_state["menu_type"]
            if current_mGBA_state.get("menu_options"):
                llm_input_state["menu_options"] = current_mGBA_state["menu_options"]
            log.info(f"Menu state: type={current_mGBA_state.get('menu_type')}, selection={current_mGBA_state.get('menu_selection')} ({current_mGBA_state.get('menu_selection_label')})")

        # Inject flash indicators with estimated map positions
        # Filter out highlight_area (HUD noise) — only keep cursor_indicator
        if flash_indicators and current_mGBA_state:
            cursor = current_mGBA_state.get("cursor")
            useful_indicators = [ind for ind in flash_indicators if ind.get("type") == "cursor_indicator"]
            if useful_indicators and cursor:
                from src.utils.screenshot_analyzer import screen_tile_to_map_estimate
                _cam = current_mGBA_state.get("camera")
                _cam_x = _cam[0] if _cam else None
                _cam_y = _cam[1] if _cam else None
                for ind in useful_indicators:
                    sx, sy = ind["screen_tile"]
                    est_x, est_y = screen_tile_to_map_estimate(
                        sx, sy, cursor[0], cursor[1],
                        camera_x=_cam_x, camera_y=_cam_y,
                    )
                    ind["estimated_map_pos"] = [est_x, est_y]
                    ind["note"] = "Flashing tile detected - may indicate where the game wants you to move"
                # Cross-reference flash targets against known-bad tiles
                for ind in useful_indicators:
                    est = ind.get("estimated_map_pos")
                    if est and _check_tile_known_bad(est[0], est[1]):
                        bad = _failed_tiles[tuple(est)]
                        ind["warning"] = (
                            f"SUSPECT: Tile {est} failed {bad['count']} times before. "
                            f"This flash indicator may be wrong — try a different target."
                        )
                        log.info(f"Flash indicator at {est} flagged as suspect (failed {bad['count']}x)")

                llm_input_state["flash_indicators"] = useful_indicators
            elif not useful_indicators:
                log.debug(f"Flash detection: filtered out {len(flash_indicators)} highlight_area indicators (HUD noise)")

        # Inject movement/attack tile data with map coordinates
        if movement_tiles and (movement_tiles["blue_tiles"] or movement_tiles["red_tiles"]) and current_mGBA_state:
            cursor = current_mGBA_state.get("cursor")
            if cursor:
                from src.utils.screenshot_analyzer import screen_tile_to_map_estimate
                _cam = current_mGBA_state.get("camera")
                _cam_x = _cam[0] if _cam else None
                _cam_y = _cam[1] if _cam else None

                if movement_tiles["blue_tiles"]:
                    blue_map = []
                    for sx, sy in movement_tiles["blue_tiles"]:
                        mx, my = screen_tile_to_map_estimate(
                            sx, sy, cursor[0], cursor[1], camera_x=_cam_x, camera_y=_cam_y)
                        blue_map.append([mx, my])
                    # Cap at 20 tiles (sorted by distance from cursor) to limit token usage
                    blue_map.sort(key=lambda t: abs(t[0] - cursor[0]) + abs(t[1] - cursor[1]))
                    llm_input_state["movement_tiles"] = blue_map[:20]
                    # Also add to current_mGBA_state so capture_action_result() can see them
                    current_mGBA_state["movement_tiles"] = blue_map[:20]
                    current_mGBA_state["unit_is_selected"] = True
                    llm_input_state["unit_is_selected"] = True  # Blue tiles = unit is selected
                    # Add selected_unit if we know which unit is selected (from cursor)
                    unit_at_cursor = current_mGBA_state.get("cursor_on_player")
                    if unit_at_cursor:
                        llm_input_state["selected_unit"] = unit_at_cursor

                # Also store red tiles (blocked tiles) in current_mGBA_state
                if movement_tiles["red_tiles"]:
                    red_map = []
                    for sx, sy in movement_tiles["red_tiles"]:
                        mx, my = screen_tile_to_map_estimate(
                            sx, sy, cursor[0], cursor[1], camera_x=_cam_x, camera_y=_cam_y)
                        red_map.append([mx, my])
                    current_mGBA_state["blocked_tiles"] = red_map

                # RED tiles = blocked/unwalkable (walls, other units, out of range)
                # NOT attackable - do NOT map to attack_tiles
                # Use attack_opportunities for actual attack options instead

                # Systematic retry: suggest untried blue tiles when stuck
                if config.CONTEXT_HINTS_ENABLED and movement_tiles["blue_tiles"] and _failed_tiles:
                    untried = []
                    for tile_pos in llm_input_state.get("movement_tiles", []):
                        mx, my = tile_pos
                        if not _check_tile_known_bad(mx, my):
                            dist = abs(mx - cursor[0]) + abs(my - cursor[1])
                            untried.append({"tile": [mx, my], "distance": dist})
                    tried_count = len(llm_input_state.get("movement_tiles", [])) - len(untried)
                    if untried and tried_count > 0:
                        untried.sort(key=lambda t: t["distance"])
                        closest = untried[0]["tile"]
                        hint = (
                            f"SYSTEMATIC RETRY: {tried_count} blue tiles already failed. "
                            f"{len(untried)} untried remain. Closest untried: ({closest[0]},{closest[1]}). "
                            f"Navigate there instead."
                        )
                        llm_input_state.setdefault("context_hints", []).append(hint)

        # Compute attack opportunities: blue tiles adjacent to enemies
        if llm_input_state.get("movement_tiles") and llm_input_state.get("enemies"):
            blue_set = set(tuple(t) for t in llm_input_state["movement_tiles"])
            attack_opps = []
            for enemy in llm_input_state["enemies"]:
                ex, ey = enemy.get("x"), enemy.get("y")
                if ex is None or ey is None:
                    continue
                # Check 4-directional adjacency (attack range 1)
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    adj = (ex + dx, ey + dy)
                    if adj in blue_set:
                        attack_opps.append({
                            "move_to": list(adj),
                            "target": enemy.get("name", "Enemy"),
                            "enemy_at": [ex, ey],
                        })
            if attack_opps:
                # Prioritize untried tiles: sort so that non-failed tiles come first
                untried_opps = [o for o in attack_opps if not _check_tile_known_bad(o["move_to"][0], o["move_to"][1])]
                tried_opps = [o for o in attack_opps if _check_tile_known_bad(o["move_to"][0], o["move_to"][1])]
                sorted_opps = untried_opps + tried_opps  # untried first
                llm_input_state["attack_opportunities"] = sorted_opps[:5]
                cursor = current_mGBA_state.get("cursor")
                if config.CONTEXT_HINTS_ENABLED and cursor and sorted_opps:
                    # Build hint listing ALL viable attack positions in priority order
                    attack_hint = (
                        f"ATTACK NOW: Move NEXT TO an enemy and press A; to confirm. "
                        f"Try these positions IN ORDER (untried first):"
                    )
                    for i, opp in enumerate(sorted_opps[:4]):
                        dx = opp["move_to"][0] - cursor[0]
                        dy = opp["move_to"][1] - cursor[1]
                        dir_parts = []
                        if dx < 0: dir_parts.extend(["L"] * (-dx))
                        elif dx > 0: dir_parts.extend(["R"] * dx)
                        if dy < 0: dir_parts.extend(["U"] * (-dy))
                        elif dy > 0: dir_parts.extend(["D"] * dy)
                        nav = ";".join(dir_parts) + ";A;" if dir_parts else "A;"
                        failed_marker = " (FAILED BEFORE)" if _check_tile_known_bad(opp["move_to"][0], opp["move_to"][1]) else ""
                        first_marker = " ← TRY THIS" if i == 0 else ""
                        attack_hint += (
                            f"\n  {i+1}. ({opp['move_to'][0]},{opp['move_to'][1]}) → attack "
                            f"{opp['target']} at ({opp['enemy_at'][0]},{opp['enemy_at'][1]}) "
                            f"→ {nav}{failed_marker}{first_marker}"
                        )
                    llm_input_state.setdefault("context_hints", []).append(attack_hint)
                    best = sorted_opps[0]
                    log.info(f"Attack opportunity: move to {best['move_to']} → attack {best['target']} at {best['enemy_at']}")

        # Even without movement tiles, inject attack direction hint when unit is selected
        elif (config.CONTEXT_HINTS_ENABLED and llm_input_state.get("enemies") and current_mGBA_state.get("cursor") and
              "UNIT SELECTED" in llm_input_state.get("screen_context", "")):
            cursor = current_mGBA_state["cursor"]
            nearest = min(
                llm_input_state["enemies"],
                key=lambda e: abs(e.get("x", 99) - cursor[0]) + abs(e.get("y", 99) - cursor[1])
            )
            ex, ey = nearest.get("x", 99), nearest.get("y", 99)
            dist = abs(ex - cursor[0]) + abs(ey - cursor[1])
            if dist <= 10:
                # Get valid movement tiles to filter suggestions
                movement_tiles = llm_input_state.get("movement_tiles", [])
                blue_set = set(tuple(t) for t in movement_tiles) if movement_tiles else set()
                
                # Compute ALL adjacent tiles, sorted by distance, filtered by failures
                adj_tiles = [(ex - 1, ey), (ex + 1, ey), (ex, ey - 1), (ex, ey + 1)]
                adj_tiles.sort(key=lambda t: abs(t[0] - cursor[0]) + abs(t[1] - cursor[1]))
                
                # Filter to only valid movement tiles if available
                if blue_set:
                    adj_tiles = [t for t in adj_tiles if t in blue_set]
                    if not adj_tiles:
                        log.debug("No adjacent tiles in movement_tiles - skipping attack hints")
                        # Don't add hint if no valid tiles
                        skip_attack_hint = True
                    else:
                        skip_attack_hint = False
                else:
                    skip_attack_hint = False
                
                if not skip_attack_hint:
                    untried_adj = [t for t in adj_tiles if not _check_tile_known_bad(t[0], t[1])]
                    if not untried_adj:
                        untried_adj = adj_tiles  # fallback: show all
                    # Build hint listing ALL options in priority order
                    attack_hint = (
                        f"ATTACK TARGET: {nearest.get('name','Enemy')} is at ({ex},{ey}). "
                        f"Move NEXT TO the enemy (not onto it). Try these tiles IN ORDER:"
                    )
                    for i, t in enumerate(untried_adj):
                        dx, dy = t[0] - cursor[0], t[1] - cursor[1]
                        nav = []
                        if dx < 0: nav.extend(["L"] * (-dx))
                        elif dx > 0: nav.extend(["R"] * dx)
                        if dy < 0: nav.extend(["U"] * (-dy))
                        elif dy > 0: nav.extend(["D"] * dy)
                        nav_str = ";".join(nav) + ";A;" if nav else "A;"
                        marker = " ← TRY THIS FIRST" if i == 0 else ""
                        attack_hint += f"\n  {i+1}. ({t[0]},{t[1]}) → {nav_str}{marker}"
                    llm_input_state.setdefault("context_hints", []).append(attack_hint)

        # Seize objective hint when no enemies remain and unit is selected
        elif (config.CONTEXT_HINTS_ENABLED and not llm_input_state.get("enemies") and
              current_mGBA_state.get("objective_type") == "seize" and
              "UNIT SELECTED" in llm_input_state.get("screen_context", "")):
            seize_pos = current_mGBA_state.get("seize_position")
            cursor = current_mGBA_state.get("cursor")
            if seize_pos and cursor:
                sx, sy = seize_pos
                dx, dy = sx - cursor[0], sy - cursor[1]
                nav = []
                if dx < 0: nav.extend(["L"] * (-dx))
                elif dx > 0: nav.extend(["R"] * dx)
                if dy < 0: nav.extend(["U"] * (-dy))
                elif dy > 0: nav.extend(["D"] * dy)
                nav_str = ";".join(nav) + ";A;" if nav else "A;"
                llm_input_state.setdefault("context_hints", []).append(
                    f"SEIZE TARGET: Gate/throne is at ({sx},{sy}). "
                    f"Navigate there and press A; to confirm. Suggested: {nav_str}"
                )
                log.info(f"Seize hint: move to ({sx},{sy}) from cursor {cursor}")
            else:
                llm_input_state.setdefault("context_hints", []).append(
                    "ALL ENEMIES DEFEATED! Objective: SEIZE. Look at the screenshot for the "
                    "gate/throne tile (where the boss was). Move there, press A;, then select 'Seize'."
                )

        state_update_start = time.time()


        new_team = current_mGBA_state.get('party')
        if new_team is not None and json.dumps(new_team) != json.dumps(state.get('currentTeam')):
            state['currentTeam'] = new_team
            update_payload['currentTeam'] = state['currentTeam']
            log.info("State Update: currentTeam")


        # Only update location if internal mapping is enabled
        if USE_INTERNAL_MAPPING:
            pos = current_mGBA_state.get('position')
            map_id = current_mGBA_state.get('map_id', 'N/A')
            map_name = current_mGBA_state.get('map_name', '')
            loc_str = "Unknown"
            if pos:
                loc_str = f"{map_name} (Map {map_id}) ({pos[0]}, {pos[1]})" if map_name else f"Map {map_id} ({pos[0]}, {pos[1]})"
            if loc_str != state.get('minimapLocation'):
                state['minimapLocation'] = loc_str
                update_payload['minimapLocation'] = state['minimapLocation']
                log.info(f"State Update: minimapLocation -> {loc_str}")
        else:
            # Set location to unknown when internal mapping is disabled
            if state.get('minimapLocation') != 'Screenshot Only Mode':
                state['minimapLocation'] = 'Screenshot Only Mode'
                update_payload['minimapLocation'] = state['minimapLocation']

        # Only combine images if both features are enabled
        if ONE_IMAGE_PER_PROMPT and FEATURE_MINIMAP_ENABLED and USE_INTERNAL_MAPPING:
            try:
                # Check if minimap file exists and is not empty
                if not os.path.exists(SAVED_MINIMAP_PATH) or os.path.getsize(SAVED_MINIMAP_PATH) == 0:
                    log.debug("Minimap file is empty or missing, skipping combination")
                else:
                    # Load images
                    ss_img = Image.open(SAVED_SCREENSHOT_PATH)
                    mm_img = Image.open(SAVED_MINIMAP_PATH)

                    # Resize minimap to match screenshot height
                    mm_ratio = ss_img.height / mm_img.height
                    new_mm_width = int(mm_img.width * mm_ratio)
                    mm_img = mm_img.resize((new_mm_width, ss_img.height), Image.LANCZOS)

                    # Create a new canvas wide enough for both
                    combined_width = ss_img.width + mm_img.width
                    combined = Image.new('RGB', (combined_width, ss_img.height))

                    # Paste screenshot at (0,0), minimap at (ss.width, 0)
                    combined.paste(ss_img, (0, 0))
                    combined.paste(mm_img, (ss_img.width, 0))

                    # Save combined image and override SCREENSHOT_PATH
                    combined_path = os.path.splitext(SAVED_SCREENSHOT_PATH)[0] + '_with_minimap.png'
                    combined.save(combined_path)
                    SCREENSHOT_PATH = combined_path

                    log.info(f"Combined screenshot + minimap saved to {combined_path}")
            except Exception as e:
                log.error(f"Failed to combine minimap: {e}")

        b64_ss = encode_image_base64(SCREENSHOT_PATH)
        vision_description = None
        if b64_ss:
            # If we have a vision model, get text descriptions instead of sending images
            if vision_client and vision_model:
                screenshot_desc = get_image_description(b64_ss, "screenshot")
                if screenshot_desc:
                    # Log the vision model's raw interpretation
                    log.info(f"Vision model interpretation (first 200 chars): {screenshot_desc[:200]}...")

                    # Detect game phase from vision description.
                    phase = detect_game_phase(screenshot_desc)

                    # Update knowledge base if enabled
                    if config.PERSISTENT_LEARNING and knowledge_base:
                        knowledge_base.update_battle_state({"vision": screenshot_desc, "phase": phase})

                    # Add phase context to the description
                    enhanced_desc = f"{screenshot_desc}\n\nPHASE: {phase}"

                    llm_input_state["screenshot_description"] = enhanced_desc
                    llm_input_state["screenshot"] = None  # Don't send image to text-only model
                    vision_description = enhanced_desc  # Store for WebSocket broadcast

                    # Capture dialogue instructions for persistence across cycles
                    if text_box_visible and vision_description:
                        party_names = [u.get("name", "") for u in llm_input_state.get("party", [])]
                        instruction = extract_dialogue_instruction(vision_description, party_names)
                        if instruction:
                            instruction["cycle"] = current_cycle
                            _dialogue_buffer.append(instruction)
                            # Trim to max size
                            while len(_dialogue_buffer) > _DIALOGUE_BUFFER_MAX:
                                _dialogue_buffer.pop(0)
                            log.info(f"Dialogue instruction captured: {instruction['instruction_type']} "
                                     f"units={instruction['unit_names']}")

                    log.info(f"PHASE DETECTED: {phase.upper()}")
                else:
                    # Fallback: try to send image anyway (might error)
                    llm_input_state["screenshot"] = {"image_url": {"url": f"data:image/png;base64,{b64_ss}", "detail": IMAGE_DETAIL}}
            else:
                # No vision model, send image directly to main model
                llm_input_state["screenshot"] = {"image_url": {"url": f"data:image/png;base64,{b64_ss}", "detail": IMAGE_DETAIL}}
        else:
            llm_input_state["screenshot"] = None

        # Only handle separate minimap if enabled
        if not ONE_IMAGE_PER_PROMPT and FEATURE_MINIMAP_ENABLED and USE_INTERNAL_MAPPING:
            b64_mm = encode_image_base64(MINIMAP_PATH)
            if b64_mm:
                # If we have a vision model, get text descriptions instead of sending images
                if vision_client and vision_model:
                    minimap_desc = get_image_description(b64_mm, "minimap")
                    if minimap_desc:
                        llm_input_state["minimap_description"] = minimap_desc
                        llm_input_state["minimap"] = None  # Don't send image to text-only model
                    else:
                        # Fallback: try to send image anyway (might error)
                        llm_input_state["minimap"] = {"image_url": {"url": f"data:image/png;base64,{b64_mm}", "detail": IMAGE_DETAIL}}
                else:
                    # No vision model, send image directly to main model
                    llm_input_state["minimap"] = {"image_url": {"url": f"data:image/png;base64,{b64_mm}", "detail": IMAGE_DETAIL}}
            else:
                llm_input_state["minimap"] = None

        log.info(f"Pre-LLM state update & image prep took {time.time() - state_update_start:.2f}s. SS:{bool(b64_ss)}, MM:{bool(b64_mm)}")

        # Build memory-aware system prompt with context from past turns
        memory_window_text = memory_manager.format_for_llm()
        session_stats = memory_manager.get_pattern_stats(vision_description or "")

        # Update system prompt with memory context
        # Get game info for prompt parameterization
        _game_title = ""
        _lord_names = None
        if current_mGBA_state:
            _game_title = current_mGBA_state.get("game_title", "")
            from src.utils.memory_reader import get_memory_reader as _get_reader
            _reader = _get_reader()
            if _reader:
                _lord_names = _reader.game.lord_names

        memory_system_prompt = build_memory_aware_prompt(
            memory_window_text=memory_window_text,
            session_stats=session_stats,
            benchmark_instruction=benchInstructions,
            game_title=_game_title,
            lord_names=_lord_names,
        )
        chat_history[0] = {"role": "system", "content": memory_system_prompt}

        # Add memory thumbnails to LLM input
        memory_thumbnails = memory_manager.get_thumbnails_for_api(count=config.MEMORY_THUMBNAIL_COUNT)
        if memory_thumbnails:
            llm_input_state["memory_thumbnails"] = memory_thumbnails

        # Send vision description to frontend if available
        if vision_description:
            await broadcast_func({
                "type": "vision_update",
                "payload": {"description": vision_description, "processing": False}
            })
        else:
            # Send processing state when starting to get vision description
            await broadcast_func({
                "type": "vision_status",
                "payload": {"processing": True}
            })

        log_id_counter = state.get("log_id_counter", 0) + 1
        state["log_id_counter"] = log_id_counter

        # Broadcast AI processing start
        await broadcast_func({
            "type": "ai_processing",
            "payload": {"status": "thinking", "model": MODEL}
        })

        # Apply token compaction if needed before LLM call
        # Build temporary messages list to check token count
        temp_messages = chat_history + [{"role": "user", "content": [{"type": "text", "text": json.dumps(llm_input_state)}]}]
        _, chat_history, thumbnail_count = compact_context_to_budget(
            temp_messages, chat_history, memory_manager
        )

        # Update memory thumbnails with compacted count
        if thumbnail_count != config.MEMORY_THUMBNAIL_COUNT:
            memory_thumbnails = memory_manager.get_thumbnails_for_api(count=thumbnail_count)
            if memory_thumbnails:
                llm_input_state["memory_thumbnails"] = memory_thumbnails
            else:
                llm_input_state.pop("memory_thumbnails", None)

        # Call LLM for decision
        action, game_analysis, needs_summary, semantic_action = await call_llm_with_timeout(llm_input_state, benchmark=benchmark)

        # NEW: Try semantic command execution first
        action_to_send = None
        action_description = None
        if semantic_action and not semantic_action.is_empty:
            log.info(f"Executing semantic command: {semantic_action}")
            buttons, desc, success = execute_with_validation(semantic_action, current_mGBA_state)
            if success:
                action_to_send = buttons
                action_description = desc
                # Track action type for result capture
                if semantic_action.commands:
                    _last_action_type = semantic_action.commands[0].type
                log.info(f"Semantic command translated to: {buttons}")
            else:
                log.warning(f"Semantic command validation failed: {desc}")
                action_description = desc

        # Fall back to legacy button action if no semantic action
        if not action_to_send and action:
            # Enforce hard cap on action length
            parts = action.rstrip(';').split(';')
            if len(parts) > config.MAX_ACTION_BUTTONS:
                log.warning(f"Action truncated from {len(parts)} to {config.MAX_ACTION_BUTTONS} buttons")
                parts = parts[:config.MAX_ACTION_BUTTONS]
                action = ';'.join(parts) + ';'

            # Record action to memory manager for context in future turns
            memory_manager.add_entry(MemoryEntry(
                turn_id=current_cycle,
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                screen_description=vision_description[:config.MEMORY_DESCRIPTION_TRUNCATE] if vision_description else "",
                thumbnail_base64=memory_manager.generate_thumbnail(SAVED_SCREENSHOT_PATH),
                game_state={
                    "phase": current_mGBA_state.get("phase", "unknown"),
                    "chapter": current_mGBA_state.get("chapter", "unknown"),
                },
                ai_reasoning=game_analysis[:config.MEMORY_REASONING_TRUNCATE] if game_analysis else "",
                action_taken=action
            ))

            # Record action if learning is enabled
            if config.PERSISTENT_LEARNING and knowledge_base:
                knowledge_base.record_action(action, vision_description if vision_description else "")

            # Increment session action count
            session_manager.increment_actions()

            action_to_send = action
            action_description = f"Action: {action}"
            log.info(f"LLM proposed action: {action}")

        # Broadcast AI processing complete
        await broadcast_func({
            "type": "ai_processing",
            "payload": {"status": "complete" if action_to_send else "error"}
        })

        if not action_to_send:
            log_action_text = "No action taken (LLM failed or semantic validation failed)."
        else:
            # Normalize button names (e.g., "R;R;D;A;" -> "RIGHT;RIGHT;DOWN;A;")
            action_to_send = normalize_button_sequence(action_to_send)
            log_action_text = f"Action: {action_description}" if action_description else f"Action: {action_to_send}"
            try:
                sock.sendall((action_to_send + "\n").encode("utf-8"))
                log.info(f"Action '{action_to_send}' sent to mGBA.")

                # Track action and state for next cycle's inference
                _last_action_sent = action_to_send
                _last_game_state = copy.deepcopy(current_mGBA_state)
            except socket.error as se:
                log.error(f"Socket error sending action '{action_to_send}': {se}. Stopping loop.")
                break
            except Exception as e:
                log.error(f"Unexpected error sending action '{action_to_send}': {e}", exc_info=True)

        # Deferred summarization — runs AFTER the action is sent to mGBA
        # so that the game doesn't stall waiting for the summary LLM call.
        if needs_summary:
            loop = asyncio.get_running_loop()
            summary_json = await loop.run_in_executor(
                None, functools.partial(summarize_and_reset, benchmark)
            )
            await asyncio.sleep(5)

            if summary_json is not None:
                await broadcast_func({
                    "type": "log_entry",
                    "payload": {"id": log_id_counter, "text": "Chat history cleaned up.", "category": "system"}
                })

                required = ("primaryGoal", "secondaryGoal", "tertiaryGoal", "otherNotes")

                if isinstance(summary_json, dict):
                    missing = [k for k in required if k not in summary_json]
                    if not missing:
                        state["goals"] = {
                            "primary":   summary_json["primaryGoal"],
                            "secondary": summary_json["secondaryGoal"],
                            "tertiary":  summary_json["tertiaryGoal"],
                        }
                        state["otherGoals"] = summary_json["otherNotes"]
                        update_payload["goals"] = state["goals"]
                        update_payload["otherGoals"] = state["otherGoals"]
                    else:
                        logging.error(f"Missing required goal keys in summary_json: {missing!r}")
                else:
                    logging.error(f"Expected summary_json to be dict, but got {type(summary_json).__name__!r}")

        action_count = current_cycle
        if state.get('actions') != action_count:
             state['actions'] = action_count
             update_payload['actions'] = action_count

        if state.get('tokensUsed') != tokens_used_session:
            state['tokensUsed'] = tokens_used_session
            update_payload['tokensUsed'] = tokens_used_session

        if state.get('inputTokens') != last_input_tokens:
            state['inputTokens'] = last_input_tokens
            update_payload['inputTokens'] = last_input_tokens

        elapsed = datetime.datetime.now() - start_time
        game_status_str = f"{int(elapsed.total_seconds() // 3600)}h {int((elapsed.total_seconds() % 3600) // 60)}m {int(elapsed.total_seconds() % 60)}s"
        if state.get('gameStatus') != game_status_str:
            state['gameStatus'] = game_status_str
            update_payload['gameStatus'] = game_status_str

        if state.get('modelName') != MODEL:
            state['modelName'] = MODEL
            update_payload['modelName'] = MODEL

        # Broadcast current objective from memory/chapter data.
        current_objective = current_mGBA_state.get("objective") if current_mGBA_state else None
        if current_objective and state.get('objective') != current_objective:
            state['objective'] = current_objective
            update_payload['objective'] = current_objective

        analysis_log_part = f"{game_analysis.strip()}\n" if game_analysis and game_analysis.strip() else None

        log.info(f"Log Entry #{log_id_counter}: {log_action_text}")

        # Broadcast state updates first
        if update_payload:
            log.info(f"Broadcasting {len(update_payload)} state updates: {list(update_payload.keys())}")
            try:
                await broadcast_func({"type": "state_update", "payload": update_payload})
            except Exception as e:
                log.error(f"Error during WebSocket broadcast: {e}", exc_info=True)

        # Send AI thought/analysis as proper typed message
        if analysis_log_part:
            try:
                await broadcast_func({
                    "type": "ai_thought",
                    "payload": {"thought": analysis_log_part.strip()}
                })
            except Exception as e:
                log.error(f"Error broadcasting AI thought: {e}", exc_info=True)

        # Send action as log entry with 'ai' category
        if action:
            try:
                await broadcast_func({
                    "type": "log_entry",
                    "payload": {"id": log_id_counter, "text": log_action_text, "category": "ai"}
                })
            except Exception as e:
                log.error(f"Error broadcasting action log: {e}", exc_info=True)


        elapsed_loop_time = time.time() - loop_start_time
        game_phase = current_mGBA_state.get("phase", "unknown") if current_mGBA_state else "unknown"
        log.info(f"Cycle {current_cycle} took {elapsed_loop_time:.2f}s. Game Phase: {game_phase}")


    # Save knowledge and end session on exit
    if config.PERSISTENT_LEARNING and knowledge_base:
        knowledge_base._save_knowledge()
        log.info("Final knowledge base saved")

    # End session gracefully
    session_manager.shutdown()
    memory_summary = memory_manager.end_session()
    log.info(f"Session ended: {memory_summary}")

    log.info("Auto loop terminated.")
    if benchmark is not None:
        benchmark.finalize(current_mGBA_state, MODEL)
