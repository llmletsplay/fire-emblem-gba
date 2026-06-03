"""
Semantic Command Parser for Fire Emblem GBA AI Agent.

Parses high-level LLM commands like:
    COMMAND: SELECT Lyn MOVE [8,7] ATTACK Bandit
into structured Command objects that the executor can translate
to deterministic button sequences.

The LLM thinks like a grandmaster (strategy only), and the system
handles all the mechanical execution (button presses, pathfinding).
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Command types ──────────────────────────────────────────────────────────
# These keywords split a COMMAND: line into individual sub-commands.
# Order matters: longer keywords checked first to avoid partial matches.
COMMAND_KEYWORDS = [
    "END_TURN", "END_PHASE",                       # no-arg phase enders
    "SELECT", "MOVE", "ATTACK", "WAIT", "SEIZE",   # core tactics
    "VISIT", "TALK", "TRADE", "RESCUE", "DROP",     # special actions
    "ITEM",                                         # item management
    "DISMISS",                                      # dialogue
    "PRESS",                                        # raw fallback
    "A", "B",                                       # single button commands
]

# Directions the LLM might use for ATTACK
DIRECTIONS = {"north", "south", "east", "west", "up", "down", "left", "right"}

# Regex to pull coordinates from various formats:
#   [8,7]  (8,7)  [8, 7]  (8, 7)  8,7  to=[8,7]  to [8,7]
_COORD_RE = re.compile(
    r'(?:to\s*=?\s*)?'        # optional "to" / "to="
    r'[\[\(]?\s*'             # optional [ or (
    r'(\d+)\s*,\s*(\d+)'     # x , y
    r'\s*[\]\)]?'             # optional ] or )
)

# Regex to strip quotes and key= prefixes from name arguments
_NAME_CLEAN_RE = re.compile(r'^(?:unit|target|name)\s*=\s*', re.IGNORECASE)


@dataclass
class Command:
    """A single parsed command."""
    type: str                     # e.g. "SELECT", "MOVE", "ATTACK"
    unit: Optional[str] = None    # unit name  (SELECT, TALK, TRADE, RESCUE)
    target: Optional[str] = None  # target name or direction (ATTACK, TALK)
    coord: Optional[Tuple[int, int]] = None  # [x,y] (MOVE, DROP)
    raw: Optional[str] = None     # raw button string (PRESS)
    menu_option: Optional[str] = None  # menu option name (ITEM)
    button: Optional[str] = None  # single button (A, B) for BUTTON type

    def __repr__(self):
        parts = [self.type]
        if self.unit:
            parts.append(f"unit={self.unit}")
        if self.coord is not None:
            parts.append(f"coord={list(self.coord)}")
        if self.target:
            parts.append(f"target={self.target}")
        if self.raw:
            parts.append(f"raw={self.raw}")
        return f"Command({', '.join(parts)})"


@dataclass
class CommandSequence:
    """An ordered list of commands parsed from one LLM output."""
    commands: List[Command] = field(default_factory=list)
    raw_text: str = ""  # original text for logging

    @property
    def is_empty(self) -> bool:
        return len(self.commands) == 0

    def get_primary_action_type(self) -> str:
        """Get the primary action type for result tracking."""
        if not self.commands:
            return "UNKNOWN"
        return self.commands[0].type

    def __repr__(self):
        return f"CommandSequence({self.commands})"


# ── Helpers ────────────────────────────────────────────────────────────────

def _clean_name(text: str) -> str:
    """Strip quotes, key= prefixes, commas, and whitespace from a name arg."""
    text = _NAME_CLEAN_RE.sub('', text)
    text = text.strip().strip('"').strip("'").strip(',').strip()
    return text


def _parse_coord(text: str) -> Optional[Tuple[int, int]]:
    """Extract (x, y) coordinate from text like '[8,7]' or 'to (8, 7)'."""
    m = _COORD_RE.search(text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def _split_by_keywords(text: str) -> List[Tuple[str, str]]:
    """Split text into (KEYWORD, args_text) segments.

    Scans left-to-right for command keywords and splits the text into
    segments. Each segment is a (keyword, remaining_text_until_next_keyword).
    """
    # Build a regex that matches any keyword as a whole word (case-insensitive)
    kw_pattern = re.compile(
        r'\b(' + '|'.join(re.escape(k) for k in COMMAND_KEYWORDS) + r')\b',
        re.IGNORECASE
    )

    matches = list(kw_pattern.finditer(text))
    if not matches:
        return []

    segments = []
    for i, m in enumerate(matches):
        keyword = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        args_text = text[start:end].strip()
        # Strip leading commas, "then", connectors
        args_text = re.sub(r'^[\s,;]+', '', args_text)
        args_text = re.sub(r'^(?:then|and|->|→)\s*', '', args_text, flags=re.IGNORECASE)
        segments.append((keyword, args_text))

    return segments


def _parse_single_command(keyword: str, args: str) -> Optional[Command]:
    """Parse a single (keyword, args) pair into a Command object."""

    if keyword == "SELECT":
        name = _clean_name(args)
        if not name:
            log.warning("SELECT command with no unit name")
            return None
        return Command(type="SELECT", unit=name)

    elif keyword == "MOVE":
        coord = _parse_coord(args)
        if coord is None:
            log.warning(f"MOVE command with unparseable coordinate: '{args}'")
            return None
        return Command(type="MOVE", coord=coord)

    elif keyword == "ATTACK":
        cleaned = _clean_name(args)
        if not cleaned:
            # No target specified — just select Attack from menu
            return Command(type="ATTACK")
        # Check if it's a direction
        if cleaned.lower() in DIRECTIONS:
            return Command(type="ATTACK", target=cleaned.lower())
        # Otherwise it's a target name
        return Command(type="ATTACK", target=cleaned)

    elif keyword in ("WAIT", "SEIZE", "VISIT"):
        return Command(type=keyword)

    elif keyword in ("END_PHASE", "END_TURN"):
        return Command(type="END_TURN")

    elif keyword == "DISMISS":
        return Command(type="DISMISS")
    
    elif keyword in ("A", "B"):
        # Single button commands - generate raw button sequence
        return Command(type="BUTTON", button=keyword)

    elif keyword == "TALK":
        name = _clean_name(args)
        return Command(type="TALK", target=name if name else None)

    elif keyword == "TRADE":
        name = _clean_name(args)
        return Command(type="TRADE", target=name if name else None)

    elif keyword == "RESCUE":
        name = _clean_name(args)
        return Command(type="RESCUE", target=name if name else None)

    elif keyword == "DROP":
        coord = _parse_coord(args)
        return Command(type="DROP", coord=coord)

    elif keyword == "ITEM":
        return Command(type="ITEM", menu_option=args.strip() if args.strip() else None)

    elif keyword == "PRESS":
        raw = args.strip().rstrip(';')
        if raw:
            # Ensure semicolons between buttons
            raw = raw.replace(' ', ';')
            if not raw.endswith(';'):
                raw += ';'
            return Command(type="PRESS", raw=raw)
        return None

    log.warning(f"Unknown command keyword: {keyword}")
    return None


# ── Public API ─────────────────────────────────────────────────────────────

def extract_command_text(llm_output: str) -> Optional[str]:
    """Extract the COMMAND: line from LLM output text.

    Handles various formats:
        COMMAND: SELECT Lyn MOVE [8,7]
        ## COMMAND: SELECT Lyn
        **COMMAND:** SELECT Lyn

    Also strips model-specific wrapper tokens (GLM <|begin_of_box|>, etc.)
    """
    # Strip model wrapper tokens that might be in the output
    cleaned_output = _MODEL_TOKEN_RE.sub('', llm_output)

    for line in cleaned_output.splitlines():
        # Strip markdown formatting
        clean = line.strip().lstrip('#').strip().lstrip('*').strip()
        if clean.upper().startswith('COMMAND:'):
            # Remove the COMMAND: prefix and any markdown bold markers
            cmd_text = clean[8:].strip().rstrip('*').strip()
            if cmd_text:
                return cmd_text
    return None


# Strip model-specific wrapper tokens (GLM <|begin_of_box|>, deepseek <|tool_call|>, etc.)
_MODEL_TOKEN_RE = re.compile(r'<\|[^|]*\|>')

# Regex to detect raw button sequences (e.g., "D;D;D;A", "L;L;U;A;")
_BUTTON_SEQUENCE_RE = re.compile(r'^[LRUDABS];([LRUDABS];)*[LRUDABS];?$', re.IGNORECASE)


def is_raw_button_sequence(text: str) -> bool:
    """Check if text looks like raw button presses.
    
    Returns True if text is ONLY button presses (no semantic commands).
    Note: Single "A" or "B" after COMMAND: are valid semantic commands (dismiss/cancel),
    not raw button sequences - they should NOT be rejected.
    """
    # Strip whitespace and semicolons, check if only button letters remain
    cleaned = text.replace(' ', '').replace(';', '')
    if not cleaned:
        return False
    
    # Single "A" or "B" are valid semantic commands (dismiss dialogue, cancel)
    # Only reject if it's a longer sequence like "A;A;" or "L;R;D;"
    if cleaned.upper() in ('A', 'B'):
        return False
    
    # If all characters are valid button letters AND it's more than one char,
    # it's likely a raw button sequence
    return bool(re.match(r'^[LRUDABS]+$', cleaned, re.IGNORECASE))


def parse_command(text: str) -> CommandSequence:
    """Parse a command string into a CommandSequence.

    Args:
        text: The command text (everything after 'COMMAND:').
              e.g. "SELECT Lyn MOVE [8,7] ATTACK Bandit"

    Returns:
        CommandSequence with parsed commands. Empty if raw buttons detected.
    """
    seq = CommandSequence(raw_text=text)

    # REJECT RAW BUTTON SEQUENCES - Only accept semantic commands
    if is_raw_button_sequence(text):
        log.warning(f"Raw button sequence detected and rejected: '{text}'. Use COMMAND format instead.")
        return seq

    segments = _split_by_keywords(text)
    if not segments:
        log.warning(f"No command keywords found in: '{text}'")
        return seq

    for keyword, args in segments:
        cmd = _parse_single_command(keyword, args)
        if cmd:
            seq.commands.append(cmd)
        else:
            log.warning(f"Failed to parse command segment: {keyword} '{args}'")

    log.info(f"Parsed {len(seq.commands)} commands: {seq.commands}")
    return seq


def parse_command_from_llm_output(llm_output: str) -> Optional[CommandSequence]:
    """Extract and parse COMMAND: from full LLM output.

    Returns None if no COMMAND: line found.
    Returns an empty CommandSequence if raw buttons detected (to trigger retry).
    Returns a CommandSequence with parsed commands if valid semantic format found.
    """
    cmd_text = extract_command_text(llm_output)
    if cmd_text is None:
        return None
    
    # If it's raw buttons, return empty sequence (will trigger retry with proper format)
    if is_raw_button_sequence(cmd_text):
        log.warning(f"Raw button sequence in LLM output rejected: '{cmd_text[:50]}...'")
        return CommandSequence(raw_text=cmd_text)
    
    return parse_command(cmd_text)
