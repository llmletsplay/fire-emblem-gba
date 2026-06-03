"""
Fire Emblem 7: The Blazing Blade - Character, Class, and Item ID Lookups

IDs sourced from FE7 Nightmare Modules and Universal FE Randomizer:
- Characters: FE7 Nightmare Modules / Chapter Unit Editor / Character List.txt
- Classes: FE7 Nightmare Modules / Class Editors / Class List.txt
- Items: FE7 Nightmare Modules / Item Editors / Item List.txt
"""

# Character ID to name mapping
# Tutorial and non-tutorial versions of the same character are both listed.
FE7_CHARACTERS = {
    # Lords
    0x01: "Eliwood",
    0x02: "Hector",
    0x03: "Lyn",           # Tutorial version
    0x2D: "Lyn",           # Main story version
    # Playable characters
    0x04: "Raven",
    0x05: "Geitz",
    0x06: "Guy",
    0x07: "Karel",
    0x08: "Dorcas",
    0x09: "Bartre",
    0x0B: "Oswin",
    0x0D: "Wil",           # Tutorial version
    0x2E: "Wil",           # Main story version
    0x0E: "Rebecca",
    0x0F: "Louise",
    0x10: "Lucius",
    0x11: "Serra",
    0x12: "Renault",
    0x13: "Erk",
    0x14: "Nino",
    0x15: "Pent",
    0x16: "Canas",
    0x17: "Kent",          # Tutorial version
    0x2F: "Kent",          # Main story version
    0x18: "Sain",          # Tutorial version
    0x30: "Sain",          # Main story version
    0x19: "Lowen",
    0x1A: "Marcus",
    0x1B: "Priscilla",
    0x1C: "Rath",          # Tutorial version
    0x32: "Rath",          # Main story version
    0x1D: "Florina",       # Tutorial version
    0x31: "Florina",       # Main story version
    0x1E: "Fiora",
    0x1F: "Farina",
    0x20: "Heath",
    0x21: "Vaida",
    0x22: "Hawkeye",
    0x23: "Matthew",
    0x24: "Jaffar",
    0x25: "Ninian",
    0x26: "Nils",
    0x27: "Athos",
    0x28: "Merlinus",
    0x29: "Nils",          # Final chapter version
    0x2C: "Wallace",
    0x33: "Dart",
    0x34: "Isadora",
    0x36: "Legault",
    0x37: "Karla",
    0x38: "Harken",
    0x39: "Leila",
    0x3A: "Bramimond",
    # Named bosses
    0x3B: "Kishuna",
    0x3C: "Groznyi",
    0x3D: "Wire",
    0x3F: "Zagan",
    0x40: "Boies",
    0x41: "Puzon",
    0x43: "Santals",
    0x44: "Nergal",
    0x45: "Erik",
    0x46: "Sealen",
    0x47: "Bauker",
    0x48: "Bernard",
    0x49: "Damian",
    0x4A: "Zoldam",
    0x4B: "Uhai",
    0x4C: "Aion",
    0x4D: "Darin",
    0x4E: "Cameron",
    0x4F: "Oleg",
    0x50: "Eubans",
    0x51: "Ursula",
    0x53: "Paul",
    0x54: "Jasmine",
    0x57: "Pascal",
    0x58: "Kenneth",
    0x59: "Jerme",
    0x5A: "Maxime",
    0x5B: "Sonia",
    0x5C: "Teodor",
    0x5D: "Georg",
    0x60: "Denning",
    0x63: "Lloyd",         # Four-Fanged Offense
    0x64: "Linus",         # Four-Fanged Offense
    0x65: "Lloyd",         # Cog of Destiny
    0x66: "Linus",         # Cog of Destiny
    0x7A: "Zephiel",
    0x7B: "Elbert",
    0x84: "Brendan",
    0x85: "Limstella",
    0x86: "Dragon",
    # Lyn mode bosses
    0x87: "Batta",
    0x89: "Zugu",
    0x8D: "Glass",
    0x8E: "Migal",
    0x94: "Carjiga",
    0x99: "Bug",
    0x9F: "Bool",
    0xA6: "Heintz",
    0xAD: "Beyard",
    0xB6: "Yogi",
    0xBE: "Eagler",
    0xC5: "Lundgren",
    # Morph bosses
    0xF4: "Lloyd",         # Morph
    0xF5: "Linus",         # Morph
    0xF6: "Brendan",       # Morph
    0xF7: "Uhai",          # Morph
    0xF8: "Ursula",        # Morph
    0xF9: "Kenneth",       # Morph
    0xFA: "Darin",         # Morph
}

