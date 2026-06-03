# --- interactive.py ---

import sys
import select
import json
import logging
from src.utils.image_utils import capture
from src.utils.socket_utils import readrange, send_command
from src.game.fe_state import prep_fe_llm
from src.utils.memory_reader import GBAMemoryReader, get_memory_reader
from src.data import get_lookup_module

log = logging.getLogger('interactive')

# ─── Console command wrappers ─────────────────────────

def cmd_units(sock):
    """Fetches and prints current units."""
    try:
        reader = get_memory_reader(sock)
        if not reader:
            from src.utils.fe8_memory_reader import FE8MemoryReader
            reader = FE8MemoryReader(sock)

        lookup = get_lookup_module(reader.game.game_id)
        state = reader.read_game_state()

        if not state:
            print("Could not read game state")
            return

        print(f"\n=== {reader.game.title} — Chapter {state.chapter}, Turn {state.turn} ({state.phase} Phase) ===")

        print("\nPlayer Units:")
        for unit in state.player_units:
            name = lookup.get_character_name(unit.char_id)
            cls = lookup.get_class_name(unit.class_id)
            print(f"  {name} ({cls}) - HP: {unit.current_hp}/{unit.max_hp} @ ({unit.x}, {unit.y})")

        print(f"\nEnemy Units: {len(state.enemy_units)}")
        for unit in state.enemy_units:
            name = lookup.get_character_name(unit.char_id)
            cls = lookup.get_class_name(unit.class_id)
            print(f"  {name} ({cls}) - HP: {unit.current_hp}/{unit.max_hp} @ ({unit.x}, {unit.y})")

        print(f"\nNPC/Ally Units: {len(state.npc_units)}")

    except Exception as e:
        print(f"Error fetching units: {e}")
        log.error(f"Error in cmd_units: {e}")

def cmd_state(sock):
    """Prints current game state."""
    try:
        state_data = prep_fe_llm(sock)
        print(json.dumps(state_data, indent=2))
    except Exception as e:
        print(f"Error fetching state: {e}")
        log.error(f"Error in cmd_state: {e}")

def cmd_capture(sock, filename="latest.png"):
    """Captures a screenshot."""
    try:
        capture(sock, filename)
        print(f"Screenshot saved as '{filename}'")
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        log.error(f"Error in cmd_capture: {e}")

def cmd_move(sock, position, screenCoords):
    """Tests pathfinding to a location."""
    try:
        # For Fire Emblem, we'd need different pathfinding logic
        print(f"Pathfinding from {position} to {screenCoords}")
        # This would need FE-specific map data
        print("Fire Emblem pathfinding not yet implemented")
    except Exception as e:
        print(f"Error in pathfinding: {e}")
        log.error(f"Error in cmd_move: {e}")

def cmd_action(sock, action_string):
    """Sends action commands to the emulator."""
    try:
        send_command(sock, action_string)
        print(f"Sent action: {action_string}")
    except Exception as e:
        print(f"Error sending action: {e}")
        log.error(f"Error in cmd_action: {e}")

def cmd_help():
    """Prints available commands."""
    print("\n=== Fire Emblem AI Console Commands ===")
    print("  units    - Show current units and positions")
    print("  state    - Display full game state as JSON")
    print("  capture  - Take a screenshot")
    print("  action <buttons> - Send button inputs (e.g., 'U;U;A;')")
    print("  help     - Show this help message")
    print("  exit     - Exit the console")
    print("\nButton inputs: U, D, L, R, A, B, Start, Select")
    print("Chain with semicolons: U;U;A;")
    print("")

# ─── Interactive Console ─────────────────────────────

def interactive_console(sock):
    """
    Interactive console for Fire Emblem AI testing.
    Allows manual control and state inspection.
    """
    log.info("Starting Fire Emblem interactive console.")
    print("\n=== Fire Emblem AI Interactive Console ===")
    print("Type 'help' for available commands.")
    print("Type 'exit' to quit.\n")

    command_map = {
        'units': lambda: cmd_units(sock),
        'state': lambda: cmd_state(sock),
        'capture': lambda: cmd_capture(sock),
        'help': cmd_help,
        'exit': lambda: None,
    }

    try:
        while True:
            # Check for input with timeout
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                try:
                    line = input("> ").strip()
                    if not line:
                        continue

                    # Parse command
                    parts = line.split(maxsplit=1)
                    command = parts[0].lower()
                    args = parts[1] if len(parts) > 1 else ""

                    # Handle special cases
                    if command == 'exit':
                        print("Exiting console...")
                        break
                    elif command == 'action' and args:
                        cmd_action(sock, args)
                    elif command in command_map:
                        command_map[command]()
                    else:
                        print(f"Unknown command: '{command}'. Type 'help' for available commands.")

                except EOFError:
                    # Handle Ctrl+D
                    print("\nExiting console...")
                    break
                except ValueError as e:
                    print(f"Invalid input: {e}")
                except Exception as e:
                    print(f"Command error: {e}")
                    log.exception(f"Error executing command '{line}'")

    except KeyboardInterrupt:
        print("\nInterrupted. Exiting console.")
        log.info("Interactive console interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nUnexpected error in console: {e}")
        log.exception("Unexpected error in interactive_console")
    finally:
        log.info("Interactive console loop finished.")
