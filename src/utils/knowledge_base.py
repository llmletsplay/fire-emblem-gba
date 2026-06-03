"""
Fire Emblem AI Knowledge Base System

This module maintains a persistent knowledge base that the AI learns from
and references for better decision making across gameplay sessions.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import deque

log = logging.getLogger('knowledge_base')

class FEKnowledgeBase:
    """
    Persistent knowledge base for Fire Emblem AI learning and improvement.
    """

    def __init__(self, knowledge_file: str = "fe_knowledge.json", on_memory_write: Optional[callable] = None):
        self.knowledge_file = knowledge_file
        self.knowledge = self._load_knowledge()
        self._on_memory_write = on_memory_write  # Callback for broadcasting memory writes to UI

        # Initialize core knowledge structures
        self._initialize_core_knowledge()

        # Recent actions buffer to prevent repetition
        self.recent_actions = deque(maxlen=10)

        # Battle state tracking
        self.current_battle_state = {
            "in_battle": False,
            "selected_unit": None,
            "movement_mode": False,
            "blue_squares_visible": False,
            "last_menu_action": None,
            "menu_depth": 0,
            "cursor_position": None,
            "in_battle_menu": False,
            "in_status_menu": False,
            "consecutive_status_checks": 0
        }

    def _load_knowledge(self) -> Dict[str, Any]:
        """Load knowledge from persistent storage."""
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_knowledge(self):
        """Save knowledge to persistent storage."""
        try:
            os.makedirs(os.path.dirname(self.knowledge_file) or '.', exist_ok=True)
            tmp_path = f"{self.knowledge_file}.tmp"
            with open(tmp_path, 'w') as f:
                json.dump(self.knowledge, f, indent=2)
            os.replace(tmp_path, self.knowledge_file)
        except Exception as e:
            log.error(f"Error saving knowledge: {e}")

    def set_memory_callback(self, callback: callable):
        """Set the memory write callback after initialization."""
        self._on_memory_write = callback

    def _broadcast_memory_write(self, text: str):
        """Broadcast a memory write event to the UI callback if configured."""
        if self._on_memory_write:
            try:
                self._on_memory_write(text)
            except Exception as e:
                log.error(f"Error broadcasting memory write: {e}")

    def _initialize_core_knowledge(self):
        """Initialize essential game knowledge that doesn't change."""
        if "core_mechanics" not in self.knowledge:
            self.knowledge["core_mechanics"] = {
                "unit_colors": {
                    "player": "blue",
                    "enemy": "red",
                    "ally": "green",
                    "grayed_out": "gray",
                    "description": "BLUE units = yours to control. GRAY units = already moved this turn (can't move again). RED units = enemies. GREEN units = allies (NPCs).",
                    "important": "NEVER click on GRAY units - they have already acted this turn!"
                },
                "movement_system": {
                    "blue_squares": "When you select 'Move' for a unit, blue squares show where that unit can move to.",
                    "cursor": "The cursor has 4 corner brackets [ ] around it. Use D-pad to move cursor to a BLUE unit.",
                    "process": "EXACT STEPS: 1. Move cursor (4 brackets) to BLUE unit -> 2. Press A to select -> 3. Choose 'Move' from menu -> 4. Blue squares appear -> 5. Move cursor to a blue square -> 6. Press A to move there",
                    "range": "Each unit has different movement range based on their class and terrain.",
                    "after_move": "After moving, you can: Attack (if enemy in range), Item, Wait (ends unit's turn)"
                },
                "combat_basics": {
                    "attack_range": "Different weapons have different ranges. Check before attacking.",
                    "weapon_triangle": "Swords > Axes > Lances > Swords. Use for advantage.",
                    "damage_preview": "Game shows damage preview before confirming attack."
                },
                "menu_navigation": {
                    "battle_menus": ["Move", "Attack", "Item", "Wait", "Trade", "Rescue"],
                    "status_menus": ["Status", "Options", "Unit List", "Supply", "Save"],
                    "escape_sequence": "If stuck in STATUS menu, press B to exit. Battle menus are OK!",
                    "priority": "Battle menus = GOOD (needed for combat). Status menus = BAD (avoid browsing).",
                    "important": "After selecting Move/Attack/Item, you MUST complete the action or press B to cancel."
                }
            }

        # Battle patterns learned from experience
        if "battle_patterns" not in self.knowledge:
            self.knowledge["battle_patterns"] = {
                "successful_strategies": [],
                "failed_attempts": [],
                "unit_effectiveness": {}
            }

        # Map knowledge
        if "map_knowledge" not in self.knowledge:
            self.knowledge["map_knowledge"] = {
                "visited_locations": [],
                "objectives_completed": [],
                "current_chapter": None
            }

    def update_battle_state(self, observation: Dict[str, Any]):
        """Update current battle state based on game observation."""
        obs_str = str(observation).lower()

        # Detect if we're in battle based on visual cues
        if "tactical_map" in obs_str or "grid" in obs_str:
            self.current_battle_state["in_battle"] = True

        # Detect cursor (4 corner brackets)
        if "cursor" in obs_str or "brackets" in obs_str or "[ ]" in obs_str:
            self.current_battle_state["cursor_position"] = "detected"

        # Detect blue squares for movement
        if "blue" in obs_str and "square" in obs_str:
            self.current_battle_state["blue_squares_visible"] = True
            self.current_battle_state["movement_mode"] = True

        # Detect gray units (units that have already moved)
        if "gray" in obs_str or "grey" in obs_str or "grayed" in obs_str:
            # Note: This will be handled in tactical context instead
            pass

        # Differentiate menu types
        if "move" in obs_str or "attack" in obs_str or "wait" in obs_str:
            self.current_battle_state["in_battle_menu"] = True
            self.current_battle_state["in_status_menu"] = False
        elif "status" in obs_str or "options" in obs_str or "supply" in obs_str:
            self.current_battle_state["in_status_menu"] = True
            self.current_battle_state["consecutive_status_checks"] += 1
            self.current_battle_state["in_battle_menu"] = False
        elif self.current_battle_state["menu_depth"] > 0 and "map" in obs_str:
            self.current_battle_state["menu_depth"] = 0
            self.current_battle_state["in_battle_menu"] = False
            self.current_battle_state["in_status_menu"] = False

    def record_action(self, action: str, result: str = ""):
        """Record an action taken and its result."""
        # Detect and warn about overly complex actions
        action_count = action.count(';')
        if action_count > 5:
            # This is too complex! Log a warning
            simplified = "B;B;" if "menu" in result.lower() else "B;"
            log.warning(f"Overly complex action detected ({action_count} commands). Consider using: {simplified}")

        action_record = {
            "action": action,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }

        self.recent_actions.append(action)

        # Learn from results and broadcast to UI
        if "successful" in result.lower() or "defeated" in result.lower():
            if action not in self.knowledge["battle_patterns"]["successful_strategies"]:
                self.knowledge["battle_patterns"]["successful_strategies"].append(action)
                self._broadcast_memory_write(f"Learned successful strategy: {action[:50]}")
        elif "failed" in result.lower() or "missed" in result.lower():
            if action not in self.knowledge["battle_patterns"]["failed_attempts"]:
                self.knowledge["battle_patterns"]["failed_attempts"].append(action)
                self._broadcast_memory_write(f"Noted failure pattern to avoid: {action[:50]}")

        self._save_knowledge()

    def learn_from_failure(self, failure_description: str):
        """Record and learn from failures to avoid repetition."""
        self.knowledge["battle_patterns"]["failed_attempts"].append({
            "description": failure_description,
            "timestamp": datetime.now().isoformat(),
            "context": self.current_battle_state.copy()
        })
        self._broadcast_memory_write(f"Learning from failure: {failure_description[:60]}")
        self._save_knowledge()


