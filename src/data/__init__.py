"""Fire Emblem GBA game data — supports FE7 and FE8."""
from .game_registry import detect_game, get_game_info, GameInfo, GAME_REGISTRY

# Game-specific imports (available directly for explicit use)
from . import fe8_lookup, fe8_chapters
from . import fe7_lookup, fe7_chapters

# Backward compatibility: re-export FE8 names that were previously at package level
from .fe8_lookup import get_character_name, get_class_name, FE8_CHARACTERS, FE8_CLASSES
from .fe8_chapters import get_chapter_objective, get_objective_text, FE8_CHAPTERS


def get_lookup_module(game_id: str):
    """Get the lookup module for a game.

    Args:
        game_id: "fe7" or "fe8"

    Returns:
        The lookup module (fe7_lookup or fe8_lookup)
    """
    if game_id == "fe8":
        return fe8_lookup
    if game_id == "fe7":
        return fe7_lookup
    raise ValueError(f"Unknown game: {game_id}")


def get_chapters_module(game_id: str):
    """Get the chapters module for a game.

    Args:
        game_id: "fe7" or "fe8"

    Returns:
        The chapters module (fe7_chapters or fe8_chapters)
    """
    if game_id == "fe8":
        return fe8_chapters
    if game_id == "fe7":
        return fe7_chapters
    raise ValueError(f"Unknown game: {game_id}")
