"""
GBA Fire Emblem Memory Reader

Game-agnostic memory reader for GBA Fire Emblem titles (FE7/FE8).
The unit struct layout is identical across both games (same engine, 0x48 bytes).
Only base addresses and ID tables differ.
"""

import socket
import struct
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from src.data.game_registry import GameInfo, detect_game, get_game_info

logger = logging.getLogger(__name__)

# Terrain types (GBA Fire Emblem)
# Each terrain type has: name, defense bonus, avoid bonus, rescue cost
TERRAIN_TYPES = {
    0x00: {"name": "Plain", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x01: {"name": "Road", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x02: {"name": "Grass", "def": 1, "avo": 10, "cost": 1, "visit": False},
    0x03: {"name": "Forest", "def": 2, "avo": 20, "cost": 2, "visit": False},  # Woods in FE7
    0x04: {"name": "Mountain", "def": 3, "avo": 30, "cost": 3, "visit": False},
    0x05: {"name": "Hill", "def": 3, "avo": 30, "cost": 2, "visit": False},
    0x06: {"name": "Fort", "def": 4, "avo": 30, "cost": 1, "visit": False},
    0x07: {"name": "Water", "def": 0, "avo": 0, "cost": 2, "visit": False},
    0x08: {"name": "Peak", "def": 0, "avo": 0, "cost": 3, "visit": False},
    0x09: {"name": "Bridge", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x0A: {"name": "Gate", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x0B: {"name": "Door", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x0C: {"name": "Throne", "def": 5, "avo": 30, "cost": 1, "visit": False},
    0x0D: {"name": "Pillar", "def": 0, "avo": 0, "cost": 1, "visit": False},
    0x0E: {"name": "Shop", "def": 0, "avo": 0, "cost": 1, "visit": True},
    0x0F: {"name": "Village", "def": 1, "avo": 10, "cost": 1, "visit": True},
    0x10: {"name": "House", "def": 0, "avo": 0, "cost": 1, "visit": True},  # FE7 house
    0x11: {"name": "Armory", "def": 0, "avo": 0, "cost": 1, "visit": True},  # FE7 armory
    0x12: {"name": "SecretShop", "def": 0, "avo": 0, "cost": 1, "visit": True},
    0x13: {"name": "Destroyable", "def": 0, "avo": 0, "cost": 1, "visit": False},  # Breakable wall
}


@dataclass
class GBAUnit:
    """GBA Fire Emblem unit data structure (shared across FE7/FE8)."""
    index: int
    char_id: int
    class_id: int
    level: int
    exp: int
    allegiance: int
    max_hp: int
    current_hp: int
    strength: int
    skill: int
    speed: int
    defense: int
    resistance: int
    luck: int
    x: int
    y: int
    status: int
    status_effect: int
    status_duration: int
    state: int
    is_alive: bool
    has_moved: bool
    is_not_deployed: bool
    has_acted: bool   # state bit 0x02: HAS_ACTED in FE7 / DEAD in FE8 (use with care)
    is_hidden: bool   # state bit 0x01: unit hidden from rendering
    is_rescuing: bool # state bit 0x10: this unit is rescuing another
    is_rescued: bool  # state bit 0x20: this unit is being rescued
    is_player: bool
    is_enemy: bool
    is_npc: bool
    items: List[Tuple[int, int]]  # (item_id, uses_remaining)
    weapon_ranks: List[int]  # 8 weapon types: Sword,Lance,Axe,Bow,Staff,Anima,Light,Dark
    con_bonus: int = 0
    mov_bonus: int = 0
    torch_duration: int = 0
    barrier_duration: int = 0
    ai_flags: int = 0  # offset 0x0A - enemy AI behavior type
    rescue_target: int = 0  # offset 0x1B - unit index being rescued (0 if none)
    ballista_index: int = 0  # offset 0x1C - which ballista unit is on (-1 if none)

    @property
    def hp_percent(self) -> float:
        """Get HP as percentage"""
        return (self.current_hp / self.max_hp) if self.max_hp > 0 else 0.0

    @property
    def position(self) -> Tuple[int, int]:
        """Get position as tuple"""
        return (self.x, self.y)

    def distance_to(self, other: 'GBAUnit') -> int:
        """Manhattan distance to another unit"""
        return abs(self.x - other.x) + abs(self.y - other.y)


@dataclass
class GBAGameState:
    """Complete GBA Fire Emblem game state."""
    phase: str  # "start_screen", "player_phase", "enemy_phase", "npc_phase", "movement", "unknown"
    chapter: int
    turn: int
    cursor_x: int
    cursor_y: int
    player_units: List[GBAUnit]
    enemy_units: List[GBAUnit]
    npc_units: List[GBAUnit]
    # BmSt fields (populated when addresses are configured)
    input_locked: bool = False
    camera_x: int = 0
    camera_y: int = 0
    display_cursor_x: int = -1  # -1 = not available
    display_cursor_y: int = -1
    # Tutorial target from gEventSlots (IWRAM)
    tutorial_target_x: int = -1  # -1 = not available
    tutorial_target_y: int = -1
    # BmSt game state bits and taken_action (raw values for downstream inference)
    game_state_bits: int = 0   # BmSt+0x04 — battle map state flags
    taken_action: int = 0      # BmSt+0x3D — last action type taken
    # Turn/phase change detection
    turn_changed: bool = False  # True if turn incremented since last read
    phase_changed: bool = False # True if phase changed since last read

    @property
    def player_count(self) -> int:
        return len(self.player_units)

    @property
    def enemy_count(self) -> int:
        return len(self.enemy_units)

    @property
    def alive_player_count(self) -> int:
        return sum(1 for u in self.player_units if u.is_alive)

    @property
    def alive_enemy_count(self) -> int:
        return sum(1 for u in self.enemy_units if u.is_alive)

    @property
    def all_units(self) -> List[GBAUnit]:
        return self.player_units + self.enemy_units + self.npc_units

    def get_unit_at(self, x: int, y: int) -> Optional[GBAUnit]:
        """Get unit at specific position"""
        for unit in self.all_units:
            if unit.x == x and unit.y == y and unit.is_alive:
                return unit
        return None

    def get_units_in_range(self, x: int, y: int, distance: int) -> List[GBAUnit]:
        """Get all units within range of a position"""
        units = []
        for unit in self.all_units:
            if unit.is_alive:
                dist = abs(unit.x - x) + abs(unit.y - y)
                if dist <= distance:
                    units.append(unit)
        return units


class GBAMemoryReader:
    """
    Game-agnostic GBA Fire Emblem memory reader.

    Parameterized by GameInfo — the unit struct parsing is identical
    for FE7 and FE8 (same engine, same offsets, same 0x48 size).
    Only base addresses differ.

    Unit struct verified from:
    - FE8: https://github.com/FireEmblemUniverse/fireemblem8u/blob/master/include/bmunit.h
    - FE7: Same engine, same struct layout
    """

    # Unit struct offsets (shared across FE7/FE8 — same engine)
    UNIT_SIZE = 0x48  # 72 bytes per unit
    OFF_CHAR_PTR = 0x00    # Pointer to CharacterData (4 bytes)
    OFF_CLASS_PTR = 0x04   # Pointer to ClassData (4 bytes)
    OFF_LEVEL = 0x08       # s8
    OFF_EXP = 0x09         # u8
    OFF_AI_FLAGS = 0x0A    # u8
    OFF_INDEX = 0x0B       # s8 (faction in bits 6-7)
    OFF_STATE = 0x0C       # u32 (state bitmask)
    OFF_X_POS = 0x10       # s8
    OFF_Y_POS = 0x11       # s8
    OFF_MAX_HP = 0x12      # s8
    OFF_CUR_HP = 0x13      # s8
    OFF_POW = 0x14         # s8 (strength)
    OFF_SKL = 0x15         # s8
    OFF_SPD = 0x16         # s8
    OFF_DEF = 0x17         # s8
    OFF_RES = 0x18         # s8
    OFF_LCK = 0x19         # s8
    OFF_CON_BONUS = 0x1A   # s8
    OFF_RESCUE = 0x1B      # u8
    OFF_BALLISTA = 0x1C    # u8
    OFF_MOV_BONUS = 0x1D   # s8
    OFF_ITEMS = 0x1E       # u16[5] (10 bytes)
    OFF_RANKS = 0x28       # u8[8] (8 bytes)
    OFF_STATUS = 0x30      # u8 (bits 0-3: effect, bits 4-7: duration)
    OFF_TORCH_BARRIER = 0x31  # u8 (bits 0-3: torch, bits 4-7: barrier)

    # Allegiance values (encoded in index field bits 6-7)
    ALLEGIANCE_PLAYER = 0x00   # FACTION_BLUE
    ALLEGIANCE_NPC = 0x40      # FACTION_GREEN (ally)
    ALLEGIANCE_ENEMY = 0x80    # FACTION_RED
    ALLEGIANCE_PURPLE = 0xC0   # FACTION_PURPLE

    # State flags (from bmunit.h US_ constants)
    STATE_HIDDEN = 0x01
    STATE_DEAD = 0x02
    STATE_NOT_DEPLOYED = 0x04
    STATE_RESCUING = 0x10
    STATE_RESCUED = 0x20

    def __init__(self, socket_client, game_info: GameInfo):
        """
        Initialize memory reader.

        Args:
            socket_client: Connected socket to mGBA Lua script
            game_info: Game configuration with addresses and metadata
        """
        self.socket = socket_client
        self.game = game_info
        self.addrs = game_info.addresses
        self._id_cache = {}  # {rom_pointer: id_byte} - ROM data is fixed
        # Turn/phase tracking for change detection
        self._last_turn = -1
        self._last_phase = None
        self._phase_consecutive_count = 0  # For hysteresis - require 2 consecutive reads
        self._turn_changed = False
        self._phase_changed = False
        logger.info(f"{game_info.title} memory reader initialized")

    def read_memory(self, address: int, length: int, retries: int = 2) -> bytes:
        """
        Read raw memory from mGBA with retry logic for transient socket errors.

        Args:
            address: Memory address (hex or decimal)
            length: Number of bytes to read
            retries: Number of retry attempts on transient errors

        Returns:
            Raw bytes from memory
        """
        for attempt in range(retries + 1):
            try:
                cmd = f"READRANGE {hex(address)} {length}\n"
                self.socket.send(cmd.encode())

                # Read 4-byte length header
                length_bytes = self.socket.recv(4)
                if len(length_bytes) != 4:
                    raise ValueError("Failed to read length header")

                data_length = struct.unpack(">I", length_bytes)[0]

                # Read actual data
                data = b''
                while len(data) < data_length:
                    chunk = self.socket.recv(data_length - len(data))
                    if not chunk:
                        raise ValueError("Connection closed while reading data")
                    data += chunk

                return data

            except (ConnectionError, TimeoutError, socket.timeout) as e:
                if attempt < retries:
                    logger.warning(f"Memory read retry {attempt+1} at 0x{address:X}: {e}")
                    time.sleep(0.05)
                    continue
                logger.error(f"Memory read failed at 0x{address:X} after {retries+1} attempts: {e}")
                return b''
            except Exception as e:
                logger.error(f"Memory read failed at 0x{address:X}: {e}")
                return b''

    def _deref_id(self, pointer: int) -> int:
        """
        Dereference a CharacterData or ClassData ROM pointer to get the ID.

        The Unit struct stores 4-byte pointers to CharacterData/ClassData in ROM.
        The actual ID (number field) is at offset 0x04 in those ROM structs.
        Results are cached since ROM data never changes.
        """
        if pointer < 0x08000000 or pointer > 0x09FFFFFF:
            return 0  # Not a valid ROM pointer
        if pointer in self._id_cache:
            return self._id_cache[pointer]
        id_data = self.read_memory(pointer + 0x04, 1)
        id_byte = id_data[0] if id_data else 0
        self._id_cache[pointer] = id_byte
        return id_byte

    def _parse_unit(self, data: bytes, index: int) -> Optional[GBAUnit]:
        """
        Parse a single unit from an already-fetched byte buffer.

        This avoids per-unit socket calls by parsing from a bulk-read buffer.
        ROM pointer dereferences still require socket calls but are cached.
        """
        if len(data) < self.UNIT_SIZE:
            return None

        # Character/class are 4-byte pointers to ROM structs
        char_ptr = struct.unpack("<I", data[self.OFF_CHAR_PTR:self.OFF_CHAR_PTR+4])[0]
        if char_ptr == 0:  # Empty slot (null pointer)
            return None

        class_ptr = struct.unpack("<I", data[self.OFF_CLASS_PTR:self.OFF_CLASS_PTR+4])[0]

        # Dereference ROM pointers to get actual character/class IDs (cached)
        char_id = self._deref_id(char_ptr)
        class_id = self._deref_id(class_ptr)

        level = data[self.OFF_LEVEL]
        exp = data[self.OFF_EXP]

        # Index field contains allegiance in bits 6-7
        index_byte = data[self.OFF_INDEX]
        allegiance = index_byte & 0xC0

        # State is a u32 bitmask
        state = struct.unpack("<I", data[self.OFF_STATE:self.OFF_STATE+4])[0]

        # Position (s8 values)
        x = data[self.OFF_X_POS]
        y = data[self.OFF_Y_POS]

        # Stats (all s8)
        max_hp = data[self.OFF_MAX_HP]
        current_hp = data[self.OFF_CUR_HP]
        strength = data[self.OFF_POW]
        skill = data[self.OFF_SKL]
        speed = data[self.OFF_SPD]
        defense = data[self.OFF_DEF]
        resistance = data[self.OFF_RES]
        luck = data[self.OFF_LCK]

        # Status byte: bits 0-3 = effect, bits 4-7 = duration
        status_byte = data[self.OFF_STATUS]
        status_effect = status_byte & 0x0F
        status_duration = (status_byte >> 4) & 0x0F

        # Torch/barrier durations
        torch_barrier = data[self.OFF_TORCH_BARRIER]
        torch_duration = torch_barrier & 0x0F
        barrier_duration = (torch_barrier >> 4) & 0x0F

        # Items: 5 slots, each u16 at offset 0x1E
        items = []
        for j in range(5):
            item_offset = self.OFF_ITEMS + j * 2
            item_word = struct.unpack("<H", data[item_offset:item_offset+2])[0]
            if item_word != 0:
                item_id = item_word & 0xFF
                item_uses = (item_word >> 8) & 0xFF
                items.append((item_id, item_uses))

        # Weapon ranks: 8 bytes at offset 0x28
        weapon_ranks = list(data[self.OFF_RANKS:self.OFF_RANKS+8])

        # Bonus stats
        con_bonus = data[self.OFF_CON_BONUS]
        mov_bonus = data[self.OFF_MOV_BONUS]

        # Additional fields
        ai_flags = data[self.OFF_AI_FLAGS]
        rescue_target = data[self.OFF_RESCUE]
        ballista_index = data[self.OFF_BALLISTA]

        # Compute flags using state bitmask
        # Note on state bits 0x01 and 0x02:
        #   FE7: 0x01=HIDDEN (rendering), 0x02=HAS_ACTED (grayed out after turn)
        #   FE8: 0x01=HIDDEN (rendering), 0x02=DEAD
        # Both are transient flags, NOT reliable for death detection.
        # Only HP and NOT_DEPLOYED (0x04) are reliable across both games.
        is_not_deployed = (state & self.STATE_NOT_DEPLOYED) != 0
        is_alive = current_hp > 0 and not is_not_deployed
        has_moved = (state & 0x40) != 0
        # Note: 0x02 = HAS_ACTED in FE7 but DEAD in FE8 - only use for FE7
        if self.game.game_id == "fe7":
            has_acted = (state & 0x02) != 0
        else:
            has_acted = False  # In FE8, 0x02 means DEAD, not has acted
        is_hidden = (state & self.STATE_HIDDEN) != 0
        is_rescuing = (state & self.STATE_RESCUING) != 0
        is_rescued = (state & self.STATE_RESCUED) != 0

        is_player = (allegiance == self.ALLEGIANCE_PLAYER)
        is_enemy = (allegiance == self.ALLEGIANCE_ENEMY)
        is_npc = (allegiance == self.ALLEGIANCE_NPC)

        return GBAUnit(
            index=index,
            char_id=char_id,
            class_id=class_id,
            level=level,
            exp=exp,
            allegiance=allegiance,
            max_hp=max_hp,
            current_hp=current_hp,
            strength=strength,
            skill=skill,
            speed=speed,
            defense=defense,
            resistance=resistance,
            luck=luck,
            x=x,
            y=y,
            status=status_byte,
            status_effect=status_effect,
            status_duration=status_duration,
            state=state,
            is_alive=is_alive,
            has_moved=has_moved,
            is_not_deployed=is_not_deployed,
            has_acted=has_acted,
            is_hidden=is_hidden,
            is_rescuing=is_rescuing,
            is_rescued=is_rescued,
            is_player=is_player,
            is_enemy=is_enemy,
            is_npc=is_npc,
            items=items,
            weapon_ranks=weapon_ranks,
            con_bonus=con_bonus,
            mov_bonus=mov_bonus,
            torch_duration=torch_duration,
            barrier_duration=barrier_duration,
            ai_flags=ai_flags,
            rescue_target=rescue_target,
            ballista_index=ballista_index,
        )

    def read_unit(self, base_addr: int, index: int) -> Optional[GBAUnit]:
        """Read a single unit from memory (legacy per-unit method)."""
        offset = base_addr + (index * self.UNIT_SIZE)
        data = self.read_memory(offset, self.UNIT_SIZE)
        return self._parse_unit(data, index)

    def _read_unit_array(self, base_addr: int, max_units: int) -> List[GBAUnit]:
        """Batch-read an entire unit array with a single socket call."""
        if base_addr == 0:
            return []  # Address not known (e.g. unverified FE7 addresses)

        total_bytes = max_units * self.UNIT_SIZE
        bulk_data = self.read_memory(base_addr, total_bytes)
        if len(bulk_data) < self.UNIT_SIZE:
            logger.warning(f"Incomplete bulk read at 0x{base_addr:X}: got {len(bulk_data)}/{total_bytes} bytes")
            return []

        units = []
        for i in range(max_units):
            start = i * self.UNIT_SIZE
            end = start + self.UNIT_SIZE
            if end > len(bulk_data):
                break
            unit_data = bulk_data[start:end]
            unit = self._parse_unit(unit_data, i)
            if unit:
                units.append(unit)
        return units

    def read_all_units(self) -> Tuple[List[GBAUnit], List[GBAUnit], List[GBAUnit]]:
        """
        Read all units from memory using batch reads.

        Uses 3 bulk socket calls (one per array) instead of ~400 individual calls.

        Returns:
            Tuple of (player_units, enemy_units, npc_units)
        """
        player_units = []
        enemy_units = []
        npc_units = []

        # Batch-read player unit array (gUnitArrayBlue)
        for unit in self._read_unit_array(self.addrs.player_units, self.addrs.max_player):
            if unit.is_player:
                player_units.append(unit)
            elif unit.is_npc:
                npc_units.append(unit)
            elif unit.is_enemy:
                enemy_units.append(unit)

        # Batch-read enemy unit array (gUnitArrayRed)
        for unit in self._read_unit_array(self.addrs.enemy_units, self.addrs.max_enemy):
            if unit.is_enemy:
                enemy_units.append(unit)
            elif unit.is_player:
                player_units.append(unit)
            elif unit.is_npc:
                npc_units.append(unit)

        # Batch-read NPC unit array (gUnitArrayGreen)
        for unit in self._read_unit_array(self.addrs.npc_units, self.addrs.max_npc):
            if unit.is_npc:
                npc_units.append(unit)
            elif unit.is_player:
                player_units.append(unit)
            elif unit.is_enemy:
                enemy_units.append(unit)

        return player_units, enemy_units, npc_units

    def read_game_state(self) -> GBAGameState:
        """Read complete game state from memory."""
        # Validate game is actually loaded by checking for player units
        player_units, enemy_units, npc_units = self.read_all_units()
        
        # If we expect FE7/FE8 units but find none, game may not be loaded
        if self.game.game_id in ("fe7", "fe8") and not player_units and not enemy_units:
            # Early game state (title screen, or before units spawn)
            # Continue reading but log warning
            logger.debug(f"No units found for {self.game.game_id}, game may be at title screen or early chapter")
        
        raw_phase = 0xFF
        chapter = turn = cursor_x = cursor_y = 0

        if self.addrs.phase != 0:
            chapter_data = self.read_memory(self.addrs.chapter, 1)
            if len(chapter_data) >= 1:
                chapter = chapter_data[0]

            state_data = self.read_memory(self.addrs.phase, 5)
            if len(state_data) >= 5:
                raw_phase = state_data[0]
                turn = state_data[1]
                cursor_x = state_data[3]
                cursor_y = state_data[4]

        # Units already read above

        # Phase detection with improved FE7/FE8 handling
        # FE8 uses sequential encoding: 0=player, 1=enemy, 2=NPC
        # FE7 uses allegiance encoding: 0x00=player, 0x80=enemy, 0x40=NPC
        phase = "unknown"
        detected_via = "unknown"
        
        # Start screen detection: no turn, no chapter, no phase data, no units
        if raw_phase == 0xFF and chapter == 0 and turn == 0 and not player_units:
            phase = "start_screen"
            detected_via = "unknown_phase_and_no_data"
        # Use phase byte as primary indicator
        elif raw_phase == 0x00 or raw_phase == 0:
            phase = "player_phase"
            detected_via = "phase_byte_0x00"
        elif raw_phase == 0x01 or raw_phase == 1:
            phase = "enemy_phase"
            detected_via = "phase_byte_0x01_FE8"
        elif raw_phase == 0x02 or raw_phase == 2:
            phase = "npc_phase"
            detected_via = "phase_byte_0x02_FE8"
        elif raw_phase == 0x80:
            phase = "enemy_phase"
            detected_via = "phase_byte_0x80_FE7"
        elif raw_phase == 0x40:
            phase = "npc_phase"
            detected_via = "phase_byte_0x40_FE7"
        # Fallback: infer from unit presence and turn
        elif player_units and not enemy_units:
            phase = "player_phase"
            detected_via = "inference_only_players"
        elif enemy_units and raw_phase % 2 == 1:  # enemy_phase usually odd
            phase = "enemy_phase"
            detected_via = "inference_phase_odd"
        else:
            phase = "unknown"
            detected_via = "no_match"
        
        logger.debug(f"Phase detection: raw_phase=0x{raw_phase:02X}, phase={phase}, via={detected_via}, turn={turn}")

        # Phase hysteresis: require 2 consecutive detections before switching
        # This prevents flickering between phases due to memory timing issues
        if phase != self._last_phase:
            self._phase_consecutive_count += 1
            if self._phase_consecutive_count >= 2:
                self._phase_changed = True
                self._last_phase = phase
                self._phase_consecutive_count = 0
                logger.info(f"Phase changed to: {phase}")
            else:
                self._phase_changed = False
                phase = self._last_phase  # Keep previous phase until hysteresis threshold
        else:
            self._phase_consecutive_count = 0
            self._phase_changed = False

        # Detect turn changes (after phase is defined)
        self._turn_changed = (turn != self._last_turn) if self._last_turn >= 0 else False
        self._last_turn = turn

        # Read BmSt fields if addresses are configured
        bm = self.read_bm_state()

        # Read tutorial target from event slots (IWRAM) - only if tutorial mode enabled
        from src.core import config
        tut_x = -1
        tut_y = -1
        
        if config.TUTORIAL_MODE:
            ev = self.read_event_slots(cursor_x, cursor_y)
            tut_x = ev["tutorial_target"][0] if "tutorial_target" in ev else -1
            tut_y = ev["tutorial_target"][1] if "tutorial_target" in ev else -1

            # If no tutorial target from memory, try screenshot detection
            if tut_x == -1 and self.game.game_id == "fe7":
                screen_target = self.detect_tutorial_target_from_screenshot()
                if screen_target:
                    tut_x, tut_y = screen_target

        # Final fallback: hardcoded chapter-based tutorial targets (only if tutorial mode)
        if tut_x == -1 and config.TUTORIAL_MODE:
            chapter_target = self._get_chapter_tutorial_sequence(chapter)
            if chapter_target and len(chapter_target) > 0:
                first_step = chapter_target[0]
                if first_step.get("coords") and len(first_step["coords"]) > 0:
                    tut_x, tut_y = first_step["coords"][0]

        return GBAGameState(
            phase=phase,
            chapter=chapter,
            turn=turn,
            cursor_x=cursor_x,
            cursor_y=cursor_y,
            player_units=player_units,
            enemy_units=enemy_units,
            npc_units=npc_units,
            input_locked=bm.get("input_locked", False),
            camera_x=bm.get("camera_x", 0),
            camera_y=bm.get("camera_y", 0),
            display_cursor_x=bm.get("display_cursor_x", -1),
            display_cursor_y=bm.get("display_cursor_y", -1),
            tutorial_target_x=tut_x,
            tutorial_target_y=tut_y,
            game_state_bits=bm.get("game_state_bits", 0),
            taken_action=bm.get("taken_action", 0),
            turn_changed=self._turn_changed,
            phase_changed=self._phase_changed,
        )

    def _get_chapter_tutorial_sequence(self, chapter: int) -> Optional[List[dict]]:
        """
        Get hardcoded tutorial sequence from chapter data as final fallback.

        This provides tutorial target coordinates for chapters where the
        event slot memory address is unknown or detection fails.

        Args:
            chapter: Chapter number from game state

        Returns:
            List of tutorial steps with coords, or None if not available
        """
        if self.game.game_id == "fe7":
            from src.data import fe7_chapters
            chapter_data = fe7_chapters.get_chapter_objective(chapter)
            if chapter_data and chapter_data.get("tutorial_sequence"):
                return chapter_data["tutorial_sequence"]
        elif self.game.game_id == "fe8":
            from src.data import fe8_chapters
            chapter_data = fe8_chapters.get_chapter_objective(chapter)
            if chapter_data and chapter_data.get("tutorial_sequence"):
                return chapter_data["tutorial_sequence"]
        return None

    def read_event_slots(self, cursor_x: int = -1, cursor_y: int = -1) -> dict:
        """
        Read gEventSlots from IWRAM and scan for tutorial target coordinates.

        The event engine stores tutorial targets as coordinate pairs in the
        14-slot gEventSlots array. We scan all adjacent slot pairs for valid
        map coordinates that differ from the current cursor position.

        Args:
            cursor_x: Current cursor X (to filter out current position)
            cursor_y: Current cursor Y (to filter out current position)

        Returns:
            Dict with 'tutorial_target': (x, y) if found, else empty dict.
        """
        if self.addrs.event_slots_base == 0:
            return {}  # Address not discovered yet

        SLOT_COUNT = 14
        ARRAY_SIZE = SLOT_COUNT * 4  # 14 x s32 = 56 bytes

        data = self.read_memory(self.addrs.event_slots_base, ARRAY_SIZE)
        if len(data) < ARRAY_SIZE:
            return {}

        slots = [struct.unpack_from("<i", data, i * 4)[0] for i in range(SLOT_COUNT)]

        # Scan adjacent pairs for valid map coordinates
        for i in range(SLOT_COUNT - 1):
            x, y = slots[i], slots[i + 1]
            # Valid map coords: 0-63 range, at least one non-zero
            if not (0 <= x <= 63 and 0 <= y <= 63):
                continue
            if x == 0 and y == 0:
                continue
            # Must differ from cursor (it's a destination, not current position)
            if x == cursor_x and y == cursor_y:
                continue
            logger.debug(f"Event slot tutorial target: ({x}, {y}) from slots[{i}:{i+1}]")
            return {"tutorial_target": (x, y)}

        return {}

    def detect_tutorial_target_from_screenshot(self) -> Optional[Tuple[int, int]]:
        """
        Detect tutorial target by analyzing screenshots.

        Uses multiple detection methods:
        1. Color-based: looks for typical tutorial colors (green, yellow, orange)
        2. Flash-based: looks for tiles that blink between frames

        Returns:
            (map_x, map_y) if detected, else None
        """
        try:
            from src.utils.screenshot_analyzer import detect_tutorial_target
            from src.utils.image_utils import capture
            import tempfile
            import os

            # Capture 6 screenshots for multi-frame consistency detection
            # Tutorial target appears in same position across ALL frames
            screenshot_paths = []
            temp_dir = tempfile.mkdtemp()

            for i in range(6):
                filename = os.path.join(temp_dir, f"tut_target_{i}.png")
                capture(self.socket, filename)
                screenshot_paths.append(filename)
                time.sleep(0.08)  # Slightly longer delay for better temporal sampling

            # Detect tutorial target
            screen_tile, detection_info = detect_tutorial_target(screenshot_paths)

            # Clean up temp files
            for path in screenshot_paths:
                try:
                    os.remove(path)
                except Exception:
                    pass
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass

            if not screen_tile:
                logger.debug(f"No tutorial target detected: {detection_info}")
                return None

            # Convert screen tile to map coordinates
            # Get camera position for accurate conversion
            bm = self.read_bm_state()
            camera_x = bm.get("camera_x", 0)
            camera_y = bm.get("camera_y", 0)

            # Screen tile to map: map_x = screen_x + camera_x / 16
            map_x = screen_tile[0] + camera_x // 16
            map_y = screen_tile[1] + camera_y // 16

            logger.info(f"Tutorial target detected: screen {screen_tile} -> map ({map_x}, {map_y}), "
                       f"method: {detection_info.get('detection_type', 'unknown')}")

            return (map_x, map_y)

        except Exception as e:
            logger.warning(f"Tutorial target screenshot detection failed: {e}")
            return None

    def read_bm_state(self) -> dict:
        """Read Battle Map State (BmSt) fields if addresses are configured."""
        result = {}
        if self.addrs.bm_lock == 0:
            return result  # BmSt addresses not yet verified

        # Read 0x40 bytes from BmSt base (lock_addr - 1)
        bm_base = self.addrs.bm_lock - 1
        data = self.read_memory(bm_base, 0x40)
        if len(data) < 0x40:
            return result

        result["input_locked"] = data[0x01] > 0
        result["lock_count"] = data[0x01]
        result["camera_x"] = struct.unpack_from("<h", data, 0x0C)[0]  # s16
        result["camera_y"] = struct.unpack_from("<h", data, 0x0E)[0]
        result["display_cursor_x"] = struct.unpack_from("<h", data, 0x14)[0]
        result["display_cursor_y"] = struct.unpack_from("<h", data, 0x16)[0]
        result["game_state_bits"] = data[0x04]
        result["taken_action"] = data[0x3D]
        return result

    def read_terrain(self, x: int, y: int) -> Optional[dict]:
        """
        Read terrain at specific map coordinates.

        Args:
            x: X coordinate (0-indexed)
            y: Y coordinate (0-indexed)

        Returns:
            dict with keys: name, def, avo, cost, or None if unavailable
        """
        if self.addrs.terrain_base == 0:
            return None

        # Read map header to get dimensions and data offset
        header = self.read_memory(self.addrs.terrain_base, 8)
        if len(header) < 8:
            return None

        # Format: u16 width, u16 height, u32 data_offset
        width = struct.unpack_from("<H", header, 0)[0]
        height = struct.unpack_from("<H", header, 2)[0]
        data_offset = struct.unpack_from("<I", header, 4)[0]

        if x < 0 or x >= width or y < 0 or y >= height:
            return None

        # Read terrain data (1 byte per tile)
        terrain_addr = self.addrs.terrain_base + data_offset + (y * width + x)
        terrain_data = self.read_memory(terrain_addr, 1)
        if len(terrain_data) < 1:
            return None

        terrain_id = terrain_data[0]
        terrain_info = TERRAIN_TYPES.get(terrain_id, {"name": f"Unknown({terrain_id})", "def": 0, "avo": 0, "cost": 99, "visit": False})

        return {
            "x": x,
            "y": y,
            "id": terrain_id,
            "name": terrain_info["name"],
            "def": terrain_info["def"],
            "avo": terrain_info["avo"],
            "cost": terrain_info["cost"],
            "visit": terrain_info.get("visit", False),
        }

    def read_map_terrain_grid(self, width: int = 16, height: int = 10) -> Optional[List[List[dict]]]:
        """
        Read terrain for a rectangular region of the map.

        Args:
            width: Number of columns to read
            height: Number of rows to read

        Returns:
            2D list of terrain dicts, or None if unavailable
        """
        if self.addrs.terrain_base == 0:
            return None

        header = self.read_memory(self.addrs.terrain_base, 8)
        if len(header) < 8:
            return None

        map_width = struct.unpack_from("<H", header, 0)[0]
        map_height = struct.unpack_from("<H", header, 2)[0]
        data_offset = struct.unpack_from("<I", header, 4)[0]

        terrain_grid = []
        for y in range(min(height, map_height)):
            row = []
            for x in range(min(width, map_width)):
                terrain_addr = self.addrs.terrain_base + data_offset + (y * map_width + x)
                terrain_data = self.read_memory(terrain_addr, 1)
                if len(terrain_data) >= 1:
                    terrain_id = terrain_data[0]
                    terrain_info = TERRAIN_TYPES.get(terrain_id, {"name": f"Unknown({terrain_id})", "def": 0, "avo": 0, "cost": 99, "visit": False})
                    row.append({
                        "x": x,
                        "y": y,
                        "id": terrain_id,
                        "name": terrain_info["name"],
                        "def": terrain_info["def"],
                        "avo": terrain_info["avo"],
                        "cost": terrain_info["cost"],
                        "visit": terrain_info.get("visit", False),
                    })
                else:
                    row.append(None)
            terrain_grid.append(row)

        return terrain_grid

    def get_ui_state(self) -> str:
        """
        Query the Lua server for current UI state via the STATE command.

        Returns a string like "player_phase", "enemy_phase", "npc_phase",
        "not_in_game", "battle", "dialogue", "menu:X", or "unknown".
        """
        try:
            self.socket.send(b"STATE\n")
            data = b''
            while b"\n" not in data:
                chunk = self.socket.recv(256)
                if not chunk:
                    break
                data += chunk
            return data.decode('utf-8').strip().lower()
        except Exception as e:
            logger.warning(f"UI state query failed: {e}")
            return "unknown"

    def get_detailed_ui_state(self) -> dict:
        """
        Parse the UI state to extract detailed information.

        Returns:
            dict with keys:
                - ui_type: "phase", "menu", "battle", "dialogue", "unknown"
                - phase: phase name if in phase (e.g., "player_phase")
                - menu_selection: int if in menu (-1 if not in menu)
                - menu_type: str if in menu (e.g., "unit", "item", "trade")
        """
        raw_state = self.get_ui_state()

        result = {
            "ui_type": "unknown",
            "phase": None,
            "menu_selection": -1,
            "menu_type": None,
        }

        if raw_state.startswith("menu:"):
            result["ui_type"] = "menu"
            parts = raw_state.split(":")
            if len(parts) >= 2:
                result["menu_type"] = parts[1]
            if len(parts) >= 3:
                try:
                    result["menu_selection"] = int(parts[2])
                except (ValueError, IndexError):
                    result["menu_selection"] = -1
        elif raw_state == "battle":
            result["ui_type"] = "battle"
        elif raw_state == "dialogue":
            result["ui_type"] = "dialogue"
        elif raw_state in ("player_phase", "enemy_phase", "npc_phase", "not_in_game"):
            result["ui_type"] = "phase"
            result["phase"] = raw_state
        elif raw_state.startswith("other:"):
            result["ui_type"] = "phase"
            result["phase"] = raw_state

        return result

    def get_cursor_unit(self, game_state: 'GBAGameState') -> Optional[GBAUnit]:
        """
        Check if the cursor is positioned on a living player unit.

        Checks both PlaySt cursor and BmSt display_cursor (the latter is
        accurate during tutorials and unit movement when PlaySt freezes).

        Returns the GBAUnit at the cursor position, or None.
        """
        # Try PlaySt cursor first
        for unit in game_state.player_units:
            if unit.is_alive and unit.x == game_state.cursor_x and unit.y == game_state.cursor_y:
                return unit
        # Fall back to BmSt display_cursor (accurate during movement/tutorials)
        if game_state.display_cursor_x >= 0:
            dcx, dcy = game_state.display_cursor_x, game_state.display_cursor_y
            if (dcx, dcy) != (game_state.cursor_x, game_state.cursor_y):
                for unit in game_state.player_units:
                    if unit.is_alive and unit.x == dcx and unit.y == dcy:
                        return unit
        return None

    def get_unit_status(self) -> Dict[str, str]:
        """
        Get status of all player units.
        
        Returns:
            Dict mapping unit name to status: "available", "already_acted", or "rescued"
        """
        from src.data.character_lookup import get_character_name
        
        status = {}
        for unit in self.player_units:
            if not unit.is_alive or unit.current_hp <= 0:
                continue
            name = get_character_name(unit.char_id)
            if unit.has_moved:
                status[name] = "already_acted"
            elif unit.is_rescued:
                status[name] = "rescued"
            else:
                status[name] = "available"
        return status

    def is_unit_available(self, unit_name: str) -> bool:
        """Check if a specific unit can still act."""
        status = self.get_unit_status()
        return status.get(unit_name) == "available"

    def get_unit_at_position(self, x: int, y: int, unit_type: str = "player") -> Optional['GBAUnit']:
        """Get unit at specific map position."""
        if unit_type == "player":
            units = self.player_units
        elif unit_type == "enemy":
            units = self.enemy_units
        elif unit_type == "npc":
            units = self.npc_units
        else:
            return None
            
        for unit in units:
            if unit.is_alive and unit.x == x and unit.y == y:
                return unit
        return None

    def get_unit_by_name(self, unit_name: str) -> Optional['GBAUnit']:
        """Get unit object by name."""
        from src.data.character_lookup import get_character_name
        
        name_lower = unit_name.lower()
        for unit in self.player_units:
            if unit.is_alive:
                name = get_character_name(unit.char_id)
                if name.lower() == name_lower:
                    return unit
        return None

    def get_state_dict(self) -> Dict:
        """Get state as dictionary for AI agent."""
        state = self.read_game_state()

        return {
            'phase': state.phase,
            'chapter': state.chapter,
            'turn': state.turn,
            'cursor': (state.cursor_x, state.cursor_y),
            'player_count': state.player_count,
            'enemy_count': state.enemy_count,
            'alive_players': state.alive_player_count,
            'alive_enemies': state.alive_enemy_count,
            'player_hp_total': sum(u.current_hp for u in state.player_units if u.is_alive),
            'player_hp_max': sum(u.max_hp for u in state.player_units if u.is_alive),
            'enemy_hp_total': sum(u.current_hp for u in state.enemy_units if u.is_alive),
            'units_moved': sum(1 for u in state.player_units if u.has_moved and u.is_alive),
        }

    def get_reward_signals(self, prev_state: Optional[GBAGameState],
                          curr_state: GBAGameState) -> Dict[str, float]:
        """Calculate reward signals from state changes."""
        rewards = {}

        if prev_state is None:
            return rewards

        # Combat rewards
        player_diff = prev_state.alive_player_count - curr_state.alive_player_count
        if player_diff > 0:
            rewards['player_died'] = -100.0 * player_diff

        enemy_diff = prev_state.alive_enemy_count - curr_state.alive_enemy_count
        if enemy_diff > 0:
            rewards['enemy_killed'] = 200.0 * enemy_diff

        # Progress rewards
        if curr_state.chapter > prev_state.chapter:
            rewards['chapter_complete'] = 1000.0

        if curr_state.turn > prev_state.turn:
            rewards['turn_advance'] = 5.0

        # Movement rewards
        moved_diff = curr_state.alive_player_count - sum(1 for u in curr_state.player_units if u.has_moved and u.is_alive)
        if moved_diff > 0:
            rewards['units_moved'] = 10.0 * moved_diff

        # Phase rewards
        if prev_state.phase != curr_state.phase:
            if curr_state.phase in ("movement", "player_phase") and prev_state.phase == "start_screen":
                rewards['game_started'] = 50.0
            elif curr_state.phase == "battle":
                rewards['combat_initiated'] = 20.0

        return rewards


# Global instance (created when needed)
_memory_reader = None


def get_memory_reader(socket_client=None) -> Optional[GBAMemoryReader]:
    """
    Get or create global memory reader.

    Uses FE_GAME/ROM_FILE when configured, otherwise reads the ROM header
    through the mGBA Lua socket to select the correct memory addresses.
    """
    global _memory_reader
    if _memory_reader is None and socket_client:
        # Use FE_GAME env var or infer from ROM_FILE
        from src.core import config
        game_id = getattr(config, 'FE_GAME', '')
        game_info = get_game_info(game_id) if game_id else None
        if not game_info:
            logger.info("Detecting game from ROM header")
            game_info = detect_game(socket_client)

        if not game_info:
            raise RuntimeError("Unable to identify running Fire Emblem game. Set FE_GAME=fe7 or FE_GAME=fe8.")

        logger.info(f"Using configured game: {game_info.game_id}")
        _memory_reader = GBAMemoryReader(socket_client, game_info)
    return _memory_reader


def reset_memory_reader():
    """Reset the global memory reader (for testing or reconnection)."""
    global _memory_reader
    _memory_reader = None
