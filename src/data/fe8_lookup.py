"""
Fire Emblem 8: The Sacred Stones - Character, Class, and Item ID Lookups

All IDs verified from FE8 decomp:
- Characters: https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/characters.h
- Classes: https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/classes.h
- Items: https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/items.h
"""

# Character ID to name mapping (decomp-verified)
FE8_CHARACTERS = {
    # Playable characters
    0x01: "Eirika",
    0x02: "Seth",
    0x03: "Gilliam",
    0x04: "Franz",
    0x05: "Moulder",
    0x06: "Vanessa",
    0x07: "Ross",
    0x08: "Neimi",
    0x09: "Colm",
    0x0A: "Garcia",
    0x0B: "Innes",
    0x0C: "Lute",
    0x0D: "Natasha",
    0x0E: "Cormag",
    0x0F: "Ephraim",
    0x10: "Forde",
    0x11: "Kyle",
    0x12: "Amelia",
    0x13: "Artur",
    0x14: "Gerik",
    0x15: "Tethys",
    0x16: "Marisa",
    0x17: "Saleh",
    0x18: "Ewan",
    0x19: "L'Arachel",
    0x1A: "Dozla",
    0x1C: "Rennac",
    0x1D: "Duessel",
    0x1E: "Myrrh",
    0x1F: "Knoll",
    0x20: "Joshua",
    0x21: "Syrene",
    0x22: "Tana",
    # Creature campaign / post-game
    0x23: "Lyon",
    0x24: "Orson",
    0x25: "Glen",
    0x26: "Selena",
    0x27: "Valter",
    0x28: "Riev",
    0x29: "Caellach",
    # Boss/enemy characters
    0x40: "Lyon",
    0x41: "Morva",
    0x42: "Orson",
    0x43: "Valter",
    0x44: "Selena",
    0x45: "Valter",
    0x46: "Breguet",
    0x47: "Bone",
    0x48: "Bazba",
    0x4A: "Saar",
    0x4B: "Novala",
    0x4C: "Murray",
    0x4D: "Tirado",
    0x4E: "Binks",
    0x4F: "Pablo",
    0x51: "Aias",
    0x52: "Carlyle",
    0x53: "Caellach",
    0x57: "Riev",
    0x5A: "Gheb",
    0x5B: "Beran",
    0x68: "O'Neill",
    0x69: "Glen",
    0x6A: "Zonta",
    0x6B: "Vigarde",
    0x6C: "Lyon",
    0x6D: "Orson",
    0xBE: "Fomortiis",
}

# Class ID to name mapping (decomp-verified from constants/classes.h)
FE8_CLASSES = {
    0x00: "None",
    # Lords
    0x01: "Lord (Ephraim)",
    0x02: "Lord (Eirika)",
    0x03: "Great Lord (Ephraim)",
    0x04: "Great Lord (Eirika)",
    # Cavalry
    0x05: "Cavalier",
    0x06: "Cavalier (F)",
    0x07: "Paladin",
    0x08: "Paladin (F)",
    # Armor
    0x09: "Armor Knight",
    0x0A: "Armor Knight (F)",
    0x0B: "General",
    0x0C: "General (F)",
    # Special
    0x0D: "Thief",
    0x0E: "Manakete",
    # Mercenary line
    0x0F: "Mercenary",
    0x10: "Mercenary (F)",
    0x11: "Hero",
    0x12: "Hero (F)",
    # Myrmidon line
    0x13: "Myrmidon",
    0x14: "Myrmidon (F)",
    0x15: "Swordmaster",
    0x16: "Swordmaster (F)",
    0x17: "Assassin",
    0x18: "Assassin (F)",
    # Archer line
    0x19: "Archer",
    0x1A: "Archer (F)",
    0x1B: "Sniper",
    0x1C: "Sniper (F)",
    0x1D: "Ranger",
    0x1E: "Ranger (F)",
    # Wyvern line
    0x1F: "Wyvern Rider",
    0x20: "Wyvern Rider (F)",
    0x21: "Wyvern Lord",
    0x22: "Wyvern Lord (F)",
    0x23: "Wyvern Knight",
    0x24: "Wyvern Knight (F)",
    # Mage line
    0x25: "Mage",
    0x26: "Mage (F)",
    0x27: "Sage",
    0x28: "Sage (F)",
    0x29: "Mage Knight",
    0x2A: "Mage Knight (F)",
    # Bishop
    0x2B: "Bishop",
    0x2C: "Bishop (F)",
    # Shaman line
    0x2D: "Shaman",
    0x2E: "Shaman (F)",
    0x2F: "Druid",
    0x30: "Druid (F)",
    0x31: "Summoner",
    0x32: "Summoner (F)",
    # Thief promotion
    0x33: "Rogue",
    # Great Knight
    0x35: "Great Knight",
    0x36: "Great Knight (F)",
    # Manakete (Myrrh)
    0x3C: "Manakete (Myrrh)",
    # Trainee classes
    0x3D: "Journeyman",
    0x3E: "Pupil",
    # Fighter line
    0x3F: "Fighter",
    0x40: "Warrior",
    0x41: "Brigand",
    0x42: "Pirate",
    0x43: "Berserker",
    # Clergy
    0x44: "Monk",
    0x45: "Priest",
    # Recruit
    0x47: "Recruit",
    # Flying
    0x48: "Pegasus Knight",
    0x49: "Falcoknight",
    # Healers
    0x4A: "Cleric",
    0x4B: "Troubadour",
    0x4C: "Valkyrie",
    # Dancer / Soldier
    0x4D: "Dancer",
    0x4E: "Soldier",
    0x4F: "Necromancer",
    # Phantom (summoned)
    0x51: "Phantom",
    # Monsters
    0x52: "Revenant",
    0x53: "Entombed",
    0x54: "Bonewalker",
    0x55: "Bonewalker (Bow)",
    0x56: "Wight",
    0x57: "Wight (Bow)",
    0x58: "Bael",
    0x59: "Elder Bael",
    0x5A: "Cyclops",
    0x5B: "Mauthedoog",
    0x5C: "Gwyllgi",
    0x5D: "Tarvos",
    0x5E: "Maelduin",
    0x5F: "Mogall",
    0x60: "Arch Mogall",
    0x61: "Gorgon",
    0x63: "Gargoyle",
    0x64: "Deathgoyle",
    0x65: "Draco Zombie",
    0x66: "Demon King",
}

