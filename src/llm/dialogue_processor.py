"""
Dialogue processing - extracted from llmdriver.py

Handles extraction of actionable instructions from dialogue text.
"""

import re

_DIALOGUE_INSTRUCTION_RES = [
    re.compile(r'(?:select|choose|cursor\s+on|pick)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE),
    re.compile(r'(?:move|go)\s+(?:to|toward|towards)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE),
    re.compile(r'(?:recruit|talk\s+to|speak\s+to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE),
    re.compile(r'(?:attack|fight|engage)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE),
    re.compile(r'(?:visit)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE),
]

_INSTRUCTION_TYPE_MAP = {
    0: "select",
    1: "move",
    2: "recruit",
    3: "attack",
    4: "visit",
}


def extract_dialogue_instruction(dialogue_text: str, party_names: list) -> dict | None:
    """Extract actionable instructions from dialogue text."""
    if not dialogue_text or not party_names:
        return None

    party_lower = {n.lower(): n for n in party_names if n}
    if not party_lower:
        return None

    matched_units = set()
    instruction_type = None

    for idx, pattern in enumerate(_DIALOGUE_INSTRUCTION_RES):
        for m in pattern.finditer(dialogue_text):
            name_candidate = m.group(1).strip()
            name_lower = name_candidate.lower()
            if name_lower in party_lower:
                matched_units.add(party_lower[name_lower])
                if instruction_type is None:
                    instruction_type = _INSTRUCTION_TYPE_MAP.get(idx, "general")

    for name_lower, name_proper in party_lower.items():
        if name_lower in dialogue_text.lower():
            matched_units.add(name_proper)

    if not matched_units:
        return None

    instruction_type = instruction_type or "general"
    unit_list = sorted(matched_units)

    return {
        "text": dialogue_text[:200],
        "unit_names": unit_list,
        "instruction_type": instruction_type,
    }
