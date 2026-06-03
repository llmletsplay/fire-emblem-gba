"""
Memory Manager for Fire Emblem AI

Manages a rolling window of game turns with AI reasoning for organic learning.
The AI sees its own past actions and outcomes to detect patterns without programmatic hints.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from PIL import Image
import base64
from io import BytesIO
import hashlib
import logging

log = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """Single turn in the AI's memory."""
    turn_id: int
    timestamp: str
    screen_description: str
    thumbnail_base64: str
    game_state: Dict[str, Any]
    ai_reasoning: str
    action_taken: str
    result: Optional[str] = None
    screen_hash: Optional[str] = None


class MemoryManager:
    """
    Manages rolling memory window for AI context.

    The AI receives its recent history including:
    - What it saw (screen descriptions + thumbnails)
    - What it thought (AI reasoning)
    - What it did (actions)
    - What happened (results)

    This allows organic pattern detection without programmatic hints.
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.entries: deque = deque(maxlen=window_size)
        self.session_id: str = ""
        self._screen_hash_counts: Dict[str, int] = {}
        self._actions_per_screen: Dict[str, List[str]] = {}
        self._turn_counter: int = 0

    def start_session(self, session_id: str) -> None:
        """Start a new memory session."""
        self.session_id = session_id
        self.entries.clear()
        self._screen_hash_counts.clear()
        self._actions_per_screen.clear()
        self._turn_counter = 0
        log.info(f"Memory manager started session: {session_id}")

    def add_entry(self, entry: MemoryEntry) -> None:
        """
        Add a memory entry, updating previous entry's result.

        The 'result' field is filled on the next turn based on what
        the screen changed to - allowing the AI to see cause and effect.
        """
        if self.entries:
            prev_entry = self.entries[-1]
            if prev_entry.result is None:
                prev_entry.result = f"Screen changed to: {entry.screen_description[:150]}"

        screen_hash = self._compute_screen_hash(entry.screen_description)
        entry.screen_hash = screen_hash

        self._screen_hash_counts[screen_hash] = self._screen_hash_counts.get(screen_hash, 0) + 1

        if screen_hash not in self._actions_per_screen:
            self._actions_per_screen[screen_hash] = []
        if entry.action_taken not in self._actions_per_screen[screen_hash]:
            self._actions_per_screen[screen_hash].append(entry.action_taken)

        self._turn_counter += 1
        self.entries.append(entry)

        log.debug(f"Memory entry added: turn {entry.turn_id}, action {entry.action_taken}")

    def _compute_screen_hash(self, description: str) -> str:
        """Compute a hash of the screen description for pattern tracking."""
        normalized = " ".join(sorted(description.lower().split()[:20]))
        return hashlib.md5(normalized.encode()).hexdigest()[:8]

    def generate_thumbnail(self, screenshot_path: str, size: int = 64) -> str:
        """
        Generate a base64 thumbnail from a screenshot.

        Args:
            screenshot_path: Path to the full screenshot
            size: Thumbnail dimensions (default 64x64)

        Returns:
            Base64 data URL for the thumbnail
        """
        try:
            img = Image.open(screenshot_path)
            img.thumbnail((size, size), Image.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            return f"data:image/png;base64,{b64}"
        except Exception as e:
            log.warning(f"Failed to generate thumbnail: {e}")
            return ""

    def format_for_llm(self) -> str:
        """
        Format memory window as structured text for LLM context.

        Returns text showing recent turns with AI's own reasoning,
        allowing it to see patterns in its behavior.
        """
        if not self.entries:
            return "No previous actions in this session yet."

        lines = [f"## Your Recent Memory ({len(self.entries)} turns)\n"]

        for entry in self.entries:
            lines.append(f"### Turn {entry.turn_id} ({entry.timestamp})")
            lines.append(f"**Screen:** {entry.screen_description[:200]}")

            state_str = ", ".join(f"{k}={v}" for k, v in entry.game_state.items())
            if state_str:
                lines.append(f"**State:** {state_str}")

            if entry.ai_reasoning:
                reasoning = entry.ai_reasoning[:250]
                lines.append(f"**Your Thought:** \"{reasoning}\"")

            lines.append(f"**Action:** {entry.action_taken}")

            if entry.result:
                lines.append(f"**Result:** {entry.result[:150]}")

            lines.append("")

        return "\n".join(lines)

    def get_thumbnails_for_api(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent thumbnails formatted for API content array.

        Args:
            count: Number of recent thumbnails to return

        Returns:
            List of image objects for API content
        """
        thumbnails = []
        recent_entries = list(self.entries)[-count:]

        for entry in recent_entries:
            if entry.thumbnail_base64:
                thumbnails.append({
                    "turn_id": entry.turn_id,
                    "type": "image_url",
                    "image_url": {
                        "url": entry.thumbnail_base64,
                        "detail": "low"
                    }
                })

        return thumbnails

    def get_pattern_stats(self, current_screen: str) -> Dict[str, Any]:
        """
        Get pattern statistics for the current screen.

        Returns factual data about repetition - no hints or suggestions.
        The AI uses this to understand if it's repeating actions.
        """
        current_hash = self._compute_screen_hash(current_screen) if current_screen else ""
        times_on_screen = self._screen_hash_counts.get(current_hash, 0)
        actions_tried = self._actions_per_screen.get(current_hash, [])

        consecutive_same = 0
        if self.entries and current_hash:
            for entry in reversed(list(self.entries)):
                if entry.screen_hash == current_hash:
                    consecutive_same += 1
                else:
                    break

        return {
            "total_turns": len(self.entries),
            "session_turn_count": self._turn_counter,
            "times_on_current_screen": times_on_screen,
            "consecutive_same_screen": consecutive_same,
            "actions_tried_here": actions_tried.copy()
        }

    def end_session(self) -> Dict[str, Any]:
        """
        End the current session and return summary stats.
        """
        summary = {
            "session_id": self.session_id,
            "total_turns": self._turn_counter,
            "unique_screens": len(self._screen_hash_counts),
            "most_visited_screens": sorted(
                self._screen_hash_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }

        log.info(f"Memory session ended: {self._turn_counter} turns, {len(self._screen_hash_counts)} unique screens")
        return summary

    def get_recent_actions(self, count: int = 5) -> List[str]:
        """Get the most recent actions taken."""
        recent = list(self.entries)[-count:]
        return [e.action_taken for e in recent]

    def was_action_tried_on_screen(self, action: str, screen_description: str) -> bool:
        """Check if an action was already tried on a similar screen."""
        screen_hash = self._compute_screen_hash(screen_description)
        actions = self._actions_per_screen.get(screen_hash, [])
        return action in actions