# Item ID to name mapping (verified from fireemblem8u constants/items.h)
FE8_ITEMS = {
    # Swords (0x01-0x13)
    0x01: "Iron Sword",
    0x02: "Slim Sword",
    0x03: "Steel Sword",
    0x04: "Silver Sword",
    0x05: "Iron Blade",
    0x06: "Steel Blade",
    0x07: "Silver Blade",
    0x08: "Venin Sword",
    0x09: "Rapier",
    0x0A: "Mani Katti",
    0x0B: "Brave Sword",
    0x0C: "Shamshir",
    0x0D: "Killing Edge",
    0x0E: "Armorslayer",
    0x0F: "Wyrmslayer",
    0x10: "Light Brand",
    0x11: "Runesword",
    0x12: "Lancereaver",
    0x13: "Zanbato",
    # Lances (0x14-0x1E)
    0x14: "Iron Lance",
    0x15: "Slim Lance",
    0x16: "Steel Lance",
    0x17: "Silver Lance",
    0x18: "Venin Lance",
    0x19: "Brave Lance",
    0x1A: "Killer Lance",
    0x1B: "Horseslayer",
    0x1C: "Javelin",
    0x1D: "Spear",
    0x1E: "Axereaver",
    # Axes (0x1F-0x2C)
    0x1F: "Iron Axe",
    0x20: "Steel Axe",
    0x21: "Silver Axe",
    0x22: "Venin Axe",
    0x23: "Brave Axe",
    0x24: "Killer Axe",
    0x25: "Halberd",
    0x26: "Hammer",
    0x27: "Devil Axe",
    0x28: "Hand Axe",
    0x29: "Tomahawk",
    0x2A: "Swordreaver",
    0x2B: "Swordslayer",
    0x2C: "Hatchet",
    # Bows (0x2D-0x34)
    0x2D: "Iron Bow",
    0x2E: "Steel Bow",
    0x2F: "Silver Bow",
    0x30: "Venin Bow",
    0x31: "Killer Bow",
    0x32: "Brave Bow",
    0x33: "Short Bow",
    0x34: "Longbow",
    # Ballistas (0x35-0x37)
    0x35: "Ballista",
    0x36: "Long Ballista",
    0x37: "Killer Ballista",
    # Anima magic (0x38-0x3E)
    0x38: "Fire",
    0x39: "Thunder",
    0x3A: "Elfire",
    0x3B: "Bolting",
    0x3C: "Fimbulvetr",
    0x3D: "Forblaze",
    0x3E: "Excalibur",
    # Light magic (0x3F-0x44)
    0x3F: "Lightning",
    0x40: "Shine",
    0x41: "Divine",
    0x42: "Purge",
    0x43: "Aura",
    0x44: "Luce",
    # Dark magic (0x45-0x4A)
    0x45: "Flux",
    0x46: "Luna",
    0x47: "Nosferatu",
    0x48: "Eclipse",
    0x49: "Fenrir",
    0x4A: "Gleipnir",
    # Staves (0x4B-0x59)
    0x4B: "Heal",
    0x4C: "Mend",
    0x4D: "Recover",
    0x4E: "Physic",
    0x4F: "Fortify",
    0x50: "Restore",
    0x51: "Silence",
    0x52: "Sleep",
    0x53: "Berserk",
    0x54: "Warp",
    0x55: "Rescue",
    0x56: "Torch (Staff)",
    0x57: "Hammerne",
    0x58: "Unlock",
    0x59: "Barrier",
    # Dragon weapon + stat boosters (0x5A-0x63)
    0x5A: "Dragon Axe",
    0x5B: "Angelic Robe",
    0x5C: "Energy Ring",
    0x5D: "Secret Book",
    0x5E: "Speedwing",
    0x5F: "Goddess Icon",
    0x60: "Dragonshield",
    0x61: "Talisman",
    0x62: "Boots",
    0x63: "Body Ring",
    # Promotion items (0x64-0x68)
    0x64: "Hero Crest",
    0x65: "Knight Crest",
    0x66: "Orion's Bolt",
    0x67: "Elysian Whip",
    0x68: "Guiding Ring",
    # Keys + consumables (0x69-0x76)
    0x69: "Chest Key",
    0x6A: "Door Key",
    0x6B: "Lockpick",
    0x6C: "Vulnerary",
    0x6D: "Elixir",
    0x6E: "Pure Water",
    0x6F: "Antitoxin",
    0x70: "Torch",
    0x71: "Delphi Shield",
    0x72: "Member Card",
    0x73: "Silver Card",
    0x74: "White Gem",
    0x75: "Blue Gem",
    0x76: "Red Gem",
    # Misc (0x77-0x80)
    0x77: "Gold",
    0x78: "Reginleif",
    0x79: "Chest Key (5)",
    0x7A: "Mine",
    0x7B: "Light Rune",
    0x7C: "Hoplon Guard",
    0x7D: "Fila's Might",
    0x7E: "Ninis's Grace",
    0x7F: "Thor's Ire",
    0x80: "Set's Litany",
    # Special weapons (0x81-0x99)
    0x85: "Sieglinde",
    0x87: "Ivaldi",
    0x88: "Master Seal",
    0x89: "Metis's Tome",
    0x8A: "Heaven Seal",
    0x8C: "Latona",
    0x8D: "Dragon Lance",
    0x8E: "Vidofnir",
    0x8F: "Naglfar",
    0x91: "Audhulma",
    0x92: "Siegmund",
    0x93: "Garm",
    0x94: "Nidhogg",
    0x95: "Heavy Spear",
    0x96: "Short Spear",
    0x97: "Ocean Seal",
    0x98: "Lunar Brace",
    0x99: "Solar Brace",
    # Monster weapons (0xA7-0xB5)
    0xA7: "Demon Stone",
    0xA8: "Demon Light",
    0xA9: "Ravager",
    0xAA: "Divine Stone",
    0x9A: "Stone",
    0x9B: "Shadowshot",
    0x9C: "Rotten Claw",
    0x9D: "Fetid Claw",
    0x9E: "Poison Claw",
    0x9F: "Lethal Talon",
    0xA0: "Sharp Claw",
}

