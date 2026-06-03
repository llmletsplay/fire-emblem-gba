# Fire Emblem GBA Data Coverage Audit

What we read from memory vs what's available but not yet implemented.
Covers both FE7 (Blazing Blade) and FE8 (Sacred Stones).

---

## What We Read

### Game State (all verified)

| Data | FE7 Address | FE8 Address | Size | Status |
|------|-------------|-------------|------|--------|
| Phase byte | `0x0202BC07` | `0x0202BCF9` | u8 | Both verified |
| Chapter number | `0x0202BC06` | `0x0202BCFE` | u8 | Both verified |
| Turn counter | `0x0202BC08` | `0x0202BD00` | u8 | Both verified |
| Cursor X | `0x0202BC0A` | `0x0202BD02` | u8 | Both verified |
| Cursor Y | `0x0202BC0B` | `0x0202BD03` | u8 | Both verified |

**Phase encoding difference:**
- FE7: Allegiance encoding (0x00=Player, 0x80=Enemy, 0x40=NPC)
- FE8: Sequential encoding (0=Player, 1=Enemy, 2=NPC)

### Unit Arrays

| Array | FE7 Address | FE8 Address | Count | Struct Size | Total |
|-------|-------------|-------------|-------|-------------|-------|
| Player (Blue) | `0x0202BD08` | `0x0202BE4C` | 62 | 0x48 (72) | 4464 bytes |
| Enemy (Red) | `0x0202CE78` | `0x0202CFBC` | 50 | 0x48 (72) | 3600 bytes |
| NPC (Green) | `0x0202DC88` | `0x0202DDCC` | 20 | 0x48 (72) | 1440 bytes |

### Unit Fields We Parse (per unit)

| Field | Offset | Size | Verified | Notes |
|-------|--------|------|----------|-------|
| Character pointer (→ char ID) | 0x00 | 4 (ptr) | Yes | Dereference to get ID |
| Class pointer (→ class ID) | 0x04 | 4 (ptr) | Yes | Dereference to get ID |
| Level | 0x08 | 1 | Yes | |
| EXP | 0x09 | 1 | Yes | |
| AI flags | 0x0A | 1 | **Now added** | Enemy AI behavior type |
| Index / Allegiance | 0x0B | 1 | Yes | bits 6-7 = faction |
| State flags | 0x0C | 4 | Yes | Bitmask |
| X position | 0x10 | 1 | Yes | |
| Y position | 0x11 | 1 | Yes | |
| Max HP | 0x12 | 1 | Yes | |
| Current HP | 0x13 | 1 | Yes | |
| Strength | 0x14 | 1 | Yes | |
| Skill | 0x15 | 1 | Yes | |
| Speed | 0x16 | 1 | Yes | |
| Defense | 0x17 | 1 | Yes | |
| Resistance | 0x18 | 1 | Yes | |
| Luck | 0x19 | 1 | Yes | |
| Con bonus | 0x1A | 1 | Yes | |
| Rescue target | 0x1B | 1 | **Now added** | Unit being rescued |
| Ballista index | 0x1C | 1 | **Now added** | Which ballista |
| Mov bonus | 0x1D | 1 | Yes | |
| Items (5 slots) | 0x1E | 10 | Yes | |
| Weapon ranks (8 types) | 0x28 | 8 | Yes | |
| Status effect + duration | 0x30 | 1 | Yes | |
| Torch/barrier duration | 0x31 | 1 | Yes | |

### Battle Map State (BmSt)

| Data | FE7 Address | FE8 Address (est.) | Status |
|------|-------------|---------------------|--------|
| Input lock | `0x0202BBB9` | `0x0202BCB1` | Both verified/estimated |
| Game state bits | `0x0202BBBC` | `0x0202BCB4` | Both verified/estimated |
| Camera X | `0x0202BBC4` | `0x0202BCBC` | Both verified/estimated |
| Camera Y | `0x0202BBC6` | `0x0202BCBE` | Both verified/estimated |
| Display cursor X | `0x0202BBCC` | `0x0202BCC4` | Both verified/estimated |
| Display cursor Y | `0x0202BBCE` | `0x0202BCC6` | Both verified/estimated |
| Taken action | `0x0202BBF5` | `0x0202BCED` | Both verified/estimated |

