# Fire Emblem 7: The Blazing Blade - Memory Map

All addresses verified against live memory dumps from mGBA.

## GBA Memory Regions
| Region | Range | Size |
|--------|-------|------|
| IWRAM | `0x03000000 - 0x03007FFF` | 32KB |
| EWRAM | `0x02000000 - 0x0203FFFF` | 256KB |
| ROM | `0x08000000+` | Variable |

## ROM Header
| Address | Size | Description |
|---------|------|-------------|
| `0x080000AC` | 4 bytes | Game code: "AE7E" |

## Unit Arrays

Units are stored in three fixed arrays in EWRAM. Each unit is **0x48 (72) bytes**.

| Array | Base Address | Count | Size | Status |
|-------|-------------|-------|------|--------|
| Player (Blue) | `0x0202BD08` | 62 | `0x1170` | **Verified** (Lyn at slot 1 confirmed) |
| Enemy (Red) | `0x0202CE78` | 50 | `0x0E10` | **Verified** (Batta + Brigand in Prologue) |
| NPC (Green) | `0x0202DC88` | 20 | `0x05A0` | Computed (needs live verification) |

Arrays are contiguous in EWRAM:
- Enemy address: `0x0202BD08 + 62 * 0x48 = 0x0202CE78`
- NPC address: `0x0202CE78 + 50 * 0x48 = 0x0202DC88`
- (Purple[5] starts at `0x0202DC88 + 20 * 0x48 = 0x0202E1E8`)

## Unit Struct Layout (0x48 bytes)

Source: FE7 uses the same engine as FE8, verified via live memory dumps.

```
Offset | Size | Type   | Field           | Notes
-------|------|--------|-----------------|----------------------------------
0x00   | 4    | ptr    | pCharData       | Pointer to CharacterData in ROM
0x04   | 4    | ptr    | pClassData      | Pointer to ClassData in ROM
0x08   | 1    | s8     | level          |
0x09   | 1    | u8     | exp            |
0x0A   | 1    | u8     | aiFlags        | Enemy AI behavior type
0x0B   | 1    | s8     | index          | bits 6-7 = allegiance
0x0C   | 4    | u32    | state          | Bitmask (see State Flags)
0x10   | 1    | s8     | xPos           |
0x11   | 1    | s8     | yPos           |
0x12   | 1    | s8     | maxHP          |
0x13   | 1    | s8     | curHP          |
0x14   | 1    | s8     | pow            | Strength/Magic
0x15   | 1    | s8     | skl            |
0x16   | 1    | s8     | spd            |
0x17   | 1    | s8     | def            |
0x18   | 1    | s8     | res            |
0x19   | 1    | s8     | lck            |
0x1A   | 1    | s8     | conBonus       |
0x1B   | 1    | u8     | rescueOtherUnit | Unit being rescued by this unit
0x1C   | 1    | u8     | ballistaIndex  | Which ballista (if any)
0x1D   | 1    | s8     | movBonus       |
0x1E   | 10   | u16[5] | items          | 5 item slots (see Item Encoding)
0x28   | 8    | u8[8]  | ranks          | Weapon ranks (see Weapon Types)
0x30   | 1    | u8     | statusIndex    | bits 0-3: effect, bits 4-7: duration
0x31   | 1    | u8     | torchBarrier    | bits 0-3: torch, bits 4-7: barrier
0x32   | 22   |        | supports        | Support data (C-B-A levels)
```

### Character/Class ID Extraction

The `pCharData` and `pClassData` fields are **4-byte ROM pointers**, NOT direct IDs!

To get the actual character/class ID:
1. Read the 4-byte pointer at unit offset `0x00` (or `0x04`)
2. Verify it's a valid ROM pointer (`>= 0x08000000`)
3. Read the byte at `pointer + 0x04` — this is the `number` field (the actual ID)

### Allegiance Constants

Encoded in bits 6-7 of the `index` byte at offset `0x0B`:

