"""
Action definitions for Fire Emblem GBA AI Agent.

Defines high-level actions that the LLM sends and the results returned
after execution with verification.
"""

from typing import Optional, List, Tuple, Any, Dict
from dataclasses import dataclass, field
from enum import Enum


class ActionType(Enum):
    SELECT = "SELECT"
    MOVE = "MOVE"
    ATTACK = "ATTACK"
    WAIT = "WAIT"
    END_TURN = "END_TURN"
    DISMISS = "DISMISS"  # Dismiss dialogue/menu
    CANCEL = "CANCEL"    # Press B to go back


@dataclass
class Action:
    """High-level action to execute in the game."""
    type: ActionType
    unit: Optional[str] = None           # Unit name (e.g., "Eliwood")
    target: Optional[str] = None         # Target unit name or direction
    coord: Optional[Tuple[int, int]] = None  # Target coordinate [x, y]
    direction: Optional[str] = None      # Direction: "north", "south", "east", "west"
    
    def __str__(self):
        parts = [self.type.value]
        if self.unit:
            parts.append(f"unit={self.unit}")
        if self.target:
            parts.append(f"target={self.target}")
        if self.coord:
            parts.append(f"to={self.coord}")
        if self.direction:
            parts.append(f"direction={self.direction}")
        return " ".join(parts)


@dataclass
class ActionResult:
    """Result of action execution with verification."""
    success: bool
    action_type: str
    
    # What happened
    unit_selected: bool = False
    unit_name: Optional[str] = None
    cursor_at: Optional[Tuple[int, int]] = None
    movement_tiles: List[Tuple[int, int]] = field(default_factory=list)
    attack_tiles: List[Tuple[int, int]] = field(default_factory=list)
    
    # Unit states after action
    unit_status: Dict[str, str] = field(default_factory=dict)  # name -> "available"|"already_acted"|"rescued"
    unit_moved: bool = False  # Did the unit complete its action?
    
    # Error info
    error: Optional[str] = None
    attempts: int = 0
    
    # Game state
    final_state: str = "unknown"  # "phase", "menu", "battle", "dialogue"
    phase: str = "unknown"
    
    # What the LLM should know
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for LLM consumption."""
        return {
            "success": self.success,
            "action_type": self.action_type,
            "unit_selected": self.unit_selected,
            "unit_name": self.unit_name,
            "cursor_at": list(self.cursor_at) if self.cursor_at else None,
            "movement_tiles": [list(t) for t in self.movement_tiles],
            "attack_tiles": [list(t) for t in self.attack_tiles],
            "unit_status": self.unit_status,
            "unit_moved": self.unit_moved,
            "error": self.error,
            "attempts": self.attempts,
            "final_state": self.final_state,
            "phase": self.phase,
            "message": self.message,
        }


@dataclass
class PreconditionResult:
    """Result of checking action preconditions before execution."""
    valid: bool
    error: Optional[str] = None
    available_units: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "error": self.error,
            "available_units": self.available_units,
        }


def parse_action_from_llm(command_line: str) -> Optional[Action]:
    """
    Parse a high-level command from LLM into an Action.
    
    Examples:
        "SELECT unit=Eliwood" -> Action(SELECT, unit="Eliwood")
        "MOVE to=[5,3]" -> Action(MOVE, coord=(5,3))
        "MOVE Eliwood to [5,3]" -> Action(MOVE, unit="Eliwood", coord=(5,3))
        "ATTACK target=Bandit" -> Action(ATTACK, target="Bandit")
        "END_TURN" -> Action(END_TURN)
    """
    command_line = command_line.strip()
    
    # Parse SELECT
    if command_line.startswith("SELECT"):
        import re
        match = re.search(r'SELECT\s+unit="?([^"\s]+)"?', command_line, re.IGNORECASE)
        if match:
            return Action(type=ActionType.SELECT, unit=match.group(1))
    
    # Parse MOVE
    if command_line.startswith("MOVE"):
        import re
        action = Action(type=ActionType.MOVE)
        
        # Get unit name
        match = re.search(r'MOVE\s+"?([^"\s]+)"?\s+to', command_line, re.IGNORECASE)
        if match:
            action.unit = match.group(1)
        
        # Get coordinate
        match = re.search(r'to=\[?(\d+)[,\s]+(\d+)\]?', command_line)
        if match:
            action.coord = (int(match.group(1)), int(match.group(2)))
        
        # Also try just "MOVE to=[x,y]" without unit
        if not action.coord:
            match = re.search(r'to=\[?(\d+)[,\s]+(\d+)\]?', command_line)
            if match:
                action.coord = (int(match.group(1)), int(match.group(2)))
        
        return action
    
    # Parse ATTACK
    if command_line.startswith("ATTACK"):
        import re
        action = Action(type=ActionType.ATTACK)
        
        match = re.search(r'ATTACK\s+target="?([^"\s]+)"?', command_line, re.IGNORECASE)
        if match:
            action.target = match.group(1)
        
        match = re.search(r'direction=("?\w+"?|north|south|east|west)', command_line, re.IGNORECASE)
        if match:
            action.direction = match.group(1).strip('"')
        
        return action
    
    # Parse WAIT
    if "WAIT" in command_line.upper():
        return Action(type=ActionType.WAIT)
    
    # Parse END_TURN
    if "END_TURN" in command_line.upper() or command_line.strip().upper() == "SELECT;":
        return Action(type=ActionType.END_TURN)
    
    # Parse DISMISS
    if "DISMISS" in command_line.upper() or command_line.strip().upper() == "A;":
        return Action(type=ActionType.DISMISS)
    
    # Parse CANCEL
    if "CANCEL" in command_line.upper() or command_line.strip().upper() == "B;":
        return Action(type=ActionType.CANCEL)
    
    return None