class BattleUnderstandingModule:
    """
    Module specifically for understanding Fire Emblem battle mechanics.
    """

    def __init__(self, knowledge_base: FEKnowledgeBase):
        self.kb = knowledge_base
        self.phase_indicators = {
            "player_phase": ["Player Phase", "your turn", "blue units can move"],
            "enemy_phase": ["Enemy Phase", "red units moving", "enemies attacking"],
            "dialogue": ["portrait", "speaking", "dialogue box", "conversation"],
            "map_view": ["tactical map", "grid", "units on map", "battlefield"],
            "menu": ["menu", "options", "status screen", "inventory"]
        }

    def identify_game_phase(self, observation: str) -> str:
        """Identify current game phase from observation."""
        obs_lower = observation.lower()

        for phase, indicators in self.phase_indicators.items():
            if any(ind.lower() in obs_lower for ind in indicators):
                return phase

        return "unknown"

    def get_phase_specific_actions(self, phase: str) -> str:
        """Return appropriate actions based on game phase."""
        actions = {
            "player_phase": """
Your turn! Take these actions:
1. Select a blue unit with cursor + A
2. Choose 'Move' from menu
3. Move to blue square and press A
4. Select 'Attack' if enemy in range
5. Or select 'Wait' to end unit's turn
""",
            "enemy_phase": """
Enemy phase - wait for it to end.
Watch enemy movements to plan counter-strategy.
Press Start to skip animations if desired.
""",
            "dialogue": """
Story dialogue - press A to advance text.
Pay attention to objectives and character info.
""",
            "map_view": """
Tactical map view:
- Use D-pad to move cursor
- Press A on blue units to select them
- Press L to see movement ranges
- Press Select to end turn when done
""",
            "menu": """
In menu - navigate carefully:
- D-pad to move selection
- A to confirm, B to cancel/back
- If stuck, press B multiple times to exit
"""
        }

        return actions.get(phase, "Observe the screen and identify game state.")

    def analyze_combat_situation(self, units_visible: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze combat situation and provide recommendations."""
        analysis = {
            "threat_level": "low",
            "recommended_actions": [],
            "units_in_danger": [],
            "attack_opportunities": []
        }

        # This would be populated with actual unit analysis
        # For now, providing structure for the system

        return analysis