# Class ID to name mapping
FE7_CLASSES = {
    0x00: "None",
    # Lords
    0x01: "Lord (Eliwood)",
    0x02: "Lord (Lyn)",
    0x03: "Lord (Hector)",
    0x07: "Knight Lord",       # Eliwood promoted
    0x08: "Blade Lord",        # Lyn promoted
    0x09: "Great Lord",        # Hector promoted
    # Mercenary line
    0x0A: "Mercenary",
    0x0B: "Mercenary (F)",
    0x0C: "Hero",
    0x0D: "Hero (F)",
    # Myrmidon line
    0x0E: "Myrmidon",
    0x0F: "Myrmidon (F)",
    0x10: "Swordmaster",
    0x11: "Swordmaster (F)",
    # Fighter line
    0x12: "Fighter",
    0x13: "Warrior",
    # Armor line
    0x14: "Knight",
    0x15: "Knight (F)",
    0x16: "General",
    0x17: "General (F)",
    # Archer line
    0x18: "Archer",
    0x19: "Archer (F)",
    0x1A: "Sniper",
    0x1B: "Sniper (F)",
    # Clergy (light)
    0x1C: "Monk",
    0x1D: "Cleric",
    0x1E: "Bishop",
    0x1F: "Bishop (F)",
    # Mage line
    0x20: "Mage",
    0x21: "Mage (F)",
    0x22: "Sage",
    0x23: "Sage (F)",
    # Shaman line
    0x24: "Shaman",
    0x25: "Shaman (F)",
    0x26: "Druid",
    0x27: "Druid (F)",
    # Cavalry
    0x28: "Cavalier",
    0x29: "Cavalier (F)",
    0x2A: "Paladin",
    0x2B: "Paladin (F)",
    # Mounted healer
    0x2C: "Troubadour",
    0x2D: "Valkyrie",
    # Nomad (mounted bow)
    0x2E: "Nomad",
    0x2F: "Nomad (F)",
    0x30: "Nomad Trooper",
    0x31: "Nomad Trooper (F)",
    # Flying
    0x32: "Pegasus Knight",
    0x33: "Falcon Knight",
    0x34: "Wyvern Rider",
    0x35: "Wyvern Rider (F)",
    0x36: "Wyvern Lord",
    0x37: "Wyvern Lord (F)",
    # Infantry
    0x38: "Soldier",
    0x39: "Brigand",
    0x3A: "Pirate",
    0x3B: "Berserker",
    # Thief line
    0x3C: "Thief",
    0x3D: "Thief (F)",
    0x3E: "Assassin",
    # Special
    0x40: "Dancer",
    0x41: "Bard",
    0x42: "Archsage",
    0x43: "Magic Seal",
    0x44: "Transporter",
    0x45: "Transporter",
    0x46: "Fire Dragon",
    0x50: "Corsair",
    0x5A: "Uber Sage",
}

