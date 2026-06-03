"""
Chronicle Manager for Fire Emblem AI

Manages persistent journal of game events with session support.
The AI can query the journal for past learnings and patterns.
"""

import json
import os
import re
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from PIL import Image
from src.core import config

class ChronicleManager:
    def __init__(self):
        self.enabled = config.CHRONICLE_ENABLED
        # Save directly to React public folder for easy serving
        self.chronicle_path = os.path.join('fe-client', 'public', 'chronicle')
        self.max_entries = config.MAX_CHRONICLE_ENTRIES
        self.entries_file = os.path.join(self.chronicle_path, 'chronicle.json')
        self.screenshots_dir = os.path.join(self.chronicle_path, 'screenshots')
        self.archive_file = os.path.join(self.chronicle_path, 'archive.json')
        self.entries = []
        self.archived_context = []  # Dropped content from compaction

        if self.enabled:
            os.makedirs(self.chronicle_path, exist_ok=True)
            os.makedirs(self.screenshots_dir, exist_ok=True)
            self.load_entries()
            self._load_archive()

    def load_entries(self) -> List[Dict]:
        """Load existing chronicle entries from disk"""
        if os.path.exists(self.entries_file):
            try:
                with open(self.entries_file, 'r') as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = []
        else:
            self.entries = []
        return self.entries

    def save_entries(self):
        """Save chronicle entries to disk"""
        if not self.enabled:
            return

        # Trim to max entries
        if len(self.entries) > self.max_entries:
            # Remove oldest entries and their screenshots
            removed = self.entries[:-self.max_entries]
            for entry in removed:
                if 'screenshot' in entry:
                    screenshot_path = os.path.join(self.screenshots_dir, entry['screenshot'])
                    if os.path.exists(screenshot_path):
                        os.remove(screenshot_path)
            self.entries = self.entries[-self.max_entries:]

        os.makedirs(os.path.dirname(self.entries_file), exist_ok=True)
        tmp_path = f"{self.entries_file}.tmp"
        with open(tmp_path, 'w') as f:
            json.dump(self.entries, f, indent=2)
        os.replace(tmp_path, self.entries_file)

    def add_entry(self,
                  interpretation: str,
                  phase: str,
                  screenshot_path: Optional[str] = None,
                  actions: Optional[List[str]] = None,
                  chapter: Optional[str] = None,
                  session_id: Optional[str] = None) -> Dict:
        """Add a new chronicle entry with story interpretation and screenshot"""
        if not self.enabled:
            return {}

        timestamp = datetime.now().isoformat()
        entry_id = f"entry_{len(self.entries)}_{timestamp.replace(':', '-').replace('.', '-')}"

        entry = {
            'id': entry_id,
            'session_id': session_id,
            'timestamp': timestamp,
            'interpretation': interpretation,
            'phase': phase,
            'actions': actions or [],
            'chapter': chapter
        }

        # Save screenshot if provided
        if screenshot_path and os.path.exists(screenshot_path):
            screenshot_name = f"{entry_id}.png"
            dest_path = os.path.join(self.screenshots_dir, screenshot_name)
            shutil.copy2(screenshot_path, dest_path)
            entry['screenshot'] = screenshot_name

        self.entries.append(entry)
        self.save_entries()
        return entry

    def get_recent_entries(self, count: int = 10) -> List[Dict]:
        """Get the most recent chronicle entries"""
        return self.entries[-count:] if self.entries else []

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict]:
        """Get a specific chronicle entry by ID"""
        for entry in self.entries:
            if entry.get('id') == entry_id:
                return entry
        return None

    def get_screenshot_path(self, entry_id: str) -> Optional[str]:
        """Get the full path to a screenshot for an entry"""
        entry = self.get_entry_by_id(entry_id)
        if entry and 'screenshot' in entry:
            return os.path.join(self.screenshots_dir, entry['screenshot'])
        return None

    def clear_chronicle(self):
        """Clear all chronicle entries and screenshots"""
        if not self.enabled:
            return

        # Remove all screenshots
        if os.path.exists(self.screenshots_dir):
            shutil.rmtree(self.screenshots_dir)
            os.makedirs(self.screenshots_dir)

        # Clear entries
        self.entries = []
        self.save_entries()

    def get_session_entries(self, session_id: str) -> List[Dict]:
        """Get all chronicle entries for a specific session."""
        return [e for e in self.entries if e.get('session_id') == session_id]

    def generate_smart_summary(self, max_entries: int = 50) -> str:
        """
        Generate a 3-sentence summary of key learnings for the AI prompt.

        This is factual information the AI can use - no prescriptive hints.
        """
        recent = self.entries[-max_entries:] if self.entries else []
        if not recent:
            return "No prior game history recorded."

        patterns = []
        phases_seen = set()
        actions_that_worked = []
        actions_that_failed = []

        for entry in recent:
            phase = entry.get('phase', '')
            interp = entry.get('interpretation', '').lower()
            actions = entry.get('actions', [])

            if phase:
                phases_seen.add(phase)

            if 'completed' in interp or 'succeeded' in interp or 'defeated' in interp:
                if actions:
                    actions_that_worked.extend(actions[-2:])

            if 'failed' in interp or 'stuck' in interp or 'repeated' in interp:
                if actions:
                    actions_that_failed.extend(actions[-2:])

        summary_parts = []

        if phases_seen:
            summary_parts.append(f"Phases encountered: {', '.join(list(phases_seen)[:5])}")

        if actions_that_worked:
            unique_worked = list(set(actions_that_worked))[:3]
            summary_parts.append(f"Actions that worked: {', '.join(unique_worked)}")

        if actions_that_failed:
            unique_failed = list(set(actions_that_failed))[:3]
            summary_parts.append(f"Actions to reconsider: {', '.join(unique_failed)}")

        if not summary_parts:
            return f"Session history: {len(recent)} turns recorded across various phases."

        return ". ".join(summary_parts) + "."

    def query_journal(self, topic: str, max_results: int = 5) -> str:
        """
        Search journal for entries matching a topic.

        The AI can output JOURNAL_QUERY: [topic] to trigger this.
        Returns relevant past entries for the AI to learn from.
        """
        if not topic:
            return "Please specify a topic to search for."

        topic_lower = topic.lower()
        topic_words = set(re.findall(r'\w+', topic_lower))
        matches = []

        for entry in self.entries:
            interp = entry.get('interpretation', '')
            phase = entry.get('phase', '')
            combined = f"{interp} {phase}".lower()

            match_count = sum(1 for word in topic_words if word in combined)
            if match_count > 0:
                matches.append({
                    'score': match_count,
                    'timestamp': entry.get('timestamp', ''),
                    'phase': phase,
                    'summary': interp[:200],
                    'actions': entry.get('actions', [])
                })

        if not matches:
            return f"No journal entries found for '{topic}'."

        matches.sort(key=lambda x: x['score'], reverse=True)
        results = matches[:max_results]

        formatted = [f"Journal entries for '{topic}':\n"]
        for m in results:
            time_str = m['timestamp'].split('T')[1][:8] if 'T' in m['timestamp'] else m['timestamp']
            formatted.append(f"- [{time_str}] ({m['phase']}) {m['summary']}")
            if m['actions']:
                formatted.append(f"  Actions: {', '.join(m['actions'][:3])}")

        return "\n".join(formatted)

    def _load_archive(self):
        """Load archived context from disk."""
        if os.path.exists(self.archive_file):
            try:
                with open(self.archive_file, 'r') as f:
                    self.archived_context = json.load(f)
            except Exception:
                self.archived_context = []
        else:
            self.archived_context = []

    def _save_archive(self):
        """Save archived context to disk."""
        if not self.enabled:
            return
        try:
            os.makedirs(os.path.dirname(self.archive_file), exist_ok=True)
            tmp_path = f"{self.archive_file}.tmp"
            with open(tmp_path, 'w') as f:
                json.dump(self.archived_context, f, indent=2)
            os.replace(tmp_path, self.archive_file)
        except Exception:
            pass  # Non-critical, continue without archive

    def archive_dropped_context(self, dropped: List[Dict]):
        """
        Archive content dropped during token compaction.

        This preserves history that was removed from active context
        so the AI can still query it via JOURNAL_QUERY.
        """
        if not dropped:
            return

        self.archived_context.extend(dropped)

        # Keep max 100 archived items (rolling window)
        if len(self.archived_context) > 100:
            self.archived_context = self.archived_context[-100:]

        self._save_archive()

    def query_archived_context(self, query: str, max_results: int = 5) -> str:
        """
        Search archived context by keyword.

        Returns dropped turns/memory entries that match the query.
        """
        if not query:
            return "Please specify a search term."

        query_lower = query.lower()
        results = []

        for item in reversed(self.archived_context):
            # Search in various fields
            content = str(item.get("content", "") or item.get("action", "") or item.get("result", ""))
            item_type = item.get("type", "unknown")

            if query_lower in content.lower():
                results.append(item)
                if len(results) >= max_results:
                    break

        if not results:
            return f"No matches in archived context for '{query}'."

        return json.dumps(results, indent=2)

    def get_journal_index(self) -> str:
        """
        Returns a brief index of journal contents so AI knows what to query.

        This is included in every prompt so the AI can request specific
        content with JOURNAL_QUERY: [topic].
        """
        index_parts = []

        # Count entries by chapter
        chapters: Dict[str, int] = {}
        for entry in self.entries:
            ch = entry.get("chapter") or "Unknown"
            chapters[ch] = chapters.get(ch, 0) + 1

        if chapters:
            chapter_str = ", ".join(f"{k}({v})" for k, v in list(chapters.items())[:5])
            index_parts.append(f"Chapters: {chapter_str}")

        # Count archived context
        archived_count = len(self.archived_context)
        if archived_count > 0:
            index_parts.append(f"Archived turns: {archived_count} (dropped from context, queryable)")

        # Extract key patterns/learnings
        patterns = self._extract_patterns()
        if patterns:
            index_parts.append(f"Patterns: {', '.join(patterns[:5])}")

        # Total entry count
        index_parts.append(f"Total entries: {len(self.entries)}")

        return "\n".join(index_parts) if index_parts else "Journal empty - no history yet"

    def _extract_patterns(self) -> List[str]:
        """Extract key patterns from recent entries."""
        patterns = []
        recent = self.entries[-20:] if self.entries else []

        # Count phase transitions
        phases = [e.get('phase', '') for e in recent if e.get('phase')]
        if phases:
            phase_counts = {}
            for p in phases:
                phase_counts[p] = phase_counts.get(p, 0) + 1
            most_common = sorted(phase_counts.items(), key=lambda x: x[1], reverse=True)
            if most_common:
                patterns.append(f"common_phase:{most_common[0][0]}")

        # Look for repeated actions
        all_actions = []
        for e in recent:
            actions = e.get('actions', [])
            if actions:
                all_actions.extend(actions)

        if all_actions:
            action_counts = {}
            for a in all_actions:
                action_counts[a] = action_counts.get(a, 0) + 1
            repeated = [a for a, c in action_counts.items() if c >= 3]
            if repeated:
                patterns.append(f"repeated_actions:{','.join(repeated[:3])}")

        return patterns
