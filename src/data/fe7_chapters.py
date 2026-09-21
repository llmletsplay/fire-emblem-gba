"""
Fire Emblem 7: The Blazing Blade - Chapter Objective Data

Covers Lyn's Tale (tutorial, Ch1-10) and Eliwood's Tale (Ch11-Final).
Hector's Tale uses different chapter numbering — to be added later.

Chapter numbers are what the game stores in memory for its internal
chapter ID. Lyn's Tale chapters may use IDs 0x00-0x09 internally.
FE7 chapter IDs need live verification with mGBA.
"""

FE7_CHAPTERS = {
    # ==================== LYN'S TALE (Tutorial, Chapters 1-10) ====================
    # Note: FE7 internal chapter IDs for Lyn's Tale need verification.
    # Listed by logical chapter number; actual memory values may differ.

    # Prologue / Ch1-10 use Lyn Mode IDs (tentative mapping)
    0: {
        "name": "Prologue: A Girl from the Plains",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Batta",
        "boss_char_id": 0x87,
        "boss_name": "Batta",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Tutorial chapter — the game gives step-by-step instructions via dialogue. "
                 "READ the dialogue text and LOOK at visual indicators (flashing tiles, blue squares) "
                 "on the screenshot. The game shows you exactly where to move. Follow its guidance. "
                 "Start Lyn@(13,7) → forced MOVE (8,7). Later mid-prologue Lyn@(7,7) → (5,4). Boss Batta at (3,2).",
        "new_units": ["Lyn"],
        "needs_verification": True,
        # Tutorial sequence - coordinates for each step (x, y) - 0-indexed
        # Each step: [coordinates], "description"
        "tutorial_sequence": [
            {
                "coords": [(8, 7)],
                "step": "move",
                "description": "Move Lyn to (8,7) — first Ch0 forced tile from start @(13,7)",
            },
            {
                "coords": [(8, 6)],
                "step": "attack",
                "description": "After WAIT/enemy phase: move adjacent to brigand@(7,6) at (8,6) then Attack",
            },
            {
                "coords": [(5, 4)],
                "step": "move",
                "description": "Move Lyn to (5,4) — vulnerary flash (verified mid-prologue)",
            },
            {
                "coords": [(5, 4)],
                "step": "item",
                "description": "Use Vulnerary from Item menu",
            },
            {
                "coords": [(2, 2), (4, 2), (3, 3), (3, 1)],
                "step": "attack",
                "description": "Attack Batta at (3,2) — any adjacent tile",
            },
            {
                "coords": [(3, 2)],
                "step": "seize",
                "description": "Seize gate at (3,2) to complete Prologue",
            },
        ],
    },
    1: {
        "name": "Chapter 1: Footsteps of Fate",
        "objective_type": "defeat_all",
        "objective": "Defeat all enemies",
        "boss_char_id": 0x89,
        "boss_name": "Zugu",
        "seize_position": (8, 4),
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Kent and Sain join. Teaches weapon triangle basics. Seize gate at (8,4) to complete chapter.",
        "new_units": ["Kent", "Sain"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        # This chapter has extensive tutorial prompts
        "tutorial_sequence": [
            # Turn 1
            {"coords": [(5, 4)], "step": "move", "unit": "Sain", "description": "Move Sain to (5,4) - 'Direct my arm!'"},
            {"coords": [(5, 6)], "step": "move", "unit": "Kent", "description": "Move Kent to (5,6) - after Sain conversation"},
            {"coords": [(4, 5)], "step": "move", "unit": "Lyn", "description": "Move Lyn to (4,5) - finish off enemy"},
            # Turn 1 (continued)
            {"coords": [(5, 9)], "step": "move", "unit": "Sain", "description": "Move Sain to (5,9) - attack (misses)"},
            {"coords": [(6, 8)], "step": "move", "unit": "Kent", "description": "Move Kent to (6,8)"},
            # Turn 2 - Lyn in woods
            {"coords": [(5, 4)], "step": "move", "unit": "Lyn", "description": "Move Lyn to Woods tile at (5,4) - terrain bonus"},
            # Trade tutorial
            {"coords": [(4, 4), (5, 5)], "step": "move", "unit": "Sain", "description": "Move Sain next to Lyn for trade (4,4) or (5,5)"},
            # Trade UI: Select Sain → A → cursor on Lyn → right → up/down to Vulnerary → A
            # Use item UI: A on Vulnerary → up/down to Vulnerary → A
            # Cavalry movement after turn end
            {"coords": "adjacent_to_sain", "step": "move", "unit": "cavalry", "description": "After turn endsKent, cavalry (/Sain) can move again - move adjacent to where they ended"},
            # Free flow - defeat remaining enemies
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
            # Seize gate to complete
            {"coords": [(8, 4)], "step": "seize", "description": "Seize gate at (8,4) to complete chapter"},
        ],
    },
    2: {
        "name": "Chapter 2: Sword of Spirits",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Glass and seize throne",
        "boss_char_id": 0x8D,
        "boss_name": "Glass",
        "seize_position": (1, 11),
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Lyn obtains the Mani Katti. Visit the shrine. Must break wall at (3,8) to access Glass.",
        "new_units": [],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            {"coords": [(0, 7)], "step": "visit", "unit": "Lyn", "description": "Visit house at (0,7) - start of chapter"},
            {"coords": [(1, 7)], "step": "visit", "unit": "Sain", "description": "Visit house at (1,7) - then move 1 tile adjacent, not (0,7) where Lyn is"},
            {"coords": "adjacent_not_0_7", "step": "move", "unit": "Sain", "description": "Move Sain 1 tile adjacent to (1,7), avoiding (0,7)"},
            {"coords": [(0, 9)], "step": "visit", "unit": "Kent", "description": "Visit last house at (0,9)"},
            {"coords": [(3, 8)], "step": "break", "unit": "any", "description": "Break wall at (3,8) to access Glass and throne room"},
            {"coords": "attack_glass", "step": "attack", "unit": "any", "description": "Defeat Glass (boss)"},
            {"coords": [(1, 11)], "step": "seize", "description": "Seize throne at (1,11) to complete chapter"},
        ],
    },
    3: {
        "name": "Chapter 3: Band of Mercenaries",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Migal",
        "boss_char_id": 0x8E,
        "boss_name": "Migal",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Florina and Wil join. Teaches rescue mechanic.",
        "new_units": ["Florina", "Wil"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            {"coords": [(3, 6)], "step": "visit", "unit": "Lyn", "description": "Visit village at (3,6) to recruit Wil"},
            {"coords": [(3, 7)], "step": "select", "unit": "Wil", "description": "Select Wil at (3,7)"},
            {"coords": [(5, 6)], "step": "move", "unit": "Wil", "description": "Move Wil to (5,6)"},
            {"coords": "adjacent_5_4", "step": "attack", "unit": "Wil", "description": "Attack bandit at (5,4) - any adjacent tile"},
            {"coords": [(2, 7)], "step": "select", "unit": "Florina", "description": "Select Florina at (2,7)"},
            {"coords": [(4, 4)], "step": "move", "unit": "Florina", "description": "Move Florina to (4,4)"},
            {"coords": "adjacent_5_4", "step": "attack", "unit": "Florina", "description": "Attack bandit at (5,4) - any adjacent tile"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    4: {
        "name": "Chapter 4: In Occupation's Shadow",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Carjiga",
        "boss_char_id": 0x94,
        "boss_name": "Carjiga",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Dorcas joins. Can be recruited by talking with Lyn. He starts as an enemy! Large map with scrolling.",
        "new_units": ["Dorcas"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED (world grid, not viewport)
        # This chapter has a large scrolling map
        "tutorial_sequence": [
            {"coords": [(9, 5)], "step": "move", "unit": "Lyn", "description": "Move Lyn from (7,5) to (9,5) - initial advance"},
            {"coords": "inside_building", "step": "position", "unit": "allies", "description": "Position other units inside the building"},
            {"coords": [(10, 5)], "step": "move", "unit": "Lyn", "description": "Move Lyn to (10,5) - approach Dorcas"},
            {"coords": [(11, 5)], "step": "talk", "unit": "Lyn", "description": "Talk to Dorcas at (11,5) to recruit him"},
            {"coords": [(11, 5)], "step": "select", "unit": "Dorcas", "description": "Select Dorcas at (11,5)"},
            {"coords": "adjacent_11_2", "step": "move", "unit": "Dorcas", "description": "Move Dorcas adjacent to (11,2) - within hand axe range of bandit"},
            {"coords": "attack_11_2", "step": "attack", "unit": "Dorcas", "description": "Attack bandit at (11,2)"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    5: {
        "name": "Chapter 5: Beyond the Borders",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Bug",
        "boss_char_id": 0x99,
        "boss_name": "Bug",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Serra and Erk join. Teaches magic basics.",
        "new_units": ["Serra", "Erk"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            {"coords": [(5, 6)], "step": "move", "unit": "Lyn", "description": "Move Lyn from (3,6) to (5,6) - approach Serra"},
            {"coords": [(6, 6)], "step": "talk", "unit": "Lyn", "description": "Talk to Serra at (6,6) to recruit Serra and Erk"},
            {"coords": [(6, 6)], "step": "select", "unit": "Serra", "description": "Select Serra at (6,6)"},
            {"coords": "heal", "step": "action", "unit": "Serra", "description": "Select Heal ability"},
            {"coords": [(7, 6)], "step": "target", "unit": "Serra", "description": "Target Erk at (7,6) to heal"},
            {"coords": [(7, 6)], "step": "select", "unit": "Erk", "description": "Select Erk at (7,6)"},
            {"coords": [(7, 5), (8, 5), (6, 5), (6, 4)], "step": "move", "unit": "Erk", "description": "Move Erk to attack archer at (7,4) - any adjacent tile"},
            {"coords": "attack_7_4", "step": "attack", "unit": "Erk", "description": "Attack archer with fire at (7,4)"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    6: {
        "name": "Chapter 6: Blood of Pride",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Bool",
        "boss_char_id": 0x9F,
        "boss_name": "Bool",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Rath joins. Matthew joins via house. Teaches mounted unit movement.",
        "new_units": ["Rath", "Matthew"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            # Turn 1
            {"coords": [(4, 2)], "step": "visit", "unit": "Lyn", "description": "Move Lyn from (4,7) to house at (4,2) to recruit Matthew"},
            {"coords": [(4, 3)], "step": "select", "unit": "Matthew", "description": "Select Matthew at (4,3)"},
            {"coords": [(8, 4)], "step": "move", "unit": "Matthew", "description": "Move Matthew to (8,4) - open door with lockpick"},
            {"coords": "open_door", "step": "action", "unit": "Matthew", "description": "Open door at (8,4)"},
            {"coords": [(6, 6)], "step": "select", "unit": "Rath", "description": "Select Rath at (6,6)"},
            {"coords": [(8, 1)], "step": "move", "unit": "Rath", "description": "Move Rath to trigger tile at (8,1) - unlock new area"},
            # Turn 2
            {"coords": [(12, 6)], "step": "move", "unit": "Matthew", "description": "Move Matthew to (12,6) - open treasure chest"},
            {"coords": "open_chest", "step": "action", "unit": "Matthew", "description": "Open chest at (12,6)"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    7: {
        "name": "Chapter 7: Siblings Abroad",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Heintz",
        "boss_char_id": 0xA6,
        "boss_name": "Heintz",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated", "Nils is defeated"],
        "notes": "Nils and Lucius join. Nils can play music to give units another turn. Starts with prep screen.",
        "new_units": ["Nils", "Lucius"],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            {"coords": "start", "step": "menu", "description": "Press Start to exit prep screen and begin"},
            {"coords": [(2, 5)], "step": "select", "unit": "Lucius", "description": "Select Lucius at (2,5) - just joined"},
            {"coords": [(3, 5)], "step": "move", "unit": "Lucius", "description": "Move Lucius 1 tile right to (3,5)"},
            {"coords": "attack", "step": "attack", "unit": "Lucius", "description": "Attack Black Fang member"},
            {"coords": [(1, 4)], "step": "select", "unit": "Nils", "description": "Select Nils at (1,4)"},
            {"coords": [(2, 5)], "step": "move", "unit": "Nils", "description": "Move Nils to (2,5) - next to Lucius"},
            {"coords": "play_music", "step": "action", "unit": "Nils", "description": "Play music to let Lucius act again"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    # Chapter 7x: Night of Farewells (intermission - no tutorial targets)
    "7x": {
        "name": "Chapter 7x: Night of Farewells",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss",  # Boss is dependent on route
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated"],
        "notes": "Intermission chapter. No tutorial targets.",
        "new_units": [],
        "needs_verification": True,
        "tutorial_sequence": [],  # No tutorial targets
    },
    8: {
        "name": "Chapter 8: Vortex of Strategy",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Yogi",
        "boss_char_id": 0xB6,
        "boss_name": "Yogi",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Wallace joins if Lyn's level is below 4, or can be skipped. Fog of war chapter.",
        "new_units": ["Wallace"],
        "needs_verification": True,
        "tutorial_sequence": [],  # No tutorial targets
    },
    9: {
        "name": "Chapter 9: A Grim Reunion",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Eagler",
        "boss_char_id": 0xBE,
        "boss_name": "Eagler",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Castle approach. Strong enemies. Use weapon triangle.",
        "new_units": [],
        "needs_verification": True,
        # Tutorial sequence - ALL COORDINATES ARE 0-INDEXED
        "tutorial_sequence": [
            {"coords": [(2, 8)], "step": "select", "unit": "Wallace", "description": "Select Wallace at (2,8)"},
            {"coords": "down_3", "step": "move", "unit": "Wallace", "description": "Move Wallace 3 spaces down onto Knight's Crest item"},
            {"coords": "use_item", "step": "action", "unit": "Wallace", "description": "Use Knight's Crest on Wallace - promotes to Great Lord"},
            {"coords": "defeat_all", "step": "battle", "description": "Defeat all remaining enemies"},
        ],
    },
    10: {
        "name": "Chapter 10: The Distant Plains",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Lundgren",
        "boss_char_id": 0xC5,
        "boss_name": "Lundgren",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Lyn is defeated"],
        "notes": "Final Lyn Mode chapter. Lundgren is a General with very high defense. Use Mani Katti.",
        "new_units": [],
        "needs_verification": True,
    },

    # ==================== ELIWOOD'S TALE (Chapters 11-Final) ====================
    # Note: Internal chapter IDs need live verification. Listed by logical number.

    11: {
        "name": "Chapter 11: Taking Leave",
        "objective_type": "seize",
        "objective": "Seize the gate",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated"],
        "notes": "First chapter of Eliwood's Tale. Eliwood, Marcus, Lowen, Rebecca, Dorcas, and Bartre available.",
        "new_units": ["Eliwood", "Marcus", "Lowen", "Rebecca", "Bartre"],
        "needs_verification": True,
    },
    12: {
        "name": "Chapter 12: Birds of a Feather",
        "objective_type": "defeat_boss",
        "objective": "Defeat all enemies or defeat boss",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated"],
        "notes": "Protect villages from bandits.",
        "new_units": [],
        "needs_verification": True,
    },
    13: {
        "name": "Chapter 13: In Search of Truth",
        "objective_type": "seize",
        "objective": "Seize the throne",
        "boss_char_id": 0x06,  # Guy is recruitable enemy
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated"],
        "notes": "Guy can be recruited by Matthew. Hector and the Ostia group join.",
        "new_units": ["Hector", "Oswin", "Serra", "Matthew", "Guy"],
        "needs_verification": True,
    },
    14: {
        "name": "Chapter 14: False Friends",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating Erik",
        "boss_char_id": 0x45,
        "boss_name": "Erik",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Erik is a Cavalier. Erk and Priscilla join.",
        "new_units": ["Erk", "Priscilla"],
        "needs_verification": True,
    },
    15: {
        "name": "Chapter 15: Talons Alight",
        "objective_type": "defeat_boss",
        "objective": "Defeat all enemies",
        "boss_char_id": 0x46,
        "boss_name": "Sealen",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Lyn, Wil, Kent, Sain, and Florina rejoin if Lyn Mode was completed.",
        "new_units": ["Lyn", "Wil", "Kent", "Sain", "Florina"],
        "needs_verification": True,
    },
    16: {
        "name": "Chapter 16: Noble Lady of Caelin",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating Bauker",
        "boss_char_id": 0x47,
        "boss_name": "Bauker",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Raven can be recruited by Priscilla. He starts as an enemy!",
        "new_units": ["Raven"],
        "needs_verification": True,
    },
    17: {
        "name": "Chapter 17: Whereabouts Unknown",
        "objective_type": "seize",
        "objective": "Seize the throne",
        "boss_char_id": 0x48,
        "boss_name": "Bernard",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Canas can be recruited by visiting a village. Fog of war chapter.",
        "new_units": ["Canas"],
        "needs_verification": True,
    },
    18: {
        "name": "Chapter 18: Pirate Ship",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Damian",
        "boss_char_id": 0x49,
        "boss_name": "Damian",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Ship battle. Dart joins. Limited space for combat.",
        "new_units": ["Dart"],
        "needs_verification": True,
    },
    19: {
        "name": "Chapter 19: The Dread Isle",
        "objective_type": "defeat_boss",
        "objective": "Defeat all enemies or reach destination",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Legault can be recruited by talking to him. He's a Thief.",
        "new_units": ["Legault"],
        "needs_verification": True,
    },
    20: {
        "name": "Chapter 20: Dragon's Gate",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Darin",
        "boss_char_id": 0x4D,
        "boss_name": "Darin",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Darin is a General. Major story chapter.",
        "new_units": [],
        "needs_verification": True,
    },
    21: {
        "name": "Chapter 21: New Resolve",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Oleg",
        "boss_char_id": 0x4F,
        "boss_name": "Oleg",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Heath can be recruited. Hawkeye joins automatically.",
        "new_units": ["Heath", "Hawkeye"],
        "needs_verification": True,
    },
    22: {
        "name": "Chapter 22: Kinship's Bond",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Eubans",
        "boss_char_id": 0x50,
        "boss_name": "Eubans",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Ninian rejoins. Fiora can be recruited by talking with Florina.",
        "new_units": ["Ninian", "Fiora"],
        "needs_verification": True,
    },
    23: {
        "name": "Chapter 23: Living Legend",
        "objective_type": "defeat_boss",
        "objective": "Defeat all enemies",
        "boss_char_id": None,
        "boss_name": None,
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated", "Pent is defeated"],
        "notes": "Desert chapter. Pent and Louise join. Hawkeye NPC. Sand reduces mounted movement.",
        "new_units": ["Pent", "Louise"],
        "needs_verification": True,
    },
    24: {
        "name": "Chapter 24: Four-Fanged Offense",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Lloyd or Linus",
        "boss_char_id": 0x63,
        "boss_name": "Lloyd",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Fight either Lloyd (Swordmaster) or Linus (Hero) depending on lords' levels.",
        "new_units": [],
        "needs_verification": True,
    },
    25: {
        "name": "Chapter 25: Crazed Beast",
        "objective_type": "seize",
        "objective": "Seize the throne after defeating boss Pascal",
        "boss_char_id": 0x57,
        "boss_name": "Pascal",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Farina can be recruited (costs 20000 gold). Isadora joins.",
        "new_units": ["Farina", "Isadora"],
        "needs_verification": True,
    },
    26: {
        "name": "Chapter 26: Unfulfilled Heart",
        "objective_type": "seize",
        "objective": "Seize the throne",
        "boss_char_id": 0x58,
        "boss_name": "Kenneth",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Split path chapter. Fight Kenneth (Bishop) or Jerme (Assassin).",
        "new_units": ["Harken"],
        "needs_verification": True,
    },
    27: {
        "name": "Chapter 27: Pale Flower of Darkness",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Sonia or Limstella",
        "boss_char_id": 0x5B,
        "boss_name": "Sonia",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated", "Nino is defeated"],
        "notes": "Nino and Jaffar join. Recruit Nino, then talk to Jaffar with Nino.",
        "new_units": ["Nino", "Jaffar"],
        "needs_verification": True,
    },
    28: {
        "name": "Chapter 28: Valorous Roland / Cog of Destiny",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Lloyd or Linus",
        "boss_char_id": 0x65,
        "boss_name": "Lloyd",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Fight the other Four Fang brother. Very strong boss. Vaida joins (or is boss depending on route).",
        "new_units": ["Vaida"],
        "needs_verification": True,
    },
    29: {
        "name": "Chapter 29: Sands of Time",
        "objective_type": "defeat_boss",
        "objective": "Defeat boss Denning",
        "boss_char_id": 0x60,
        "boss_name": "Denning",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Renault joins. Large map with many morphs. Karla can be recruited (requires Bartre Lv5+ as Warrior).",
        "new_units": ["Renault", "Karla"],
        "needs_verification": True,
    },
    30: {
        "name": "Chapter 30: Victory or Death",
        "objective_type": "defeat_boss",
        "objective": "Defeat Nergal",
        "boss_char_id": 0x44,
        "boss_name": "Nergal",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Athos joins. Many morph bosses. Limstella guards Nergal. Sacred weapons available.",
        "new_units": ["Athos"],
        "needs_verification": True,
    },
    31: {
        "name": "Final: Light",
        "objective_type": "defeat_boss",
        "objective": "Defeat the Fire Dragon",
        "boss_char_id": 0x86,
        "boss_name": "Dragon",
        "seize_position": None,
        "turn_limit": None,
        "defeat_conditions": ["Eliwood is defeated", "Hector is defeated"],
        "notes": "Final chapter. Fire Dragon has massive HP and stats. Use legendary weapons. Athos with Forblaze/Aureola is key.",
        "new_units": [],
        "needs_verification": True,
    },
}


def get_chapter_objective(chapter_number) -> dict | None:
    """Get chapter objective data by chapter number.

    Args:
        chapter_number: Chapter number as read from memory

    Returns:
        Dict with objective data, or None if chapter not found
    """
    return FE7_CHAPTERS.get(chapter_number)


def get_objective_text(chapter_number) -> str:
    """Get a human-readable objective string for the LLM.

    Args:
        chapter_number: Chapter number as read from memory

    Returns:
        Formatted string describing the chapter objective
    """
    data = FE7_CHAPTERS.get(chapter_number)
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