| Value | Name | Notes |
|-------|------|-------|
| `0x00` | Player (Blue) | FACTION_BLUE |
| `0x40` | NPC/Ally (Green) | FACTION_GREEN |
| `0x80` | Enemy (Red) | FACTION_RED |
| `0xC0` | Purple | FACTION_PURPLE |

**Important**: FE7 uses **allegiance encoding** (0x00/0x40/0x80), NOT sequential encoding (0/1/2) like FE8.

### State Flags (u32 bitmask at offset 0x0C)

| Bit | Value | Constant | Meaning |
|-----|-------|----------|---------|
| 0 | `0x01` | US_HIDDEN | Unit hidden from rendering |
| 1 | `0x02` | US_HAS_ACTED | Unit has acted this turn (FE7 specific) |
| 2 | `0x04` | US_NOT_DEPLOYED | Not on map |
| 4 | `0x10` | US_RESCUING | Rescuing another unit |
| 5 | `0x20` | US_RESCUED | Being rescued by another unit |
| 6 | `0x40` | US_HAS_MOVED | Has moved this turn |

**Note**: In FE7, bit 0x02 means HAS_ACTED (unit grayed out). In FE8, it means DEAD. Use HP and NOT_DEPLOYED for liveness.

### Item Encoding (u16)

Each item slot is a 16-bit value:
- Bits 0-7: Item index (see `constants/items.h`)
- Bits 8-15: Uses remaining

### Weapon Rank Order (8 bytes at offset 0x28)

| Index | Type |
|-------|------|
| 0 | Sword |
| 1 | Lance |
| 2 | Axe |
| 3 | Bow |
| 4 | Staff |
| 5 | Anima |
| 6 | Light |
| 7 | Dark |

Rank thresholds: E=1, D=31, C=71, B=121, A=181, S=251

### Status Effects (offset 0x30, lower nibble)

| Value | Effect |
|-------|--------|
| 0 | None |
| 1 | Poison |
| 2 | Sleep |
| 3 | Silence |
| 4 | Berserk |
| 5 | Attack boost |
| 6 | Defense boost |
| 13 | Petrify |

## Game State Addresses (PlaySt)

| Address | Size | Description | Status |
|---------|------|-------------|--------|
| `0x0202BC06` | 1 | Chapter (u8) | **Verified** (1=Ch1) |
| `0x0202BC07` | 1 | Phase byte (u8) | **Verified** - allegiance encoding: 0x00=Player, 0x80=Enemy, 0x40=NPC |
| `0x0202BC08` | 1 | Turn number (u8) | **Verified** (01→05 across turns) |
| `0x0202BC0A` | 1 | Cursor X (u8) | **Verified** (matches unit position) |
| `0x0202BC0B` | 1 | Cursor Y (u8) | **Verified** (matches unit position) |

PlaySt base: `0x0202BC00` (chapter at +0x06)

## Battle Map State (BmSt)

| Address | Size | Field | Description | Status |
|---------|------|-------|-------------|--------|
| `0x0202BBB8` | 64 | BmSt base | 0x40 bytes | **Verified** |
| `0x0202BBB9` | 1 | lock | Input locked during dialogue/anim | **Verified** |
| `0x0202BBBC` | 1 | gameStateBits | Battle map state flags | **Verified** |
| `0x0202BBC4` | 2 | camera.x | Camera X position (s16, pixels) | **Verified** |
| `0x0202BBC6` | 2 | camera.y | Camera Y position (s16, pixels) | **Verified** |
| `0x0202BBCC` | 2 | playerCursor.x | Display cursor X (s16, tiles) | **Verified** |
| `0x0202BBCE` | 2 | playerCursor.y | Display cursor Y (s16, tiles) | **Verified** |
| `0x0202BBF5` | 1 | taken_action | Last action type taken | **Verified** |

BmSt base: `0x0202BBB8` (PlaySt - 0x40)

### BmSt Field Details

