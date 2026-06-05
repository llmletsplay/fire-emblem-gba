"""
GBA Fire Emblem Game Registry

Central registry mapping ROM game codes to per-game configurations.
Supports FE7 (Blazing Blade) and FE8 (Sacred Stones).
"""

import struct
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GameAddresses:
    """Memory addresses for a specific GBA Fire Emblem game."""
    player_units: int
    enemy_units: int
    npc_units: int
    max_player: int
    max_enemy: int
    max_npc: int
    phase: int
    chapter: int
    turn: int
    cursor_x: int
    cursor_y: int
    # BmSt (Battle Map State) — set to 0 until verified via memory_probe --find-bmst
    bm_lock: int = 0         # BmSt.lock (+0x01) — 0=free, >0=input locked (dialogue/anim)
    bm_camera_x: int = 0     # BmSt.camera.x (+0x0C, s16)
    bm_camera_y: int = 0     # BmSt.camera.y (+0x0E, s16)
    bm_cursor_x: int = 0     # BmSt.playerCursor.x (+0x14, s16) — live display cursor
    bm_cursor_y: int = 0     # BmSt.playerCursor.y (+0x16, s16)
    bm_game_state_bits: int = 0  # BmSt.gameStateBits (+0x04)
    bm_taken_action: int = 0 # BmSt.taken_action (+0x3D)
    # gEventSlots (IWRAM) — 14 x s32, tutorial target coords
    # Set to 0 until verified via memory_probe --find-event-slots
    event_slots_base: int = 0
    # Live map buffers. These point to engine globals, not packed map data.
    # gBmMapSize is a Vec2; gBmMapTerrain is a u8** row-pointer map.
    map_size: int = 0
    map_terrain: int = 0


@dataclass(frozen=True)
class GameInfo:
    """Complete game configuration."""
    game_id: str           # "fe7", "fe8"
    title: str             # "Fire Emblem: The Blazing Blade"
    rom_code: str          # "AE7E", "BE8E"
    addresses: GameAddresses
    lord_names: List[str]
    unit_struct_size: int  # 0x48 for both


# ROM header offset for the 4-byte game code
ROM_GAME_CODE_ADDR = 0x080000AC


