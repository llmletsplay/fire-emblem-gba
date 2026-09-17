"""
Command Validator for Fire Emblem GBA AI Agent.

Validates semantic commands against actual game state from memory.
Ensures MOVE targets are valid movement tiles, auto-corrects to nearest valid tile,
and provides feedback for course-correction.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from src.game.command_parser import Command, CommandSequence

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a command sequence."""
    valid: bool
    commands: List[Command]
    corrections: List[str]  # Human-readable corrections made
    warnings: List[str]     # Non-fatal warnings
    errors: List[str]       # Fatal errors that prevent execution
    game_state_requirements: Dict[str, Any]  # What the executor needs

    @property
    def is_empty(self) -> bool:
        return len(self.commands) == 0


def manhattan_distance(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Manhattan distance between two grid positions."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def validate_command_sequence(
    commands: List[Command],
    game_state: Dict[str, Any],
) -> ValidationResult:
    """Validate and auto-correct a command sequence against game state.

    Args:
        commands: Parsed command list
        game_state: Current game state from prep_fe_llm() with fields like:
            - cursor: (x, y) tuple
            - cursor_on_player: str or None
            - movement_tiles: List[List[int]] of valid destinations
            - tutorial_target: (x, y) tuple from event memory (authoritative)
            - flash_indicators: List of flashing tiles from screenshot analysis
            - unit_status: Dict[str, "available"|"already_acted"|"rescued"]
            - party: List[Unit] with name, x, y, hasMoved fields
            - enemies: List[Unit] with name, x, y fields
            - phase: "player_phase" | "enemy_phase" | etc.

    Returns:
        ValidationResult with valid flags, corrections, and requirements.
    """
    corrections = []
    warnings = []
    errors = []
    validated_commands = []
    requirements = {
        "cursor_start": None,
        "unit_must_be_selected": False,
        "required_movement_tiles": [],
        "required_unit_position": None,
        "target_enemy_position": None,
        "action_menu_expected": False,
    }

    if not commands:
        return ValidationResult(
            valid=False,
            commands=[],
            corrections=[],
            warnings=["No commands to validate"],
            errors=["Empty command sequence"],
            game_state_requirements=requirements,
        )

    phase = game_state.get("phase") or "unknown"
    # Memory often returns None/"player" mid-frame; coerce to player_phase when
    # any map-play signal or living party is present.
    if phase in (None, "", "unknown", "player", "Player", "PLAYER"):
        if (
            game_state.get("movement_tiles")
            or game_state.get("cursor_on_player")
            or game_state.get("unit_is_selected")
            or game_state.get("selected_unit")
            or game_state.get("attack_opportunities")
            or game_state.get("party")
        ):
            phase = "player_phase"
        else:
            phase = "unknown"
    if phase != "player_phase":
        errors.append(f"Cannot execute commands during {phase}. Wait for player phase.")

    cursor = game_state.get("cursor")
    if cursor is None:
        cursor = (0, 0)
    requirements["cursor_start"] = cursor

    from src.core import config
    tutorial_target = game_state.get("tutorial_target") if config.TUTORIAL_MODE else None
    flash_indicators = game_state.get("flash_indicators", [])

    if tutorial_target:
        log.info(f"Using authoritative tutorial_target: {tutorial_target}")
        if flash_indicators:
            log.info(f"Ignoring {len(flash_indicators)} flash_indicators (tutorial_target takes priority)")

    unit_status = game_state.get("unit_status", {})
    party = game_state.get("party", [])
    enemies = game_state.get("enemies", [])

    for i, cmd in enumerate(commands):
        cmd_errors = []

        if cmd.type == "SELECT":
            unit_name = cmd.unit
            if not unit_name:
                cmd_errors.append("SELECT command missing unit name")
            else:
                # If unit_status is empty or unit not found, allow anyway - executor will try
                if not unit_status:
                    log.warning(f"unit_status empty - allowing SELECT '{unit_name}' (memory may have failed)")
                elif unit_name not in unit_status:
                    log.warning(f"Unit '{unit_name}' not in unit_status - allowing anyway")
                elif unit_status.get(unit_name) == "already_acted":
                    errors.append(f"Unit '{unit_name}' has already acted (gray/out)")
                elif unit_status.get(unit_name) == "rescued":
                    errors.append(f"Unit '{unit_name}' is being rescued (cannot act)")

        elif cmd.type == "MOVE":
            target_coord = cmd.coord
            if target_coord is None:
                cmd_errors.append("MOVE command missing coordinates")
            else:
                tx, ty = target_coord
                valid_tiles = game_state.get("movement_tiles", [])
                valid_set = set(tuple(t) for t in valid_tiles)

                if valid_tiles:
                    if (tx, ty) not in valid_set:
                        # Priority order: tutorial_target > attack_opportunities > nearest valid
                        if tutorial_target and (tx, ty) == tuple(tutorial_target):
                            # The move target is the tutorial_target but it's not in movement range
                            # This means the unit needs to be selected first
                            log.info(f"MOVE target {target_coord} is tutorial_target but not in current movement range")
                            corrections.append(
                                f"Tile {target_coord} is the TUTORIAL TARGET but unit not selected yet. "
                                f"Will navigate toward this destination after selecting unit."
                            )
                        else:
                            # Use attack opportunities if available
                            attack_opps = game_state.get("attack_opportunities", [])
                            if attack_opps:
                                for opp in attack_opps:
                                    opp_tile = tuple(opp.get("move_to", []))
                                    if opp_tile in valid_set:
                                        corrections.append(
                                            f"Tile {target_coord} not valid. "
                                            f"Using attack position {list(opp_tile)} from attack_opportunities."
                                        )
                                        cmd.coord = opp_tile
                                        tx, ty = opp_tile
                                        target_coord = opp_tile
                                        break
                                else:
                                    pass

                        # If still not valid, find nearest
                        if (tx, ty) not in valid_set and valid_tiles:
                            nearest = None
                            nearest_dist = float('inf')
                            for vt in valid_tiles:
                                dist = manhattan_distance((tx, ty), (vt[0], vt[1]))
                                if dist < nearest_dist:
                                    nearest_dist = dist
                                    nearest = (vt[0], vt[1])

                            if nearest:
                                corrections.append(
                                    f"Tile {target_coord} not in movement range. "
                                    f"Auto-corrected to nearest valid tile {nearest}."
                                )
                                cmd.coord = nearest
                                target_coord = nearest
                            else:
                                cmd_errors.append("No valid movement tiles available")

                requirements["required_movement_tiles"].append(target_coord)
                requirements["unit_must_be_selected"] = True

        elif cmd.type == "ATTACK":
            target_name = cmd.target
            direction = cmd.target if cmd.target in {"north", "south", "east", "west"} else None

            if direction:
                pass
            elif target_name:
                target_unit = next((e for e in enemies if e.get("name") == target_name), None)
                if target_unit:
                    ex, ey = target_unit.get("x"), target_unit.get("y")
                    requirements["target_enemy_position"] = (ex, ey)
                else:
                    warnings.append(f"Target enemy '{target_name}' not found in current enemies")

            requirements["unit_must_be_selected"] = True
            requirements["action_menu_expected"] = True

        elif cmd.type == "SEIZE":
            requirements["unit_must_be_selected"] = True
            requirements["action_menu_expected"] = True

        elif cmd.type == "WAIT":
            requirements["unit_must_be_selected"] = True
            requirements["action_menu_expected"] = True

        elif cmd.type == "TALK":
            if cmd.target:
                target_unit = next((p for p in party if p.get("name") == cmd.target), None)
                if target_unit:
                    requirements["required_unit_position"] = (target_unit.get("x"), target_unit.get("y"))

        elif cmd.type == "VISIT":
            pass

        elif cmd.type == "TRADE":
            pass

        elif cmd.type == "RESCUE":
            if cmd.target:
                warnings.append(f"RESCUE '{cmd.target}' - ensure unit is adjacent")

        elif cmd.type == "DROP":
            if cmd.coord:
                corrections.append(f"DROP at {cmd.coord} - will navigate to nearest position")

        elif cmd.type == "END_TURN":
            pass

        elif cmd.type == "DISMISS":
            pass

        elif cmd.type == "ITEM":
            requirements["action_menu_expected"] = True

        if cmd_errors:
            errors.extend(cmd_errors)
        else:
            validated_commands.append(cmd)

    is_valid = len(errors) == 0 and len(validated_commands) > 0

    return ValidationResult(
        valid=is_valid,
        commands=validated_commands,
        corrections=corrections,
        warnings=warnings,
        errors=errors,
        game_state_requirements=requirements,
    )


def get_validation_feedback(result: ValidationResult) -> str:
    """Generate human-readable feedback for the LLM about validation results."""
    parts = []

    if result.corrections:
        parts.append("CORRECTIONS:")
        for c in result.corrections:
            parts.append(f"  - {c}")

    if result.warnings:
        parts.append("WARNINGS:")
        for w in result.warnings:
            parts.append(f"  - {w}")

    if result.errors:
        parts.append("ERRORS (cannot execute):")
        for e in result.errors:
            parts.append(f"  - {e}")
        parts.append("Please provide corrected commands.")

    if result.valid and not result.corrections and not result.warnings:
        parts.append("All commands validated successfully. Executing...")

    return "\n".join(parts) if parts else "Validation complete."
