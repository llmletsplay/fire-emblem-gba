"""
Tile failure tracker - extracted from llmdriver.py

Tracks which tiles have been tried and failed to help with stuck recovery.
"""

import logging

log = logging.getLogger(__name__)


class TileTracker:
    """Track failed tile actions to help the agent recover from stuck states."""
    
    def __init__(self):
        self.failed_tiles = {}
        self.unit_attempt_tracker = {}
    
    def record_tile_failure(self, cursor_pos, action: str, cycle: int):
        """Record that an action at this cursor position had no effect."""
        if not cursor_pos:
            return
        key = tuple(cursor_pos)
        if key not in self.failed_tiles:
            self.failed_tiles[key] = {"count": 0, "actions": [], "last_cycle": 0}
        entry = self.failed_tiles[key]
        entry["count"] += 1
        if action and action not in entry["actions"]:
            entry["actions"].append(action)
        entry["last_cycle"] = cycle
        log.info(f"Tile failure recorded at {key}: count={entry['count']}, actions={entry['actions']}")
    
    def check_tile_known_bad(self, x: int, y: int) -> bool:
        """Check if a tile has been tried and failed multiple times."""
        return (x, y) in self.failed_tiles and self.failed_tiles[(x, y)]["count"] >= 2
    
    def clear_on_progress(self, prev_state: dict, curr_state: dict):
        """Clear trackers when real game progress happens (turn/chapter change)."""
        if not prev_state or not curr_state:
            return
        
        progress_made = (curr_state.get("turn") != prev_state.get("turn") or
                         curr_state.get("chapter") != prev_state.get("chapter"))
        
        prev_unmoved = prev_state.get("unmoved_count")
        curr_unmoved = curr_state.get("unmoved_count")
        if prev_unmoved is not None and curr_unmoved is not None and curr_unmoved < prev_unmoved:
            progress_made = True
        
        if progress_made:
            if self.failed_tiles or self.unit_attempt_tracker:
                log.info(f"Game progressed — clearing tile trackers")
            self.failed_tiles = {}
            self.unit_attempt_tracker = {}
        
        return progress_made
    
    def get_failed_tiles(self) -> dict:
        """Return the failed tiles dictionary for inspection."""
        return self.failed_tiles


tile_tracker = TileTracker()


def record_tile_failure(cursor_pos, action: str, cycle: int):
    """Module-level function for backward compatibility."""
    tile_tracker.record_tile_failure(cursor_pos, action, cycle)


def check_tile_known_bad(x: int, y: int) -> bool:
    """Module-level function for backward compatibility."""
    return tile_tracker.check_tile_known_bad(x, y)


def clear_failed_tiles_on_progress(prev_state: dict, curr_state: dict):
    """Module-level function for backward compatibility."""
    return tile_tracker.clear_on_progress(prev_state, curr_state)