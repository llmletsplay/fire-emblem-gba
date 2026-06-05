"""
Session Manager for Fire Emblem AI

Manages session lifecycle:
- Clears active screenshots on startup
- Marks interrupted sessions
- Creates new sessions with unique IDs
- Cleans up old sessions beyond limit
"""

import os
import json
import uuid
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

log = logging.getLogger(__name__)

SESSIONS_FILE = "runtime/sessions/sessions.json"
SESSION_SCREENSHOTS_DIR = "runtime/sessions/screenshots"
ACTIVE_SCREENSHOTS = ["screenshot_0.png", "screenshot_1.png", "screenshot_2.png"]


@dataclass
class SessionMetadata:
    """Metadata for a game session."""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    chapter_start: Optional[str] = None
    chapter_current: Optional[str] = None
    total_actions: int = 0
    status: str = "active"
    screenshot_count: int = 0


class SessionManager:
    """
    Manages game session lifecycle.

    On startup:
    1. Clears active screenshots (screenshot_0/1/2.png)
    2. Marks any 'active' sessions as 'interrupted'
    3. Creates new session with unique ID
    4. Cleans up sessions beyond MAX_SESSIONS

    During gameplay:
    - Tracks actions and chapter changes
    - Manages screenshot counts per session

    On shutdown:
    - Marks session as 'completed'
    - Saves final metadata
    """

    def __init__(self, base_path: str = ".", max_sessions: int = 10, max_screenshots_per_session: int = 500):
        self.base_path = Path(base_path)
        self.max_sessions = max_sessions
        self.max_screenshots = max_screenshots_per_session
        self.sessions_file = self.base_path / SESSIONS_FILE
        self.screenshots_dir = self.base_path / SESSION_SCREENSHOTS_DIR
        self.current_session: Optional[SessionMetadata] = None
        self._sessions: List[SessionMetadata] = []

    def startup(self) -> str:
        """
        Initialize session manager on application startup.

        Returns:
            session_id: The new session's unique ID
        """
        log.info("Session manager starting up...")

        self._clear_active_screenshots()

        self._load_sessions()

        self._mark_interrupted_sessions()

        session_id = self._create_new_session()

        self._cleanup_old_sessions()

        self._save_sessions()

        log.info(f"Session manager ready. Active session: {session_id}")
        return session_id

    def _clear_active_screenshots(self) -> None:
        """Delete the active screenshot files from previous run."""
        for screenshot in ACTIVE_SCREENSHOTS:
            path = self.base_path / screenshot
            if path.exists():
                try:
                    path.unlink()
                    log.debug(f"Cleared active screenshot: {screenshot}")
                except Exception as e:
                    log.warning(f"Failed to clear {screenshot}: {e}")

    def _load_sessions(self) -> None:
        """Load existing sessions from JSON file."""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    self._sessions = [
                        SessionMetadata(**s) for s in data.get("sessions", [])
                    ]
                log.debug(f"Loaded {len(self._sessions)} existing sessions")
            except Exception as e:
                log.warning(f"Failed to load sessions: {e}")
                self._sessions = []
        else:
            self._sessions = []

    def _save_sessions(self) -> None:
        """Save sessions to JSON file."""
        self.sessions_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            all_sessions = self._sessions.copy()
            if self.current_session:
                existing_idx = next(
                    (i for i, s in enumerate(all_sessions)
                     if s.session_id == self.current_session.session_id),
                    None
                )
                if existing_idx is not None:
                    all_sessions[existing_idx] = self.current_session
                else:
                    all_sessions.append(self.current_session)

            data = {
                "sessions": [asdict(s) for s in all_sessions],
                "last_updated": datetime.now().isoformat()
            }

            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)

            log.debug(f"Saved {len(all_sessions)} sessions")
        except Exception as e:
            log.error(f"Failed to save sessions: {e}")

    def _mark_interrupted_sessions(self) -> None:
        """Mark any 'active' sessions as 'interrupted' (crash recovery)."""
        for session in self._sessions:
            if session.status == "active":
                session.status = "interrupted"
                session.end_time = datetime.now().isoformat()
                log.info(f"Marked session {session.session_id} as interrupted")

    def _create_new_session(self) -> str:
        """Create a new session with unique ID."""
        session_id = str(uuid.uuid4())[:8]
        self.current_session = SessionMetadata(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            status="active"
        )
        log.info(f"Created new session: {session_id}")
        return session_id

    def _cleanup_old_sessions(self) -> None:
        """Remove sessions beyond MAX_SESSIONS limit."""
        if len(self._sessions) <= self.max_sessions:
            return

        completed_sessions = [
            s for s in self._sessions
            if s.status in ("completed", "interrupted")
        ]
        completed_sessions.sort(key=lambda s: s.start_time)

        sessions_to_remove = len(self._sessions) - self.max_sessions
        for session in completed_sessions[:sessions_to_remove]:
            self._delete_session_screenshots(session.session_id)
            self._sessions.remove(session)
            log.info(f"Cleaned up old session: {session.session_id}")

    def _delete_session_screenshots(self, session_id: str) -> None:
        """Delete all screenshots for a session."""
        if not self.screenshots_dir.exists():
            return

        for screenshot in self.screenshots_dir.iterdir():
            if session_id in screenshot.name:
                try:
                    screenshot.unlink()
                except Exception as e:
                    log.warning(f"Failed to delete screenshot {screenshot}: {e}")

    def shutdown(self) -> None:
        """Shutdown session manager, marking current session as completed."""
        if self.current_session:
            self.current_session.status = "completed"
            self.current_session.end_time = datetime.now().isoformat()
            log.info(f"Session {self.current_session.session_id} completed: "
                    f"{self.current_session.total_actions} actions")

        self._save_sessions()

    def update_chapter(self, chapter: str) -> None:
        """Update the current chapter in session metadata."""
        if not self.current_session:
            return

        if not self.current_session.chapter_start:
            self.current_session.chapter_start = chapter

        self.current_session.chapter_current = chapter
        self._save_sessions()

    def increment_actions(self) -> None:
        """Increment the action count for current session."""
        if self.current_session:
            self.current_session.total_actions += 1

    def increment_screenshots(self) -> None:
        """Increment screenshot count for current session."""
        if self.current_session:
            self.current_session.screenshot_count += 1

    def should_cleanup_screenshots(self) -> bool:
        """Check if we should cleanup screenshots due to limit."""
        if not self.current_session:
            return False
        return self.current_session.screenshot_count >= self.max_screenshots

    def get_current_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self.current_session.session_id if self.current_session else None

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """Get current session info for WebSocket broadcast."""
        if not self.current_session:
            return None
        return asdict(self.current_session)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all session metadata for UI display."""
        all_sessions = self._sessions.copy()
        if self.current_session:
            all_sessions.append(self.current_session)
        return [asdict(s) for s in all_sessions]
