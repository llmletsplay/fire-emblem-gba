# FE8 Data Coverage Audit

What we read from memory vs what's available but not yet implemented.

## What We Read

### Game State (all verified)

| Data | Address | Size | Status | Source File |
|------|---------|------|--------|-------------|
| Phase byte | `0x0202BCF9` | u8 | Live-verified | `fe8_memory_reader.py` |
| Chapter number | `0x0202BCFE` | u8 | Live-verified | `fe8_memory_reader.py` |
| Turn counter | `0x0202BD00` | u8 | Live-verified | `fe8_memory_reader.py` |
| Cursor X | `0x0202BD02` | u8 | Live-verified | `fe8_memory_reader.py` |
| Cursor Y | `0x0202BD03` | u8 | Live-verified | `fe8_memory_reader.py` |

### Unit Arrays (all verified)

| Array | Address | Count | Struct Size | Total |
|-------|---------|-------|-------------|-------|
| Player (Blue) | `0x0202BE4C` | 62 | 0x48 (72) | 4464 bytes |
| Enemy (Red) | `0x0202CFBC` | 50 | 0x48 (72) | 3600 bytes |
| NPC (Green) | `0x0202DDCC` | 20 | 0x48 (72) | 1440 bytes |

### Unit Fields We Parse (per unit)

| Field | Offset | Size | Verified |
|-------|--------|------|----------|
| Character pointer (→ char ID) | 0x00 | 4 (ptr) | Yes |
| Class pointer (→ class ID) | 0x04 | 4 (ptr) | Yes |
| Level | 0x08 | 1 | Yes |
| EXP | 0x09 | 1 | Yes |
| Index / Allegiance | 0x0B | 1 | Yes |
| State flags | 0x0C | 4 | Yes |
| X position | 0x10 | 1 | Yes |
| Y position | 0x11 | 1 | Yes |
| Max HP | 0x12 | 1 | Yes |
| Current HP | 0x13 | 1 | Yes |
| Strength | 0x14 | 1 | Yes |
| Skill | 0x15 | 1 | Yes |
| Speed | 0x16 | 1 | Yes |
| Defense | 0x17 | 1 | Yes |
| Resistance | 0x18 | 1 | Yes |
| Luck | 0x19 | 1 | Yes |
| Con bonus | 0x1A | 1 | Yes |
| Mov bonus | 0x1D | 1 | Yes |
| Items (5 slots) | 0x1E | 10 | Yes |
| Weapon ranks (8 types) | 0x28 | 8 | Yes |
| Status effect + duration | 0x30 | 1 | Yes |
| Torch/barrier duration | 0x31 | 1 | Yes |

### Lookup Tables (hardcoded from decomp)

| Table | Count | Source |
|-------|-------|--------|
| Characters | ~80 | `fe8_lookup.py` (from `constants/characters.h`) |
| Classes | ~100 | `fe8_lookup.py` (from `constants/classes.h`) |
| Items | ~160 | `fe8_lookup.py` (from `constants/items.h`) |
| Status effects | ~10 | `fe8_lookup.py` |
| Weapon ranks | 8 types | `fe8_lookup.py` |
| Chapter objectives | 22 chapters | `fe8_chapters.py` |

---

## What We DON'T Read (but could)

### Easy to Add (data is in unit struct, just not parsed)

| Data | Offset | Notes | Difficulty |
|------|--------|-------|------------|
| AI flags | 0x0A | Enemy AI behavior type | Easy |
| Rescue target | 0x1B | Who this unit is rescuing/rescued by | Easy |
| Ballista index | 0x1C | Which ballista unit is on | Easy |
| Support levels | 0x32-0x47 | 22 bytes of support data per unit | Easy |

### Medium Difficulty (known addresses, need parsing work)

| Data | Address/Location | Notes | Difficulty |
|------|-----------------|-------|------------|
| Battle forecast | `0x0203A958` | Hit%, crit%, damage preview during combat | Medium |
| Map terrain | `gBmMap` pointer | 2D array of terrain types per tile | Medium |
| Map dimensions | Chapter data table | Width/height of current map | Medium |
| Movement costs | Class data in ROM | Per-class terrain movement costs | Medium |

### Hard / Unknown (need research)

| Data | Notes | Difficulty |
|------|-------|------------|
| Convoy inventory | Items stored outside party — address unknown | Hard |
| Shop inventory | Dynamic per chapter, address unknown | Hard |
| Fog of war state | Per-tile visibility, unclear address | Hard |
| Event flags | Chapter event completion tracking | Hard |
| Danger zone | Computed from enemy movement + attack range | Compute (not memory) |

### Unreliable (tried, didn't work)

| Data | Address | Problem |
|------|---------|---------|
| Menu state | `0x030030C4` (IWRAM) | Reads non-zero during normal gameplay |
| Battle active | `0x0203A4D0` | Reads non-zero during normal gameplay |
| Old chapter addr | `0x0202BCF0` | Returns garbage, wrong address |
| Old cursor addr | `0x0202E4DC/DE` | Contains EWRAM pointers, not coordinates |

---

## Data Sources

### ROM (static, cacheable)
- Character data tables (names, base stats, growths)
- Class data tables (names, base stats, movement)
- Item data tables (names, stats, weapon type)
- Map data per chapter

### EWRAM (dynamic, read each cycle)
- Unit arrays (positions, stats, items change during gameplay)
- Game state (chapter, turn, cursor, phase)

### IWRAM (dynamic, mostly unreliable for us)
- Menu state — too transient to read reliably over socket
- Battle calculations — same problem

---

## Improvement Priorities

1. **Battle forecast** — Would let the AI know hit/damage before committing to attacks
2. **Map terrain** — Would enable terrain-aware pathfinding and positioning
3. **Support data** — Low effort, useful for tracking support conversations
4. **Enemy AI flags** — Would help predict enemy behavior patterns
