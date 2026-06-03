"""
Fire Emblem 8: The Sacred Stones - Chapter Objective Data

Hardcoded chapter objectives so the AI knows what to do each chapter.
Covers shared route (Prologue-Ch8) and Eirika route (Ch9-Ch20 + Final).

Boss char_ids from constants/characters.h (decomp-verified).
"""

# Chapter numbers match what fe8_memory_reader reads from 0x0202BCFE.
# Route split happens after Ch8. Eirika route uses chapter numbers 9-20 in memory.
# Ephraim route uses different chapter numbers (to be added later).

FE8_CHAPTERS = {
    # ==================== SHARED ROUTE (Prologue - Chapter 8) ====================
    0: {
        "name": "Prologue: The Fall of Renais",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss O'Neill",
        "boss_char_id": 0x68,
        "boss_name": "O'Neill",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Tutorial chapter. Seth is very strong but let Eirika get kills for EXP.",
        "new_units": ["Eirika", "Seth"],
        # Hardcoded tutorial target coordinates (x, y) - 0-indexed
        # FE8 Prologue has tutorial prompts but specific target varies
        "tutorial_target": None,
    },
    1: {
        "name": "Chapter 1: Escape!",
        "objective_type": "seize",
        "objective": "Seize the gate with Eirika",
        "boss_char_id": 0x46,
        "boss_name": "Breguet",
        "seize_position": None,  # gate position varies
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "First seize chapter. Breguet is an Armor Knight — use Rapier for bonus damage. Franz and Gilliam join.",
        "new_units": ["Franz", "Gilliam"],
    },
    2: {
        "name": "Chapter 2: The Protected",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Bone",
        "boss_char_id": 0x47,
        "boss_name": "Bone",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Ross, Garcia, and Moulder join. Protect Ross — he's fragile but has great growth potential as a trainee. Visit villages for items.",
        "new_units": ["Ross", "Garcia", "Moulder"],
    },
    3: {
        "name": "Chapter 3: The Bandits of Borgo",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Bazba",
        "boss_char_id": 0x48,
        "boss_name": "Bazba",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Neimi and Colm join. Colm can steal from enemies and open chests. Visit the village before bandits destroy it.",
        "new_units": ["Neimi", "Colm"],
    },
    4: {
        "name": "Chapter 4: Ancient Horrors",
        "objective_type": "defeat_boss",
        "objective": "Defeat all monsters (rout) or defeat boss",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "First monster chapter. Artur and Lute join. Artur's Light magic is effective vs monsters. Protect the villagers.",
        "new_units": ["Artur", "Lute"],
    },
    5: {
        "name": "Chapter 5: The Empire's Reach",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating the boss",
        "boss_char_id": 0x4A,
        "boss_name": "Saar",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Natasha is defeated"],
        "notes": "Natasha and Joshua join. To recruit Joshua, talk to him with Natasha. He starts as an enemy! Don't kill him.",
        "new_units": ["Natasha", "Joshua"],
    },
    5.5: {
        "name": "Chapter 5x: Unbroken Heart",
        "objective_type": "survive",
        "objective": "Survive for 7 turns with Ephraim",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": 7,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Ephraim's side chapter. Kyle and Forde join. Focus on survival, don't overextend. Ephraim, Kyle, Forde, and Orson are available.",
        "new_units": ["Ephraim", "Kyle", "Forde", "Orson"],
    },
    6: {
        "name": "Chapter 6: Victims of War",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Novala",
        "boss_char_id": 0x4B,
        "boss_name": "Novala",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Novala is a Shaman with dark magic. Be wary of his range. Clear the path to the throne.",
        "new_units": [],
    },
    7: {
        "name": "Chapter 7: Waterside Renvall",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Murray",
        "boss_char_id": 0x4C,
        "boss_name": "Murray",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Vanessa and Tana are useful here for flying over water. Watch for ballistae.",
        "new_units": ["Vanessa", "Tana"],
    },
    8: {
        "name": "Chapter 8: It's a Trap!",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Tirado",
        "boss_char_id": 0x4D,
        "boss_name": "Tirado",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Ephraim joins Eirika's party. After this chapter, the route splits. Tirado is strong — gang up on him.",
        "new_units": ["Ephraim"],
    },

    # ==================== EIRIKA ROUTE (Chapters 9-20 + Final) ====================
    9: {
        "name": "Chapter 9: Distant Blade (Eirika)",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "First chapter of Eirika's route. Tethys and Gerik can be recruited.",
        "new_units": ["Tethys", "Gerik", "Marisa", "Innes"],
    },
    10: {
        "name": "Chapter 10: Revolt at Carcino (Eirika)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Pablo",
        "boss_char_id": 0x4F,
        "boss_name": "Pablo",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Innes is defeated"],
        "notes": "Protect Innes who starts in a dangerous position. L'Arachel and Dozla appear but don't join yet.",
        "new_units": [],
    },
    11: {
        "name": "Chapter 11: Creeping Darkness (Eirika)",
        "objective_type": "defeat_boss",
        "objective": "Defeat all monsters or defeat the boss",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Monster chapter in a foggy forest. Bring torch users or Colm for vision. L'Arachel and Dozla join.",
        "new_units": ["L'Arachel", "Dozla"],
    },
    12: {
        "name": "Chapter 12: Village of Silence (Eirika)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Gheb",
        "boss_char_id": 0x5A,
        "boss_name": "Gheb",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Ewan joins (trainee mage). Marisa can be recruited by Gerik if not recruited earlier. Cormag can be recruited by talking with Eirika.",
        "new_units": ["Ewan", "Cormag"],
    },
    13: {
        "name": "Chapter 13: Hamill Canyon (Eirika)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Aias",
        "boss_char_id": 0x51,
        "boss_name": "Aias",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Mountainous terrain. Fliers are very useful. Aias is a powerful Great Knight. Saleh joins.",
        "new_units": ["Saleh"],
    },
    14: {
        "name": "Chapter 14: Queen of White Dunes (Eirika)",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Carlyle",
        "boss_char_id": 0x52,
        "boss_name": "Carlyle",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated"],
        "notes": "Desert chapter — mounted units have reduced movement. Rennac can be recruited (costs gold or use L'Arachel). Buried treasure in sand tiles.",
        "new_units": ["Rennac"],
    },
    15: {
        "name": "Chapter 15: Scorched Sand (Eirika)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Caellach",
        "boss_char_id": 0x53,
        "boss_name": "Caellach",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Eirika and Ephraim's armies reunite. Caellach is a Hero with high stats. Myrrh joins with her Dragonstone.",
        "new_units": ["Myrrh"],
    },
    16: {
        "name": "Chapter 16: Ruled by Madness",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Orson",
        "boss_char_id": 0x6D,
        "boss_name": "Orson",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Recapturing Renais castle. Orson is a Paladin on the throne — high avoid. Duessel joins.",
        "new_units": ["Duessel"],
    },
    17: {
        "name": "Chapter 17: River of Regret",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Riev",
        "boss_char_id": 0x57,
        "boss_name": "Riev",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Syrene joins. Many promoted enemies. Riev is a Bishop with high resistance — use physical attackers.",
        "new_units": ["Syrene"],
    },
    18: {
        "name": "Chapter 18: Two Faces of Evil",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Vigarde",
        "boss_char_id": 0x6B,
        "boss_name": "Vigarde",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Emperor Vigarde is a General with very high defense. Use magic or armor-effective weapons. Knoll joins.",
        "new_units": ["Knoll"],
    },
    19: {
        "name": "Chapter 19: Last Hope",
        "objective_type": "defeat_boss",
        "objective": "Defeat all monsters",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Rout chapter. Many powerful monsters including Draco Zombies. Sacred weapons are very effective here.",
        "new_units": [],
    },
    20: {
        "name": "Chapter 20: Darkling Woods",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Morva",
        "boss_char_id": 0x41,
        "boss_name": "Morva",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Morva is a Draco Zombie with massive stats. Use sacred weapons. Prepare for the final chapter.",
        "new_units": [],
    },
    21: {
        "name": "Final: Sacred Stone",
        "objective_type": "defeat_boss",
        "objective": "Defeat the Demon King Fomortiis",
        "boss_char_id": 0xBE,
        "boss_name": "Fomortiis",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eirika is defeated", "Ephraim is defeated"],
        "notes": "Final chapter. Fomortiis has two phases. Use all sacred weapons. Lyon must be defeated first, then the Demon King.",
        "new_units": [],
    },
    # ==================== EPHRAIM ROUTE (Chapters 9-20) ====================
    # Ephraim route uses different internal chapter IDs in memory.
    # These IDs need live verification with mGBA — the memory value may be
    # offset from the logical chapter number. Placeholder IDs use 100+ range.
    # Once verified, replace keys with actual memory values.

    100: {
        "name": "Chapter 9: Fort Rigwald (Ephraim)",
        "objective_type": "seize",
        "objective": "Seize the throne",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "First chapter of Ephraim's route. Amelia can be recruited by talking with any unit.",
        "new_units": ["Amelia"],
        "needs_verification": True,
    },
    101: {
        "name": "Chapter 10: Turning Traitor (Ephraim)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Beran",
        "boss_char_id": 0x5B,
        "boss_name": "Beran",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Duessel joins. Cormag can be recruited by talking with Ephraim.",
        "new_units": ["Duessel", "Cormag"],
        "needs_verification": True,
    },
    102: {
        "name": "Chapter 11: Phantom Ship (Ephraim)",
        "objective_type": "defeat_boss",
        "objective": "Defeat all monsters",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Ship battle with monsters. L'Arachel and Dozla join.",
        "new_units": ["L'Arachel", "Dozla"],
        "needs_verification": True,
    },
    103: {
        "name": "Chapter 12: Landing at Taizel (Ephraim)",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Ewan joins (trainee mage). Marisa can be recruited by Gerik.",
        "new_units": ["Ewan", "Marisa"],
        "needs_verification": True,
    },
    104: {
        "name": "Chapter 13: Fluorspar's Oath (Ephraim)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Aias",
        "boss_char_id": 0x51,
        "boss_name": "Aias",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Gerik and Tethys join. Desert terrain — mounted units slowed.",
        "new_units": ["Gerik", "Tethys"],
        "needs_verification": True,
    },
    105: {
        "name": "Chapter 14: Father and Son (Ephraim)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Vigarde",
        "boss_char_id": 0x6B,
        "boss_name": "Vigarde",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated"],
        "notes": "Knoll joins. Major story chapter.",
        "new_units": ["Knoll"],
        "needs_verification": True,
    },
    106: {
        "name": "Chapter 15: Scorched Sand (Ephraim)",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Caellach and Valter",
        "boss_char_id": 0x53,
        "boss_name": "Caellach",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Ephraim is defeated", "Eirika is defeated"],
        "notes": "Routes reunite. Myrrh joins. Rennac can be recruited.",
        "new_units": ["Myrrh", "Rennac"],
        "needs_verification": True,
    },
    # Chapters 16-21 are shared between routes (same as Eirika Ch16-21 above)
}


def get_chapter_objective(chapter_number) -> dict | None:
    """Get chapter objective data by chapter number.

    Args:
        chapter_number: Chapter number as read from memory (0x0202BCFE)

    Returns:
        Dict with objective data, or None if chapter not found
    """
    return FE8_CHAPTERS.get(chapter_number)


def get_objective_text(chapter_number) -> str:
    """Get a human-readable objective string for the LLM.

    Args:
        chapter_number: Chapter number as read from memory

    Returns:
        Formatted string describing the chapter objective
    """
    data = FE8_CHAPTERS.get(chapter_number)
    if not data:
        return f"Chapter {chapter_number}: Unknown objective"

    parts = [f"{data['name']}: {data['objective']}"]

    if data.get("boss_name"):
        parts.append(f"Boss: {data['boss_name']}")

    if data.get("turn_limit"):
        parts.append(f"Turn limit: {data['turn_limit']}")

    if data.get("notes"):
        parts.append(f"Tip: {data['notes']}")

    return " | ".join(parts)
