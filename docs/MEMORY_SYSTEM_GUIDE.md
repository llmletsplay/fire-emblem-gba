# Memory System Guide

The memory system reads live GBA Fire Emblem state from mGBA through a Lua TCP
socket. It supports FE7 and FE8 with one shared Python reader and per-game
address metadata.

## Supported Games

| Game | ROM code | Title | Status |
| --- | --- | --- | --- |
| FE7 | `AE7E` | Fire Emblem: The Blazing Blade | Live memory support, tutorial handling, lookup tables, chapter data |
| FE8 | `BE8E` | Fire Emblem: The Sacred Stones | Live memory support, richer bundled assets, lookup tables, chapter data |

## Bridge

`lua/socketserver.lua` runs inside mGBA and exposes:

- `READRANGE <address> <length>` for raw memory bytes
- `CAP` for a 240x160 screenshot
- semicolon-delimited button input queues
- `LOADSTATE <slot>` and `SAVESTATE <slot>`
- FE7/FE8 helper commands loaded from `lua/fe7_memory.lua` and
  `lua/fe8_memory.lua`

The Python side connects to `localhost:${FE_MGBA_PORT:-8888}`.

## Reader Pipeline

1. `src/data/game_registry.py` maps ROM code to a `GameInfo` object.
2. `src/utils/memory_reader.py` uses that `GameInfo` to read the correct memory
   addresses.
3. Unit arrays are read in bulk:
   - 62 player units
   - 50 enemy units
   - 20 NPC units
   - 0x48-byte shared unit struct
4. ROM pointers in unit structs are dereferenced to character/class IDs.
5. `src/game/fe_state.py` resolves IDs into names and builds LLM/frontend JSON.

## Core Fields

| Field | FE7 | FE8 |
| --- | --- | --- |
| Phase | `0x0202BC07` | `0x0202BCF9` |
| Chapter | `0x0202BC06` | `0x0202BCFE` |
| Turn | `0x0202BC08` | `0x0202BD00` |
| Cursor X/Y | `0x0202BC0A/0x0202BC0B` | `0x0202BD02/0x0202BD03` |
| Player units | `0x0202BD08` | `0x0202BE4C` |
| Enemy units | `0x0202CE78` | `0x0202CFBC` |
| NPC units | `0x0202DC88` | `0x0202DDCC` |

FE7 phase uses allegiance encoding (`0x00`, `0x80`, `0x40`). FE8 phase uses
sequential encoding (`0`, `1`, `2`).

## Unit Struct

Both games use the same 0x48-byte unit struct layout for the fields the harness
currently reads:

| Offset | Field |
| --- | --- |
| `0x00` | Character data pointer |
| `0x04` | Class data pointer |
| `0x08` | Level |
| `0x0A` | AI flags |
| `0x0B` | Unit index / allegiance |
| `0x0C` | State flags |
| `0x10/0x11` | X/Y position |
| `0x12/0x13` | Max/current HP |
| `0x14-0x19` | Core stats |
| `0x1B` | Rescue target |
| `0x1D` | Movement bonus |
| `0x1E` | Items |
| `0x28` | Weapon ranks |
| `0x30` | Status effect and duration |

The reader treats hidden, dead, not-deployed, rescued, and moved flags carefully
because some bit meanings differ between FE7 and FE8.

## State Payload

`prep_fe_llm(sock)` produces a context payload with:

- `game`, `game_title`, `chapter`, `turn`, `phase`
- `cursor`, `display_cursor`, `camera`, `input_locked`
- `party`, `enemies`, `allies`
- `unit_status` and `unmoved_count`
- `objective`, `objective_type`, boss/seize metadata when known
- `terrain_at_cursor`, movement tiles, attack opportunities when available
- tutorial fields for FE7 Lyn's Tale when `FE_TUTORIAL=true`

Memory-derived fields should be treated as stronger than screenshot-derived
fields when they disagree.

## Known Gaps

- Battle forecast data is not yet exposed.
- FE8 BmSt addresses include estimated fields that should continue to be live
  verified.
- FE7 event slots for tutorial targets are not reliable; the harness uses
  validated chapter-script fallbacks.
- Terrain-aware pathfinding is partial and should stay conservative until map
  dimensions and movement costs are fully verified per chapter.

## Verification

Use `tools/memory_probe.py` against a live mGBA session:

```bash
python tools/memory_probe.py --diag
```

For code-level checks:

```bash
python -m pytest
```

See also:

- `docs/FE7_FE8_DATA_COVERAGE.md`
- `docs/FE7_MEMORY_MAP.md`
- `docs/FE8_MEMORY_MAP.md`