GAME_REGISTRY = {
    "BE8E": GameInfo(
        game_id="fe8",
        title="Fire Emblem: The Sacred Stones",
        rom_code="BE8E",
        lord_names=["Eirika", "Ephraim"],
        unit_struct_size=0x48,
        addresses=GameAddresses(
            player_units=0x0202BE4C,  # gUnitArrayBlue[62]
            enemy_units=0x0202CFBC,   # gUnitArrayRed[50]
            npc_units=0x0202DDCC,     # gUnitArrayGreen[20]
            max_player=62,
            max_enemy=50,
            max_npc=20,
            phase=0x0202BCF9,
            chapter=0x0202BCFE,
            turn=0x0202BD00,
            cursor_x=0x0202BD02,
            cursor_y=0x0202BD03,
            # BmSt base=0x0202BCB0 (gBmSt from FE8 decomp)
            bm_lock=0x0202BCB1,
            bm_camera_x=0x0202BCBC,
            bm_camera_y=0x0202BCBE,
            bm_cursor_x=0x0202BCC4,
            bm_cursor_y=0x0202BCC6,
            bm_game_state_bits=0x0202BCB4,
            bm_taken_action=0x0202BCED,
            # gEventSlots — 14 x s32 at 0x030004B8 (from FE8 decomp)
            event_slots_base=0x030004B8,
            # gBmMapSize / gBmMapTerrain from FE8 decomp symbols.
            map_size=0x0202E4D4,
            map_terrain=0x0202E4DC,
        ),
    ),
    "AE7E": GameInfo(
        game_id="fe7",
        title="Fire Emblem: The Blazing Blade",
        rom_code="AE7E",
        lord_names=["Eliwood", "Hector", "Lyn"],
        unit_struct_size=0x48,
        addresses=GameAddresses(
            # Player array CONFIRMED via live probe (Lyn found at slot 1).
            # CB code stride=0x48, HP addr=0x0202BD62
            #   unit[1] base = 0x0202BD50, array base = 0x0202BD08
            player_units=0x0202BD08,
            # Enemy/NPC: COMPUTED from contiguous layout (same engine as FE8).
            # enemy = player + 62*0x48 = 0x0202BD08 + 0x1170 = 0x0202CE78
            # npc   = enemy  + 50*0x48 = 0x0202CE78 + 0x0E10 = 0x0202DC88
            # Enemy array VERIFIED: Batta + Brigand found at 0x0202CE78 in Prologue.
            enemy_units=0x0202CE78,
            npc_units=0x0202DC88,  # Computed, needs live verification
            max_player=62,
            max_enemy=50,
            max_npc=20,
            # Game state: PlaySt struct at 0x0202BBF8.
            # Turn/Cursor/Chapter/Phase all VERIFIED from live hex dumps.
            # Phase uses allegiance encoding (0x00=player, 0x80=enemy, 0x40=NPC)
            # unlike FE8 which uses sequential (0/1/2).
            phase=0x0202BC07,     # PlaySt+0x0F — VERIFIED (0x00→0x80 on enemy turn)
            chapter=0x0202BC06,   # PlaySt+0x0E — VERIFIED (reads 1 for Ch.1)
            turn=0x0202BC08,      # PlaySt+0x10 — VERIFIED (01→05 across turns)
            cursor_x=0x0202BC0A,  # PlaySt+0x12 — VERIFIED (matches unit positions)
            cursor_y=0x0202BC0B,  # PlaySt+0x13 — VERIFIED (matches unit positions)
            # BmSt base=0x0202BBB8 (PlaySt-0x40) — VERIFIED via --find-bmst probe
            # lock=1 during "Let's advance on that bandit!" dialogue ✓
            # playerCursor=(13,7) matches PlaySt cursor ✓
            bm_lock=0x0202BBB9,
            bm_camera_x=0x0202BBC4,
            bm_camera_y=0x0202BBC6,
            bm_cursor_x=0x0202BBCC,
            bm_cursor_y=0x0202BBCE,
            bm_game_state_bits=0x0202BBBC,
            bm_taken_action=0x0202BBF5,
            # gEventSlots — address unknown for FE7, needs discovery
            # FE8 uses 0x030004B8 (14 x s32 in IWRAM)
            event_slots_base=0,
            # FE7 terrain symbols are not public in the partial US decomp.
            # Keep disabled until verified by live probe or a named symbol table.
            map_size=0,
            map_terrain=0,
        ),
    ),
}


def detect_game(socket_client) -> Optional[GameInfo]:
    """
    Read ROM header at 0x080000AC to identify the running game.

    Args:
        socket_client: Connected socket to mGBA Lua script

    Returns:
        GameInfo for the detected game, or None if unrecognized
    """
    try:
        cmd = f"READRANGE {hex(ROM_GAME_CODE_ADDR)} 4\n"
        socket_client.send(cmd.encode())

        # Read 4-byte length header
        length_bytes = socket_client.recv(4)
        if len(length_bytes) != 4:
            logger.warning("Failed to read ROM header length")
            return None

        data_length = struct.unpack(">I", length_bytes)[0]

        # Read payload
        data = b''
        while len(data) < data_length:
            chunk = socket_client.recv(data_length - len(data))
            if not chunk:
                break
            data += chunk

        if len(data) < 4:
            logger.warning("ROM header read too short")
            return None

        rom_code = data.decode('ascii', errors='replace')
        logger.info(f"ROM game code: '{rom_code}'")

        game_info = GAME_REGISTRY.get(rom_code)
        if game_info:
            logger.info(f"Detected: {game_info.title} ({game_info.rom_code})")
        else:
            logger.warning(f"Unrecognized ROM code: '{rom_code}'")

        return game_info

    except Exception as e:
        logger.error(f"ROM detection failed: {e}")
        return None


def get_game_info(game_id: str) -> Optional[GameInfo]:
    """
    Look up game configuration by game id.

    Args:
        game_id: "fe7" or "fe8"

    Returns:
        GameInfo or None if not found
    """
    for info in GAME_REGISTRY.values():
        if info.game_id == game_id:
            return info
    return None
