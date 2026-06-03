"""
Button Mapping Module - Single Source of Truth for all button mappings.

This module centralizes button name constants and normalization functions
to ensure consistency across the codebase and with the Lua server.

Button Index Mapping (mGBA):
    0: A
    1: B
    2: SELECT
    3: START
    4: RIGHT (D-pad)
    5: LEFT (D-pad)
    6: UP (D-pad)
    7: DOWN (D-pad)
    8: RT (right shoulder/trigger)
    9: LT (left shoulder/trigger)
"""

from typing import Dict, Optional

BUTTONS: Dict[str, str] = {
    "UP": "UP",
    "DOWN": "DOWN",
    "LEFT": "LEFT",
    "RIGHT": "RIGHT",
    "A": "A",
    "B": "B",
    "START": "START",
    "SELECT": "SELECT",
    "LT": "LT",
    "RT": "RT",
    "L": "LEFT",
    "R": "RIGHT",
    "U": "UP",
    "D": "DOWN",
}

DPAD_BUTTONS = {"UP", "DOWN", "LEFT", "RIGHT", "U", "D", "L", "R"}
SHOULDER_BUTTONS = {"LT", "RT", "L_TRIGGER", "R_TRIGGER", "L_SHOULDER", "R_SHOULDER"}
FACE_BUTTONS = {"A", "B"}
MENU_BUTTONS = {"START", "SELECT"}


def normalize_button(button: str) -> str:
    """
    Normalize a button name to its canonical form.
    
    Args:
        button: Raw button name (e.g., 'R', 'r', 'RIGHT', 'right')
        
    Returns:
        Canonical button name (e.g., 'RIGHT', 'LEFT', 'UP', 'DOWN', 'A', 'B', 'LT', 'RT')
    """
    if not button:
        return button
    
    canonical = button.strip().upper()
    return BUTTONS.get(canonical, canonical)


def normalize_button_sequence(buttons: str) -> str:
    """
    Normalize a button sequence string (e.g., 'R;R;D;A;' -> 'RIGHT;RIGHT;DOWN;A;').
    
    Args:
        buttons: Button sequence string with semicolon separators
        
    Returns:
        Normalized button sequence string
    """
    if not buttons:
        return buttons
    
    parts = buttons.strip().rstrip(';').split(';')
    normalized = [normalize_button(p.strip()) for p in parts if p.strip()]
    return ';'.join(normalized) + ';' if normalized else buttons


def is_dpad(button: str) -> bool:
    """Check if button is a D-pad direction."""
    return normalize_button(button) in DPAD_BUTTONS


def is_shoulder(button: str) -> bool:
    """Check if button is a shoulder/trigger button."""
    return normalize_button(button) in SHOULDER_BUTTONS


def is_face(button: str) -> bool:
    """Check if button is a face button (A or B)."""
    return normalize_button(button) in FACE_BUTTONS
