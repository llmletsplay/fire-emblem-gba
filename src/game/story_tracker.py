"""
Fire Emblem Story and Context Tracker

Maintains narrative understanding and provides streaming commentary context.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import json
import logging

log = logging.getLogger(__name__)

@dataclass
class StoryEvent:
    """Represents a story event or dialogue sequence."""
    timestamp: str
    chapter: str
    event_type: str  # "dialogue", "cutscene", "battle_start", "battle_end", "recruit"
    characters: List[str]
    summary: str
    key_points: List[str]
    emotional_tone: Optional[str] = None

@dataclass
class CharacterRelation:
    """Tracks relationships between characters."""
    character1: str
    character2: str
    relationship: str  # "allies", "enemies", "siblings", "romantic", "lord_retainer"
    notes: str

@dataclass
class StoryContext:
    """Maintains the overall story context and progression."""
    current_chapter: str = ""
    current_objective: str = ""
    story_events: List[StoryEvent] = field(default_factory=list)
    character_relations: List[CharacterRelation] = field(default_factory=list)
    recruited_units: List[str] = field(default_factory=list)
    fallen_units: List[str] = field(default_factory=list)
    key_items: List[str] = field(default_factory=list)

    # Streaming commentary helpers
    last_commentary: str = ""
    commentary_style: str = "informative"  # "informative", "humorous", "dramatic", "analytical"
    viewer_context: Dict[str, str] = field(default_factory=dict)

class StoryTracker:
    """Tracks Fire Emblem story progression and provides context."""

    def __init__(self):
        self.context = StoryContext()
        self.phase_history: List[str] = []
        self.current_phase = "unknown"
        self.title_screen_attempts = 0  # Track attempts at title screen

    def update_phase(self, phase: str, vision_description: str = "") -> str:
        """
        Update current game phase and generate appropriate response.

        Returns:
            Suggested action or commentary based on phase
        """
        self.phase_history.append(phase)
        self.current_phase = phase

        if phase == "transition":
            return self._handle_transition_phase(vision_description)
        elif phase == "story_dialogue":
            return self._handle_story_phase(vision_description)
        elif phase == "battle_prep":
            return self._handle_prep_phase(vision_description)
        elif phase == "tactical_map":
            return self._handle_tactical_phase(vision_description)
        elif phase == "battle_forecast":
            return self._handle_combat_phase(vision_description)
        elif phase == "unknown":
            return self._handle_unknown_phase(vision_description)
        else:
            return self._handle_menu_phase(vision_description)

    def _handle_story_phase(self, description: str) -> str:
        """Handle story/dialogue phases with A button presses and commentary."""
        # Extract character names and dialogue context from vision description
        commentary = self._generate_story_commentary(description)

        return f"""
        STORY PHASE DETECTED
        Action: Press A to advance dialogue

        Commentary for stream: {commentary}

        Next: A;
        """

    def _handle_prep_phase(self, description: str) -> str:
        """Handle battle preparation phase."""
        return f"""
        BATTLE PREPARATION PHASE
        Review unit positions and formation.
        Check objectives and enemy positions.

        Analyzing battlefield...
        """

    def _handle_tactical_phase(self, description: str) -> str:
        """Handle tactical map gameplay."""
        return f"""
        TACTICAL PHASE
        Analyzing unit positions and threats.
        Planning optimal moves.
        """

    def _handle_combat_phase(self, description: str) -> str:
        """Handle combat forecast screens."""
        return f"""
        COMBAT FORECAST
        Evaluating battle outcome.
        Check hit rates and damage.
        """

    def _handle_menu_phase(self, description: str) -> str:
        """Handle menu navigation."""
        desc_lower = description.lower()

        # Check if we're stuck on title screen
        if "fire emblem" in desc_lower and "press start" in desc_lower:
            self.title_screen_attempts += 1

            if self.title_screen_attempts >= 2:
                # Try double Start to skip opening movie
                log.info(f"Title screen attempt {self.title_screen_attempts} - trying double Start to skip movie")
                return f"""
                TITLE SCREEN - SKIP MOVIE
                Attempting to skip opening movie with double Start.

                Next: Start;Start;
                """
            else:
                return f"""
                TITLE SCREEN
                Press Start to begin.

                Next: Start;
                """
        else:
            # Reset counter when we're past title screen
            self.title_screen_attempts = 0
            return f"""
            MENU NAVIGATION
            Navigate with D-pad, confirm with A.
            """

    def _handle_transition_phase(self, description: str) -> str:
        """Handle black/transition screens - wait or press A."""
        return f"""
        TRANSITION SCREEN
        Screen is black or transitioning.
        Wait a moment or try pressing A to continue.

        Next: A;
        """

    def _handle_unknown_phase(self, description: str) -> str:
        """Handle unknown screens - try pressing A to progress."""
        return f"""
        UNKNOWN SCREEN
        Cannot determine current game state.
        Try pressing A to progress.

        Next: A;
        """

    def _generate_story_commentary(self, description: str) -> str:
        """Generate engaging commentary for story scenes."""
        # This would analyze the description and generate appropriate commentary
        # based on detected characters, emotions, and plot points

        if "Eirika" in description:
            return "Princess Eirika continues her journey to find her brother Ephraim."
        elif "battle" in description.lower():
            return "The war between Grado and Renais intensifies."
        else:
            return "The story unfolds as our heroes face new challenges."

    def add_story_event(self, event: StoryEvent):
        """Add a story event to the context."""
        self.context.story_events.append(event)
        log.info(f"Story event added: {event.summary}")

    def get_streaming_commentary(self, include_tips: bool = True) -> str:
        """
        Generate commentary suitable for Twitch streaming.

        Args:
            include_tips: Whether to include gameplay tips for viewers

        Returns:
            Commentary string
        """
        if self.current_phase == "story_dialogue":
            base = "We're in a story scene right now. "
            if self.context.current_chapter:
                base += f"This is {self.context.current_chapter}. "
            if include_tips:
                base += "For new players: Fire Emblem stories are rich with political intrigue and character development."

        elif self.current_phase == "tactical_map":
            base = "Time for tactical gameplay! "
            if include_tips:
                base += "Remember viewers: the weapon triangle is key - swords beat axes, axes beat lances, lances beat swords."

        else:
            base = "Navigating through menus. "

        return base

    def save_context(self, filepath: str):
        """Save story context to file."""
        data = {
            'current_chapter': self.context.current_chapter,
            'current_objective': self.context.current_objective,
            'recruited_units': self.context.recruited_units,
            'fallen_units': self.context.fallen_units,
            'story_events': [
                {
                    'timestamp': e.timestamp,
                    'chapter': e.chapter,
                    'summary': e.summary
                }
                for e in self.context.story_events[-10:]  # Keep last 10 events
            ]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_context(self, filepath: str):
        """Load story context from file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.context.current_chapter = data.get('current_chapter', '')
                self.context.current_objective = data.get('current_objective', '')
                self.context.recruited_units = data.get('recruited_units', [])
                self.context.fallen_units = data.get('fallen_units', [])
                log.info(f"Loaded story context from {filepath}")
        except FileNotFoundError:
            log.info(f"No existing story context found at {filepath}")
        except Exception as e:
            log.error(f"Error loading story context: {e}")

# Global instance
story_tracker = StoryTracker()