- **lock** (0x0202BBB9): 0 = input free, >0 = input locked (dialogue/animation active)
- **camera**: Pixel coordinates (tile * 16 - offset). GBA screen is 240x160, centered on cursor.
- **playerCursor**: Live display cursor position (accurate during movement/tutorials, unlike PlaySt cursor)
- **gameStateBits**: Various state flags (turnwheel active, etc.)
- **taken_action**: Action type of last action (0=none, 1=attack, 2=item, etc.)

## Additional Memory Regions (from research)

| Address | Size | Description | Notes |
|---------|------|-------------|-------|
| `0x0202E3D8` | ? | Map terrain data | Width, height, terrain grid |
| `0x0203A3F0` | ? | Battle structs | Combat stats and calculations |
| `0x0203A958` | ? | Battle forecast | Hit%, crit%, damage preview during combat |

Note: These addresses may differ slightly between FE7 and FE8. Battle forecast address from FE8 (0x0203A958) may need adjustment for FE7.

## Unreliable / Unused Addresses

| Address | Problem |
|---------|---------|
| `0x030030C4` (IWRAM) | Menu state - reads non-zero during normal gameplay |
| `0x0203A4D0` | Battle active flag - unreliable |

## Screenshot Capture

- Resolution: 240x160 (GBA native)
- Format: ARGB32 pixels
- Command: `CAP` via Lua socket server
- Implementation: `lua/socketserver.lua:304-326`

## Diagnostic Tools

- **Memory Probe**: `python tools/memory_probe.py --watch` — reads all addresses and displays with proper pointer dereferencing
- **mGBA Launch**: `./scripts/run_mgba.sh` — starts emulator with Lua socket server
- **Find BmSt**: `python tools/memory_probe.py --find-bmst` — discover BmSt struct address

## Verification Checklist

- [x] Load Prologue save → verify Lyn (ID 0x04) at slot 1 in player array
- [x] Check classes resolve correctly (Lyn = 0x01, Merchant = 0x02, etc.)
- [x] Verify enemy units appear in enemy array at 0x0202CE78 (Batta + Brigand)
- [x] Confirm allegiance: player=0x00, enemy=0x80, NPC=0x40
- [x] Cursor at 0x0202BC0A/0B matches on-screen cursor position
- [x] Turn counter at 0x0202BC08 increments on turn end
- [x] Item names resolve correctly (Rapier, Iron Sword, etc.)
- [ ] NPC array at 0x0202DC88 live verification
- [ ] Chapter address verification with later chapters

## Tutorial Target Detection - VERIFIED NOT IN RAM

**Important Discovery**: After multiple RAM searches during FE7 tutorials, we found that **FE7 does NOT store tutorial targets in memory**. The coordinates are computed dynamically by the event engine.

### Evidence

| Test | Target Coordinates | RAM Result |
|------|-------------------|------------|
| Turn 1 movement | (9, 8) | Not found in IWRAM/EWRAM |
| Attack range | (7,5), (6,6), (8,6), (7,7) | Not found in IWRAM/EWRAM |

The flashing yellow/white indicators (movement range, attack range) are rendered directly from:
- Unit stats (movement, attack range)
- Map terrain data
- Computed on-the-fly by the game engine

They are NOT stored as coordinate pairs in any RAM region we can read.

### Solution

We use **hardcoded chapter-based tutorial targets** as a fallback:

As of the MiniMax harness refresh,  **hard-prefers** the active  destination (derived in  when RAM/screenshot miss) so MOVE confirm lands on the forced Ch0+ tile:
- FE7 Chapter 0 (Prologue): (9, 8)
- This is documented in `src/data/fe7_chapters.py`

For AI gameplay, the LLM should:
1. Read the **dialogue text** - it tells you exactly what to do
2. Look at the **screenshot** - blue tiles = movement, white/yellow = attack range
3. Follow the **hardcoded tutorial_target** when available

## References

1. [FE Universe](https://feuniverse.us/)
2. [FE7 ROM Data](https://github.com/StanH/fe7-doc)
3. [Fire Emblem GBA Disassembly](https://github.com/FireEmblemUniverse/)
