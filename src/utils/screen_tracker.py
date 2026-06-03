"""
Screen State Tracker for Fire Emblem AI

Detects when the AI is stuck on the same screen by comparing:
1. Perceptual image hash (pixel-based)
2. Vision description hash (semantic)

Returns factual data only - no hints. The AI learns organically from its memory.
"""

import hashlib
import time
import logging
from collections import deque
from typing import Optional
from PIL import Image

log = logging.getLogger(__name__)


class ScreenTracker:
    """
    Tracks screen states to detect when AI is stuck.

    Uses dual-hash approach:
    - Image hash: Fast perceptual hash for visual similarity
    - Vision hash: Semantic hash from vision model description

    Both must match for screen to be considered "same".
    """

    def __init__(self, stuck_threshold: int = 3, max_history: int = 20):
        """
        Args:
            stuck_threshold: How many times same screen before considered stuck
            max_history: How many screen states to remember
        """
        self.stuck_threshold = stuck_threshold
        self.history = deque(maxlen=max_history)
        # Each entry: (img_hash, vision_hash, action, timestamp)

        self.last_action = None
        self.last_img_hash = None
        self.last_vision_hash = None

    def get_image_hash(self, img_path: str) -> Optional[str]:
        """
        Compute perceptual hash of screenshot.

        Resizes to 8x8 grayscale, thresholds by average.
        Similar images produce similar hashes.
        """
        try:
            img = Image.open(img_path).convert('L').resize((8, 8), Image.LANCZOS)
            pixels = list(img.getdata())
            avg = sum(pixels) / 64
            bits = ''.join('1' if p > avg else '0' for p in pixels)
            return hex(int(bits, 2))
        except Exception as e:
            log.warning(f"Failed to hash image {img_path}: {e}")
            return None

    def get_vision_hash(self, description: str) -> str:
        """
        Hash the vision model's description for semantic comparison.

        Normalizes text (lowercase, sorted unique words) so minor
        phrasing differences don't affect the hash.
        """
        if not description:
            return "empty"

        # Normalize: lowercase, remove punctuation, get unique words
        import re
        words = re.findall(r'\w+', description.lower())
        unique_sorted = sorted(set(words))
        normalized = ' '.join(unique_sorted)

        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    def check_stuck(self, img_path: str, vision_desc: str) -> dict:
        """
        Check if we're stuck on the same screen.

        Returns:
            dict with:
                - is_stuck: bool
                - times_seen: int (how many times this screen appeared)
                - tried_actions: list of actions already tried on this screen
                - img_hash: str
                - vision_hash: str
                - last_action_failed: bool (if last action didn't change screen)
        """
        img_hash = self.get_image_hash(img_path)
        vision_hash = self.get_vision_hash(vision_desc)

        if img_hash is None:
            return {
                "is_stuck": False,
                "times_seen": 1,
                "tried_actions": [],
                "img_hash": None,
                "vision_hash": vision_hash,
                "last_action_failed": False
            }

        # Count how many recent entries match BOTH hashes
        matches = sum(
            1 for h in self.history
            if h[0] == img_hash and h[1] == vision_hash
        )

        is_stuck = matches >= self.stuck_threshold

        # Get actions tried on this exact screen
        tried_actions = [
            h[2] for h in self.history
            if h[0] == img_hash and h[1] == vision_hash and h[2]
        ]

        # Check if last action had no effect (screen didn't change)
        last_action_failed = False
        if self.last_img_hash and self.last_vision_hash and self.last_action:
            if img_hash == self.last_img_hash and vision_hash == self.last_vision_hash:
                last_action_failed = True
                log.info(f"Last action '{self.last_action}' had no effect on screen")

        if is_stuck:
            log.warning(f"STUCK DETECTED: Same screen seen {matches + 1} times. "
                       f"Tried actions: {tried_actions}")

        return {
            "is_stuck": is_stuck,
            "times_seen": matches + 1,
            "tried_actions": tried_actions,
            "img_hash": img_hash,
            "vision_hash": vision_hash,
            "last_action_failed": last_action_failed,
            "last_action": self.last_action if last_action_failed else None
        }

    def record(self, img_hash: str, vision_hash: str, action: str):
        """
        Record this screen state and action taken.

        Called after action is sent to emulator.
        """
        if img_hash is None:
            return

        self.history.append((img_hash, vision_hash, action, time.time()))
        self.last_action = action
        self.last_img_hash = img_hash
        self.last_vision_hash = vision_hash

        log.debug(f"Recorded: action={action}, img_hash={img_hash[:10]}..., "
                 f"history_size={len(self.history)}")

    def clear(self):
        """Clear history. Call on chapter change or game reset."""
        self.history.clear()
        self.last_action = None
        self.last_img_hash = None
        self.last_vision_hash = None
        log.info("Screen tracker history cleared")


# Singleton instance for easy access
_tracker = None

def get_tracker() -> ScreenTracker:
    """Get or create the global screen tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ScreenTracker()
    return _tracker