# Status effect lookup
FE8_STATUS_EFFECTS = {
    0: "None",
    1: "Poison",
    2: "Sleep",
    3: "Silence",
    4: "Berserk",
    5: "Attack boost",
    6: "Defense boost",
    7: "Crit boost",
    8: "Avoid boost",
    13: "Petrify",
}

# Weapon type names (order matches weapon rank array)
FE8_WEAPON_TYPES = ["Sword", "Lance", "Axe", "Bow", "Staff", "Anima", "Light", "Dark"]

# Weapon rank thresholds
FE8_WEAPON_RANK_NAMES = {
    0: "-",
    1: "E",
    31: "D",
    71: "C",
    121: "B",
    181: "A",
    251: "S",
}


def get_character_name(char_id: int) -> str:
    """Get character name from ID, with fallback.
    Generic enemies (IDs 0x70+) use 'Enemy' as name since their class
    provides the useful identifier (Fighter, Soldier, etc.)."""
    name = FE8_CHARACTERS.get(char_id)
    if name:
        return name
    if char_id >= 0x70:
        return "Enemy"
    return f"Unit 0x{char_id:02X}"


def get_class_name(class_id: int) -> str:
    """Get class name from ID, with fallback"""
    return FE8_CLASSES.get(class_id, f"Class 0x{class_id:02X}")


def get_item_name(item_id: int) -> str:
    """Get item name from ID, with fallback"""
    if item_id == 0:
        return "None"
    return FE8_ITEMS.get(item_id, f"Item 0x{item_id:02X}")


def get_status_name(status_id: int) -> str:
    """Get status effect name from ID"""
    return FE8_STATUS_EFFECTS.get(status_id, f"Status {status_id}")


def get_weapon_rank_letter(rank_value: int) -> str:
    """Convert weapon rank value to letter grade"""
    if rank_value == 0:
        return "-"
    if rank_value >= 251:
        return "S"
    if rank_value >= 181:
        return "A"
    if rank_value >= 121:
        return "B"
    if rank_value >= 71:
        return "C"
    if rank_value >= 31:
        return "D"
    return "E"
