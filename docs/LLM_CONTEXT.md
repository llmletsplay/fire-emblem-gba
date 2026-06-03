# LLM Context

This document describes what the model receives during each agent cycle.

## System Prompt

`src/llm/prompts.py` builds the primary prompt. The game title and lord names
come from the detected `GameInfo`, so the prompt can describe either FE7 or FE8.

The prompt includes:

- Recent memory and session statistics
- Controls reference
- FE tactical objectives such as seize, rout, defeat boss, and survive
- Weapon range and terrain guidance
- Title/menu/dialogue handling rules
- The preferred semantic `COMMAND:` response format

## State JSON

`src/game/fe_state.py` builds the base state from live memory:

```json
{
  "game": "fe7",
  "game_title": "Fire Emblem: The Blazing Blade",
  "chapter": 1,
  "turn": 3,
  "phase": "player_phase",
  "cursor": [13, 7],
  "display_cursor": [13, 7],
  "unit_status": {"Lyn": "available"},
  "objective": "Defeat the boss",
  "party": [
    {
      "name": "Lyn",
      "unitClass": "Lord",
      "hp": 18,
      "maxHp": 18,
      "x": 13,
      "y": 7,
      "hasMoved": false,
      "equippedWeapon": "Iron Sword"
    }
  ],
  "enemies": []
}
```

Game-specific objective and lookup fields come from `src/data/fe7_*` or
`src/data/fe8_*` modules selected by the registry.

## Driver Additions

`src/core/llmdriver.py` adds runtime context such as:

- Current screenshot
- Optional vision-model description
- Recent memory thumbnails
- Previous action and inferred screen context
- Failed tile/unit recovery hints
- Attack opportunities when movement plus enemy range can be derived

Memory-derived fields are treated as authoritative. Screenshot-derived fields
are useful for dialogue, visible menus, and overlays, but can be stale or
ambiguous.

## Response Format

The model should return one semantic command line:

```text
COMMAND: SELECT unit="Lyn"
COMMAND: MOVE to=[8,7]
COMMAND: ATTACK target="Batta"
COMMAND: WAIT
COMMAND: END_TURN
COMMAND: A
```

`src/game/command_parser.py` parses the command, `command_validator.py` checks it
against current memory state, and `command_executor.py` converts it to GBA
button input.

Raw button sequences remain available through `COMMAND: PRESS ...`, but semantic
commands are preferred because the executor can correct movement targets and
menu navigation.

## Known Blind Spots

The harness still has incomplete visibility into:

- Battle forecast hit/crit/damage
- Full enemy danger ranges
- Fog of war state
- Convoy/shop inventory
- Some FE7 tutorial internals
- Fully verified per-chapter map dimensions and terrain movement costs

These gaps should be handled conservatively in prompts and command validation.