# Item ID to name mapping
FE7_ITEMS = {
    # Swords (0x01-0x13)
    0x01: "Iron Sword",
    0x02: "Slim Sword",
    0x03: "Steel Sword",
    0x04: "Silver Sword",
    0x05: "Iron Blade",
    0x06: "Steel Blade",
    0x07: "Silver Blade",
    0x08: "Poison Sword",
    0x09: "Rapier",
    0x0A: "Mani Katti",
    0x0B: "Brave Sword",
    0x0C: "Wo Dao",
    0x0D: "Killing Edge",
    0x0E: "Armorslayer",
    0x0F: "Wyrmslayer",
    0x10: "Light Brand",
    0x11: "Rune Sword",
    0x12: "Lancereaver",
    0x13: "Long Sword",
    # Lances (0x14-0x1E)
    0x14: "Iron Lance",
    0x15: "Slim Lance",
    0x16: "Steel Lance",
    0x17: "Silver Lance",
    0x18: "Poison Lance",
    0x19: "Brave Lance",
    0x1A: "Killer Lance",
    0x1B: "Horseslayer",
    0x1C: "Javelin",
    0x1D: "Spear",
    0x1E: "Axereaver",
    # Axes (0x1F-0x2B)
    0x1F: "Iron Axe",
    0x20: "Steel Axe",
    0x21: "Silver Axe",
    0x22: "Poison Axe",
    0x23: "Brave Axe",
    0x24: "Killer Axe",
    0x25: "Halberd",
    0x26: "Hammer",
    0x27: "Devil Axe",
    0x28: "Hand Axe",
    0x29: "Tomahawk",
    0x2A: "Swordreaver",
    0x2B: "Swordslayer",
    # Bows (0x2C-0x36)
    0x2C: "Iron Bow",
    0x2D: "Steel Bow",
    0x2E: "Silver Bow",
    0x2F: "Poison Bow",
    0x30: "Killer Bow",
    0x31: "Brave Bow",
    0x32: "Short Bow",
    0x33: "Longbow",
    0x34: "Ballista",
    0x35: "Iron Ballista",
    0x36: "Killer Ballista",
    # Anima magic (0x37-0x3D)
    0x37: "Fire",
    0x38: "Thunder",
    0x39: "Elfire",
    0x3A: "Bolting",
    0x3B: "Fimbulvetr",
    0x3C: "Forblaze",
    0x3D: "Excalibur",
    # Light magic (0x3E-0x43)
    0x3E: "Lightning",
    0x3F: "Shine",
    0x40: "Divine",
    0x41: "Purge",
    0x42: "Aura",
    0x43: "Luce",
    # Dark magic (0x44-0x49)
    0x44: "Flux",
    0x45: "Luna",
    0x46: "Nosferatu",
    0x47: "Eclipse",
    0x48: "Fenrir",
    0x49: "Gespenst",
    # Staves (0x4A-0x58)
    0x4A: "Heal",
    0x4B: "Mend",
    0x4C: "Recover",
    0x4D: "Physic",
    0x4E: "Fortify",
    0x4F: "Restore",
    0x50: "Silence",
    0x51: "Sleep",
    0x52: "Berserk",
    0x53: "Warp",
    0x54: "Rescue",
    0x55: "Torch (Staff)",
    0x56: "Hammerne",
    0x57: "Unlock",
    0x58: "Barrier",
    # Dragon weapon + stat boosters (0x59-0x62)
    0x59: "Dragon Axe",
    0x5A: "Angelic Robe",
    0x5B: "Energy Ring",
    0x5C: "Secret Book",
    0x5D: "Speedwings",
    0x5E: "Goddess Icon",
    0x5F: "Dragonshield",
    0x60: "Talisman",
    0x61: "Boots",
    0x62: "Body Ring",
    # Promotion items (0x63-0x67)
    0x63: "Hero Crest",
    0x64: "Knight Crest",
    0x65: "Orion's Bolt",
    0x66: "Elysian Whip",
    0x67: "Guiding Ring",
    # Keys + consumables (0x68-0x6F)
    0x68: "Chest Key",
    0x69: "Door Key",
    0x6A: "Lockpick",
    0x6B: "Vulnerary",
    0x6C: "Elixir",
    0x6D: "Pure Water",
    0x6E: "Antitoxin",
    0x6F: "Torch",
    # Equipment + gems (0x70-0x75)
    0x70: "Delphi Shield",
    0x71: "Member Card",
    0x72: "Silver Card",
    0x73: "White Gem",
    0x74: "Blue Gem",
    0x75: "Red Gem",
    # Misc (0x76-0x7F)
    0x76: "Gold",
    0x78: "Chest Key (5)",
    0x79: "Mine",
    0x7A: "Light Rune",
    0x7B: "Iron Rune",
    0x7C: "Filla's Might",
    0x7D: "Ninis's Grace",
    0x7E: "Thor's Ire",
    0x7F: "Set's Litany",
    # Legendary / PRF weapons (0x84-0x93)
    0x84: "Durandal",
    0x85: "Armads",
    0x86: "Aureola",
    0x87: "Earth Seal",
    0x88: "Afa's Drops",
    0x89: "Heaven Seal",
    0x8B: "Fell Contract",
    0x8C: "Sol Katti",
    0x8D: "Wolf Beil",
    0x8E: "Ereshkigal",
    0x8F: "Flametongue",
    0x90: "Regal Blade",
    0x91: "Rex Hasta",
    0x92: "Basilikos",
    0x93: "Rienfleche",
    # Additional weapons (0x94-0x99)
    0x94: "Heavy Spear",
    0x95: "Short Spear",
    0x96: "Ocean Seal",
    0x99: "Wind Sword",
}

# Status effect lookup (same engine, same values as FE8)
FE7_STATUS_EFFECTS = {
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

# Weapon type names (order matches weapon rank array — same as FE8)
FE7_WEAPON_TYPES = ["Sword", "Lance", "Axe", "Bow", "Staff", "Anima", "Light", "Dark"]

# Weapon rank thresholds (same as FE8)
FE7_WEAPON_RANK_NAMES = {
    0: "-",
    1: "E",
    31: "D",
    71: "C",
    121: "B",
    181: "A",
    251: "S",
}


def get_character_name(char_id: int) -> str:
    """Get character name from ID, with fallback."""
    name = FE7_CHARACTERS.get(char_id)
    if name:
        return name
    if char_id >= 0x67:
        return "Enemy"
    return f"Unit 0x{char_id:02X}"


def get_class_name(class_id: int) -> str:
    """Get class name from ID, with fallback."""
    return FE7_CLASSES.get(class_id, f"Class 0x{class_id:02X}")


def get_item_name(item_id: int) -> str:
    """Get item name from ID, with fallback."""
    if item_id == 0:
        return "None"
    return FE7_ITEMS.get(item_id, f"Item 0x{item_id:02X}")


def get_status_name(status_id: int) -> str:
    """Get status effect name from ID."""
    return FE7_STATUS_EFFECTS.get(status_id, f"Status {status_id}")


def get_weapon_rank_letter(rank_value: int) -> str:
    """Convert weapon rank value to letter grade."""
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