### Screenshot

| Data | Status |
|------|--------|
| 240x160 ARGB32 capture | Implemented via `CAP` command |

---

## What We DON'T Read (but could)

### Easy to Add (data is in unit struct, just not fully exposed)

| Data | Offset | Notes | Priority |
|------|--------|-------|----------|
| Support levels | 0x32-0x47 | 22 bytes of support data per unit | Low |
| Full rescue chain | 0x1B | Already parsing, could expose rescued unit name | Low |

### Medium Difficulty (requires research)

| Data | Address | Notes | Priority |
|------|---------|-------|----------|
| Battle forecast | `0x0203A958` (FE8) | Hit%, crit%, damage preview during combat | **High** |
| Map terrain | `0x0202E3D8` | 2D array of terrain types per tile | **High** |
| Map dimensions | Chapter data table | Width/height of current map | Medium |
| Movement costs | Class data in ROM | Per-class terrain movement costs | Medium |
| Fog of war state | Unknown | Per-tile visibility | Medium |

### Hard / Unknown (need research)

| Data | Notes | Priority |
|------|-------|----------|
| Convoy inventory | Items stored outside party — address unknown | Low |
| Shop inventory | Dynamic per chapter, address unknown | Low |
| Event flags | Chapter event completion tracking | Medium |
| Danger zone | Computed from enemy movement + attack range | Compute (not memory) |
| AI behavior patterns | Enemy AI decision-making | Hard |

### Tutorial Target - VERIFIED NOT IN RAM

| Data | FE7 Status | FE8 Status | Notes |
|------|-------------|------------|-------|
| Tutorial target from event slots | **NOT IN RAM** | `0x030004B8` | FE7 computes targets dynamically |
| Tutorial target from screenshot | Implemented but flawed | N/A | Detects movement highlights incorrectly |
| Tutorial target hardcoded | Chapter 0: (9,8) | None | **Only solution for FE7** |

**Finding**: After RAM search verification, FE7 does NOT store tutorial targets in memory. The flashing indicators (movement/attack range) are computed on-the-fly by the event engine from unit stats and map data.

**Solution**: Use hardcoded chapter-based targets in `src/data/fe7_chapters.py`. The LLM should also read dialogue text and look at screenshot for visual cues.

---

## Lookup Tables

| Table | FE7 Count | FE8 Count | Source |
|-------|-----------|-----------|--------|
| Characters | ~60 | ~80 | `fe7_lookup.py` / `fe8_lookup.py` |
| Classes | ~50 | ~100 | Lookup modules |
| Items | ~100 | ~160 | Lookup modules |
| Status effects | ~10 | ~10 | Lookup modules |
| Weapon ranks | 8 types | 8 types | Lookup modules |
| Chapter objectives | 31 chapters | 22 chapters | `fe7_chapters.py` / `fe8_chapters.py` |

---

## Addresses Unique to Each Game

### FE7 Only
- Event slots base: **Unknown** (needs discovery)
- Uses allegiance encoding for phase (0x00/0x40/0x80)

### FE8 Only
- Event slots base: `0x030004B8` (verified via decomp)
- Uses sequential encoding for phase (0/1/2)

---

## References

1. [FE7 Memory Map](FE7_MEMORY_MAP.md)
2. [FE8 Memory Map](FE8_MEMORY_MAP.md)
3. [FE8 Decomp](https://github.com/FireEmblemUniverse/fireemblem8u)
4. [EmblemMind FE7 Project](https://github.com/Wreaperz/EmblemMind) - Found additional addresses

---

## Improvement Priorities

1. **Battle forecast** — Would let the AI know hit/damage before committing to attacks
2. **Map terrain** — Would enable terrain-aware pathfinding and positioning
3. **FE7 event slots** — Tutorial target discovery for FE7
4. **Support data** — Low effort, useful for tracking support conversations
5. **Enemy AI flags** — Would help predict enemy behavior patterns
