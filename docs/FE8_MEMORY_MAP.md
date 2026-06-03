# Fire Emblem 8: The Sacred Stones - Memory Map

All addresses verified against the [FE8 decomp](https://github.com/FireEmblemUniverse/fireemblem8u) (US version).

## GBA Memory Regions
| Region | Range | Size |
|--------|-------|------|
| IWRAM | `0x03000000 - 0x03007FFF` | 32KB |
| EWRAM | `0x02000000 - 0x0203FFFF` | 256KB |
| ROM | `0x08000000+` | Variable |

## Unit Arrays

Units are stored in three fixed arrays in EWRAM. Each unit is **0x48 (72) bytes**.

| Array | Base Address | Count | Size | Source |
|-------|-------------|-------|------|--------|
| Player (Blue) | `0x0202BE4C` | 62 | `0x1170` | `gUnitArrayBlue[62]` |
| Enemy (Red) | `0x0202CFBC` | 50 | `0x0E10` | `gUnitArrayRed[50]` |
| NPC (Green) | `0x0202DDCC` | 20 | `0x05A0` | `gUnitArrayGreen[20]` |

Arrays are contiguous in EWRAM:
- Enemy address: `0x0202BE4C + 62 * 0x48 = 0x0202CFBC`
- NPC address: `0x0202CFBC + 50 * 0x48 = 0x0202DDCC`
- (Purple[5] starts at `0x0202DDCC + 20 * 0x48 = 0x0202E36C`)

## Unit Struct Layout (0x48 bytes)

Source: `include/bmunit.h` → `struct Unit`

```
Offset | Size | Type | Field         | Notes
-------|------|------|---------------|----------------------------------
0x00   | 4    | ptr  | pCharData     | Pointer to CharacterData in ROM
0x04   | 4    | ptr  | pClassData    | Pointer to ClassData in ROM
0x08   | 1    | s8   | level         |
0x09   | 1    | u8   | exp           |
0x0A   | 1    | u8   | aiFlags       |
0x0B   | 1    | s8   | index         | bits 6-7 = allegiance
0x0C   | 4    | u32  | state         | Bitmask (see State Flags)
0x10   | 1    | s8   | xPos          |
0x11   | 1    | s8   | yPos          |
0x12   | 1    | s8   | maxHP         |
0x13   | 1    | s8   | curHP         |
0x14   | 1    | s8   | pow           | Strength/Magic
0x15   | 1    | s8   | skl           |
0x16   | 1    | s8   | spd           |
0x17   | 1    | s8   | def           |
0x18   | 1    | s8   | res           |
0x19   | 1    | s8   | lck           |
0x1A   | 1    | s8   | conBonus      |
0x1B   | 1    | u8   | rescueOtherUnit |
0x1C   | 1    | u8   | ballistaIndex |
0x1D   | 1    | s8   | movBonus      |
0x1E   | 10   | u16[5]| items        | 5 item slots (see Item Encoding)
0x28   | 8    | u8[8]| ranks         | Weapon ranks (see Weapon Types)
0x30   | 1    | u8   | statusIndex   | bits 0-3: effect, bits 4-7: duration
0x31   | 1    | u8   | torchBarrier  | bits 0-3: torch, bits 4-7: barrier
0x32-0x47 | 22 |     | (supports, etc) |
```

### Character/Class ID Extraction

The `pCharData` and `pClassData` fields are **4-byte ROM pointers**, NOT direct IDs!

To get the actual character/class ID:
1. Read the 4-byte pointer at unit offset `0x00` (or `0x04`)
2. Verify it's a valid ROM pointer (`>= 0x08000000`)
3. Read the byte at `pointer + 0x04` — this is the `number` field (the actual ID)

**Wrong approach** (what the old code did): `char_ptr & 0xFF` — this gives arbitrary values based on ROM layout.

### Allegiance Constants

Encoded in bits 6-7 of the `index` byte at offset `0x0B`:

| Value | Name | Decomp Constant |
|-------|------|-----------------|
| `0x00` | Player (Blue) | `FACTION_BLUE` |
| `0x40` | NPC/Ally (Green) | `FACTION_GREEN` |
| `0x80` | Enemy (Red) | `FACTION_RED` |
| `0xC0` | Purple | `FACTION_PURPLE` |

**Note**: Previous code had Enemy=0x40 and NPC=0x80 (swapped). This caused enemies to be misidentified as NPCs and dropped.

### State Flags (u32 bitmask at offset 0x0C)

| Bit | Value | Constant | Meaning |
|-----|-------|----------|---------|
| 0 | `0x01` | `US_HIDDEN` | Unit hidden |
| 1 | `0x02` | `US_DEAD` | Unit dead |
| 2 | `0x04` | `US_NOT_DEPLOYED` | Not on map |
| 4 | `0x10` | `US_RESCUING` | Rescuing another |
| 5 | `0x20` | `US_RESCUED` | Being rescued |
| 6 | `0x40` | `US_HAS_MOVED` | Has acted this turn |

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
| `0x0202BCF9` | 1 | Phase byte (u8) | **Verified** - sequential: 0=Player, 1=Enemy, 2=NPC |
| `0x0202BCFE` | 1 | Current chapter (u8) | **Verified** (0=Prologue, 1=Ch1, etc.) |
| `0x0202BD00` | 1 | Turn number | **Verified** (increments on turn end) |
| `0x0202BD02` | 1 | Cursor X (u8) | **Verified** (matches unit/cursor position) |
| `0x0202BD03` | 1 | Cursor Y (u8) | **Verified** (matches unit/cursor position) |
| `0x0202BCB4` | 1 | Game mode | Verified |

PlaySt base: `0x0202BCB0` (phase at -0x09)

## Battle Map State (BmSt)

| Address | Size | Field | Description | Status |
|---------|------|-------|-------------|--------|
| `0x0202BCB0` | 64 | BmSt base | 0x40 bytes | Estimated |
| `0x0202BCB1` | 1 | lock | Input locked during dialogue/anim | Estimated |
| `0x0202BCB4` | 1 | gameStateBits | Battle map state flags | Estimated |
| `0x0202BCBC` | 2 | camera.x | Camera X position (s16, pixels) | Estimated |
| `0x0202BCBE` | 2 | camera.y | Camera Y position (s16, pixels) | Estimated |
| `0x0202BCC4` | 2 | playerCursor.x | Display cursor X (s16, tiles) | Estimated |
| `0x0202BCC6` | 2 | playerCursor.y | Display cursor Y (s16, tiles) | Estimated |
| `0x0202BCED` | 1 | taken_action | Last action type taken | Estimated |

**Note**: BmSt addresses are estimated from PlaySt - 0x40 offset (same as FE7). Live verification recommended.

## gEventSlots (IWRAM)

| Address | Size | Description | Status |
|---------|------|-------------|--------|
| `0x030004B8` | 56 | gEventSlots[14] (14 x s32) | Verified via FE8 decomp |

Used for tutorial target coordinates and other event data.

## Additional Memory Regions (from research)

| Address | Size | Description | Notes |
|---------|------|-------------|-------|
| `0x0202E3D8` | ? | Map terrain data | Width, height, terrain grid |
| `0x0203A3F0` | ? | Battle structs | Combat stats and calculations |
| `0x0203A958` | ? | Battle forecast | Hit%, crit%, damage preview during combat |

## Unreliable / Unused Addresses

| Address | Problem |
|---------|---------|
| `0x030030C4` (IWRAM) | Menu state - reads non-zero during normal gameplay |
| `0x0203A4D0` | Battle active flag - unreliable |

Old/wrong addresses (DO NOT USE):
- `0x0202BCF0` - was labeled "chapter" but returns garbage
- `0x0202BCF8` - was labeled "turn" but reads 0 during gameplay
- `0x0202E4DC/DE` - was labeled "cursor" but contains EWRAM pointers, not coords

## Diagnostic Tools

- **Memory Probe**: `python tools/memory_probe.py --watch` — reads all addresses and displays with proper pointer dereferencing
- **mGBA Launch**: `./scripts/run_mgba.sh` — starts emulator with Lua socket server

## Verification Checklist

Use the memory probe to verify against in-game display:

- [x] Load Prologue save → verify Eirika (ID 0x01) + Seth (ID 0x02) names
- [x] Check classes resolve correctly (Lord Eirika = 0x02, Paladin = 0x07)
- [ ] Verify enemy units appear in enemy array at 0x0202CFBC
- [x] Confirm allegiance: player=0x00, enemy=0x80, NPC=0x40
- [x] Cursor at 0x0202BD02/03 matches on-screen cursor position
- [x] Turn counter at 0x0202BD00 increments on turn end
- [x] Item names resolve correctly (Rapier, Vulnerary, Silver Lance)
- [ ] NPC/green units appear when present on map
- [ ] Verify chapter address with a later chapter

## References

1. [FE8 Decomp (bmunit.h)](https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/bmunit.h)
2. [FE8 Characters](https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/characters.h)
3. [FE8 Classes](https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/classes.h)
4. [FE8 Items](https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/constants/items.h)
5. [FE Universe RAM offsets](https://feuniverse.us/t/fe8-ram-offset-of-other-units/233)
