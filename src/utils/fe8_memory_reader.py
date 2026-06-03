"""
Fire Emblem 8 Memory Reader — Backward Compatibility Wrapper

All logic has moved to memory_reader.py (game-agnostic GBAMemoryReader).
This module provides aliases so existing imports continue to work.
"""

from src.utils.memory_reader import (
    GBAUnit,
    GBAGameState,
    GBAMemoryReader,
    get_memory_reader,
    reset_memory_reader,
)
from src.data.game_registry import get_game_info

# Backward compatibility aliases
FE8Unit = GBAUnit
FE8GameState = GBAGameState


class FE8MemoryReader(GBAMemoryReader):
    """FE8-specific memory reader (backward compatibility)."""

    def __init__(self, socket_client):
        super().__init__(socket_client, get_game_info("fe8"))
