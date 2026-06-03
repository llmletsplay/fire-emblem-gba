#!/usr/bin/env python3
"""
GBA Fire Emblem Memory Probe - Diagnostic tool for verifying memory addresses

Connects to mGBA's Lua socket server and reads/displays all known
game state addresses. Supports FE7 and FE8 via ROM auto-detection.

Usage:
    python tools/memory_probe.py                    # One-shot dump (auto-detect game)
    python tools/memory_probe.py --watch            # Refresh every 2s
    python tools/memory_probe.py --raw              # Include raw hex dumps
    python tools/memory_probe.py --port 8888        # Custom port
    python tools/memory_probe.py --diag             # Diagnostic hex dumps
"""

import argparse
import socket
import struct
import sys
import time
import os

# Add project root to path so we can import data modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.game_registry import GAME_REGISTRY, ROM_GAME_CODE_ADDR, GameInfo

# Allegiance constants (shared across FE7/FE8 — same engine)
ALLEGIANCE_PLAYER = 0x00   # FACTION_BLUE
ALLEGIANCE_NPC = 0x40      # FACTION_GREEN (ally)
ALLEGIANCE_ENEMY = 0x80    # FACTION_RED
ALLEGIANCE_PURPLE = 0xC0   # FACTION_PURPLE

ALLEGIANCE_NAMES = {
    ALLEGIANCE_PLAYER: "PLAYER",
    ALLEGIANCE_NPC: "NPC/ALLY",
    ALLEGIANCE_ENEMY: "ENEMY",
    ALLEGIANCE_PURPLE: "PURPLE",
}

UNIT_SIZE = 0x48  # 72 bytes per unit — same for both games

WEAPON_TYPES = ["Sword", "Lance", "Axe", "Bow", "Staff", "Anima", "Light", "Dark"]


# ── Socket Communication ─────────────────────────────────────────────────────

class MemoryProbe:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.sock = None
        self._id_cache = {}
        self.game_info = None
        self.lookup = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, self.port))
        print(f"Connected to mGBA at {self.host}:{self.port}")

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def detect_game(self):
        """Read ROM header and set up game-specific data."""
        try:
            code_data = self.read_memory(ROM_GAME_CODE_ADDR, 4)
            rom_code = code_data.decode('ascii', errors='replace')
            self.game_info = GAME_REGISTRY.get(rom_code)

            if self.game_info:
                print(f"  Detected: {self.game_info.title} ({rom_code})")
                # Import correct lookup module
                if self.game_info.game_id == "fe8":
                    from src.data import fe8_lookup
                    self.lookup = fe8_lookup
                elif self.game_info.game_id == "fe7":
                    from src.data import fe7_lookup
                    self.lookup = fe7_lookup
            else:
                print(f"  Unknown ROM code: '{rom_code}' — defaulting to FE8")
                from src.data import fe8_lookup
                self.lookup = fe8_lookup
                self.game_info = GAME_REGISTRY.get("BE8E")
        except Exception as e:
            print(f"  ROM detection failed: {e} — defaulting to FE8")
            from src.data import fe8_lookup
            self.lookup = fe8_lookup
            self.game_info = GAME_REGISTRY.get("BE8E")

    def read_memory(self, address, length, retries=2):
        """Read raw bytes from mGBA memory via READRANGE command with retry logic."""
        for attempt in range(retries + 1):
            try:
                cmd = f"READRANGE {hex(address)} {length}\n"
                self.sock.sendall(cmd.encode())

                # Read 4-byte big-endian length header
                hdr = self._recv_exact(4)
                data_len = struct.unpack(">I", hdr)[0]

                # Read payload
                return self._recv_exact(data_len)
            except (ConnectionError, TimeoutError, socket.timeout) as e:
                if attempt < retries:
                    print(f"  [retry {attempt+1}] Memory read at 0x{address:X}: {e}")
                    time.sleep(0.05)
                    continue
                raise

    def _recv_exact(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Socket closed")
            buf += chunk
        return buf

    def read_u8(self, addr):
        data = self.read_memory(addr, 1)
        return data[0] if data else 0

    def read_u16(self, addr):
        data = self.read_memory(addr, 2)
        return struct.unpack("<H", data)[0] if len(data) >= 2 else 0

    def read_u32(self, addr):
        data = self.read_memory(addr, 4)
        return struct.unpack("<I", data)[0] if len(data) >= 4 else 0

    # ── Pointer dereferencing ─────────────────────────────────────────

    def _deref_id(self, pointer):
        """Dereference a ROM pointer to get ID number (cached)."""
        if pointer < 0x08000000 or pointer > 0x09FFFFFF:
            return 0
        if pointer in self._id_cache:
            return self._id_cache[pointer]
        data = self.read_memory(pointer + 0x04, 1)
        id_byte = data[0] if data else 0
        self._id_cache[pointer] = id_byte
        return id_byte

    # ── Unit reading ─────────────────────────────────────────────────

    def _parse_unit(self, data, index, show_raw=False):
        """Parse a single unit from byte buffer."""
        if len(data) < UNIT_SIZE:
            return None

        char_ptr = struct.unpack("<I", data[0x00:0x04])[0]
        if char_ptr == 0:
            return None

        class_ptr = struct.unpack("<I", data[0x04:0x08])[0]
        char_id = self._deref_id(char_ptr)
        class_id = self._deref_id(class_ptr)

        index_byte = data[0x0B]
        allegiance = index_byte & 0xC0
        state = struct.unpack("<I", data[0x0C:0x10])[0]

        status_byte = data[0x30]
        status_effect = status_byte & 0x0F
        status_duration = (status_byte >> 4) & 0x0F

        torch_barrier = data[0x31]
        torch_dur = torch_barrier & 0x0F
        barrier_dur = (torch_barrier >> 4) & 0x0F

        items = []
        for j in range(5):
            item_word = struct.unpack("<H", data[0x1E + j*2:0x1E + j*2 + 2])[0]
            if item_word != 0:
                item_idx = item_word & 0xFF
                item_uses = (item_word >> 8) & 0xFF
                items.append((item_idx, item_uses))

        weapon_ranks = list(data[0x28:0x30])

        is_not_deployed = bool(state & 0x04)
        # Liveness: only HP and NOT_DEPLOYED are reliable across FE7/FE8.
        # Bit 0x01 (HIDDEN) = rendering flag; bit 0x02 = HAS_ACTED in FE7, DEAD in FE8.
        # Both are transient and NOT reliable for death detection.
        is_alive = data[0x13] > 0 and not is_not_deployed

        # Use lookup module for names
        char_name = self.lookup.get_character_name(char_id) if self.lookup else f"0x{char_id:02X}"
        class_name = self.lookup.get_class_name(class_id) if self.lookup else f"0x{class_id:02X}"

        unit = {
            "slot": index,
            "char_ptr": char_ptr,
            "class_ptr": class_ptr,
            "char_id": char_id,
            "class_id": class_id,
            "char_name": char_name,
            "class_name": class_name,
            "level": data[0x08],
            "exp": data[0x09],
            "allegiance": allegiance,
            "allegiance_name": ALLEGIANCE_NAMES.get(allegiance, f"??? (0x{allegiance:02X})"),
            "state": state,
            "x": data[0x10],
            "y": data[0x11],
            "max_hp": data[0x12],
            "cur_hp": data[0x13],
            "str": data[0x14],
            "skl": data[0x15],
            "spd": data[0x16],
            "def": data[0x17],
            "res": data[0x18],
            "lck": data[0x19],
            "con_bonus": data[0x1A],
            "mov_bonus": data[0x1D],
            "items": items,
            "weapon_ranks": weapon_ranks,
            "status_effect": status_effect,
            "status_duration": status_duration,
            "torch_dur": torch_dur,
            "barrier_dur": barrier_dur,
            "is_alive": is_alive,
            "is_not_deployed": is_not_deployed,
            "has_moved": bool(state & 0x40),
        }

        if show_raw:
            unit["raw_hex"] = data.hex()

        return unit

    def _read_unit_array(self, base_addr, max_units, show_raw=False):
        """Batch-read an entire unit array with a single socket call."""
        if base_addr == 0:
            return []
        total_bytes = max_units * UNIT_SIZE
        bulk_data = self.read_memory(base_addr, total_bytes)
        if len(bulk_data) < UNIT_SIZE:
            return []

        units = []
        for i in range(max_units):
            start = i * UNIT_SIZE
            end = start + UNIT_SIZE
            if end > len(bulk_data):
                break
            unit = self._parse_unit(bulk_data[start:end], i, show_raw)
            if unit:
                units.append(unit)
        return units

    def read_all_units(self, show_raw=False):
        """Read all unit arrays using batch reads."""
        addrs = self.game_info.addresses
        players = self._read_unit_array(addrs.player_units, addrs.max_player, show_raw)
        enemies = self._read_unit_array(addrs.enemy_units, addrs.max_enemy, show_raw)
        npcs = self._read_unit_array(addrs.npc_units, addrs.max_npc, show_raw)
        return players, enemies, npcs


# ── Display ──────────────────────────────────────────────────────────────────

def format_items(items, lookup):
    parts = []
    for item_id, uses in items:
        name = lookup.get_item_name(item_id) if lookup else f"Item 0x{item_id:02X}"
        parts.append(f"{name} ({uses})")
    return ", ".join(parts) if parts else "none"

def format_wranks(ranks):
    parts = []
    for i, r in enumerate(ranks):
        if r > 0:
            parts.append(f"{WEAPON_TYPES[i]}:{r}")
    return ", ".join(parts) if parts else "none"

def format_status(effect, duration, lookup):
    name = lookup.get_status_name(effect) if lookup else f"Status {effect}"
    if effect == 0:
        return "none"
    return f"{name} ({duration} turns)"

def print_unit(u, prefix="", lookup=None):
    alive = "ALIVE" if u["is_alive"] else "DEAD"
    moved = " [MOVED]" if u["has_moved"] else ""
    deployed = " [NOT_DEPLOYED]" if u["is_not_deployed"] else ""
    status = format_status(u["status_effect"], u["status_duration"], lookup)

    # Decode state flags for display
    state = u["state"]
    state_flags = []
    if state & 0x01: state_flags.append("HIDDEN")
    if state & 0x02: state_flags.append("ACTED/DEAD")
    if state & 0x04: state_flags.append("NOT_DEPLOYED")
    if state & 0x08: state_flags.append("TURN_STARTED")
    if state & 0x10: state_flags.append("RESCUING")
    if state & 0x20: state_flags.append("RESCUED")
    if state & 0x40: state_flags.append("HAS_MOVED")
    state_str = f" state=0x{state:08X}"
    if state_flags:
        state_str += f" [{','.join(state_flags)}]"

    print(f"  {prefix}[{u['slot']:2d}] {u['char_name']:<12s} {u['class_name']:<20s} "
          f"Lv{u['level']:2d} HP {u['cur_hp']:2d}/{u['max_hp']:2d} "
          f"({u['x']:2d},{u['y']:2d}) "
          f"S{u['str']:2d} K{u['skl']:2d} P{u['spd']:2d} D{u['def']:2d} R{u['res']:2d} L{u['lck']:2d} "
          f"{alive}{moved}{deployed}{state_str}")

    if u["items"]:
        print(f"          Items: {format_items(u['items'], lookup)}")

    if u["status_effect"] != 0:
        print(f"          Status: {status}")

    if "raw_hex" in u:
        hex_str = u["raw_hex"]
        for row in range(0, len(hex_str), 32):
            offset = row // 2
            print(f"          0x{offset:02X}: {hex_str[row:row+32]}")

    print(f"          CharPtr=0x{u['char_ptr']:08X} → ID 0x{u['char_id']:02X}, "
          f"ClassPtr=0x{u['class_ptr']:08X} → ID 0x{u['class_id']:02X}, "
          f"Allegiance=0x{u['allegiance']:02X} ({u['allegiance_name']})")

def format_hex_dump(data, base_addr, bytes_per_row=16):
    """Format a hex dump with address labels."""
    lines = []
    for i in range(0, len(data), bytes_per_row):
        addr = base_addr + i
        hex_part = " ".join(f"{b:02X}" for b in data[i:i+bytes_per_row])
        ascii_part = "".join(
            chr(b) if 0x20 <= b < 0x7F else "." for b in data[i:i+bytes_per_row]
        )
        lines.append(f"  {addr:08X}: {hex_part:<48s} {ascii_part}")
    return "\n".join(lines)


def print_game_state(probe, show_raw=False, diag=False):
    """Print complete game state."""
    game_info = probe.game_info
    addrs = game_info.addresses
    lookup = probe.lookup

    print("=" * 80)
    print(f"  {game_info.title} MEMORY PROBE - Game State Dump")
    print("=" * 80)

    # ── ROM Header Verification ────────────────────────────────────────
    print()
    print("── ROM Header ─────────────────────────────────────────────")
    try:
        title_data = probe.read_memory(0x080000A0, 12)
        code_data = probe.read_memory(ROM_GAME_CODE_ADDR, 4)
        title = title_data.decode('ascii', errors='replace').rstrip('\x00')
        code = code_data.decode('ascii', errors='replace')
        print(f"  Title: '{title}'  Code: '{code}'")
        print(f"  --> {game_info.title} ({game_info.rom_code})")
    except Exception as e:
        print(f"  ROM header read failed: {e}")

    # ── Game state ────────────────────────────────────────────────────
    phase_raw = 0xFF
    if addrs.phase != 0:
        phase_raw = probe.read_u8(addrs.phase)

    if addrs.chapter != 0:
        state_data = probe.read_memory(addrs.chapter, 6)
        if len(state_data) >= 6:
            chapter = state_data[0]
            turn = state_data[addrs.turn - addrs.chapter]
            cursor_x = state_data[addrs.cursor_x - addrs.chapter]
            cursor_y = state_data[addrs.cursor_y - addrs.chapter]
        else:
            chapter = turn = cursor_x = cursor_y = 0
    else:
        chapter = turn = cursor_x = cursor_y = 0
        print("\n  *** Game state addresses not verified for this ROM ***")

    # FE8 uses 0/1/2; FE7 uses allegiance encoding 0x00/0x80/0x40
    phase_names = {0x00: "player_phase", 1: "enemy_phase", 0x80: "enemy_phase",
                   2: "npc_phase", 0x40: "npc_phase"}
    phase_name = phase_names.get(phase_raw, f"unknown (0x{phase_raw:02X})")

    print()
    print("── Game State ─────────────────────────────────────────────")
    print(f"  Phase:    {phase_raw} ({phase_name})")
    print(f"  Chapter:  {chapter}")
    print(f"  Turn:     {turn}")
    print(f"  Cursor:   ({cursor_x}, {cursor_y})")

    # ── Diagnostic hex dumps ──────────────────────────────────────────
    if diag:
        print()
        print("── DIAGNOSTIC: Raw Memory Dumps ───────────────────────────")

        try:
            if addrs.chapter != 0:
                # Known game state region
                diag_start = addrs.chapter - 30
                print()
                print(f"  Game state region (0x{diag_start:08X}, 64 bytes):")
                playst_data = probe.read_memory(diag_start, 64)
                print(format_hex_dump(playst_data, diag_start))
            else:
                # Dump PlaySt region — scan from ~0x120 before player array
                # FE7: PlaySt base ≈ 0x0202BBF8 (player_units - 0x110)
                # Covers phase (+0x09), chapter (+0x0E), turn (+0x10), cursor (+0x12/13)
                scan_start = addrs.player_units - 0x120
                scan_len = 0x120
                print()
                print(f"  PlaySt region scan (0x{scan_start:08X}, {scan_len} bytes):")
                print(f"  Expected: phase@+0x09, chapter@+0x0E, turn@+0x10, cursor@+0x12/13 from base")
                scan_data = probe.read_memory(scan_start, scan_len)
                print(format_hex_dump(scan_data, scan_start))

            # First player unit slot (raw)
            print()
            print(f"  Player unit slot 0 (0x{addrs.player_units:08X}, {UNIT_SIZE} bytes):")
            unit0_data = probe.read_memory(addrs.player_units, UNIT_SIZE)
            print(format_hex_dump(unit0_data, addrs.player_units))

            # Second player unit slot (slot 1 — where Lyn was found for FE7)
            slot1_addr = addrs.player_units + UNIT_SIZE
            print()
            print(f"  Player unit slot 1 (0x{slot1_addr:08X}, {UNIT_SIZE} bytes):")
            unit1_data = probe.read_memory(slot1_addr, UNIT_SIZE)
            print(format_hex_dump(unit1_data, slot1_addr))

            # Enemy unit slots
            if addrs.enemy_units != 0:
                print()
                print(f"  Enemy unit slots 0-2 (0x{addrs.enemy_units:08X}, 3x{UNIT_SIZE} bytes):")
                enemy_data = probe.read_memory(addrs.enemy_units, UNIT_SIZE * 3)
                print(format_hex_dump(enemy_data, addrs.enemy_units))
        except (ConnectionError, OSError) as e:
            print(f"\n  (diagnostic hex dump interrupted: {e})")

    # ── Units ─────────────────────────────────────────────────────────
    print()
    print("── Reading Units ──────────────────────────────────────────")
    players, enemies, npcs = probe.read_all_units(show_raw)

    # Categorize by actual allegiance
    actual_players = [u for u in players if u["allegiance"] == ALLEGIANCE_PLAYER]
    actual_enemies_in_blue = [u for u in players if u["allegiance"] == ALLEGIANCE_ENEMY]
    actual_npcs_in_blue = [u for u in players if u["allegiance"] == ALLEGIANCE_NPC]

    print()
    print(f"── Player Units (array @ 0x{addrs.player_units:08X}, {len(players)} found) ──")
    if actual_players:
        for u in actual_players:
            print_unit(u, "P ", lookup)
    else:
        print("  (none)")

    if actual_enemies_in_blue:
        print(f"\n  *** WARNING: {len(actual_enemies_in_blue)} units in PLAYER array have ENEMY allegiance! ***")
        for u in actual_enemies_in_blue:
            print_unit(u, "!E", lookup)

    if actual_npcs_in_blue:
        print(f"\n  *** WARNING: {len(actual_npcs_in_blue)} units in PLAYER array have NPC allegiance! ***")
        for u in actual_npcs_in_blue:
            print_unit(u, "!N", lookup)

    enemy_addr = addrs.enemy_units
    print()
    if enemy_addr != 0:
        print(f"── Enemy Units (array @ 0x{enemy_addr:08X}, {len(enemies)} found) ──")
    else:
        print(f"── Enemy Units (address unknown, {len(enemies)} found) ──")
    if enemies:
        for u in enemies:
            print_unit(u, "E ", lookup)
    else:
        print("  (none)")

    npc_addr = addrs.npc_units
    print()
    if npc_addr != 0:
        print(f"── NPC Units (array @ 0x{npc_addr:08X}, {len(npcs)} found) ──")
    else:
        print(f"── NPC Units (address unknown, {len(npcs)} found) ──")
    if npcs:
        for u in npcs:
            print_unit(u, "N ", lookup)
    else:
        print("  (none)")

    # ── Summary ───────────────────────────────────────────────────────
    alive_players = sum(1 for u in actual_players if u["is_alive"])
    alive_enemies = sum(1 for u in enemies if u["is_alive"])
    alive_npcs = sum(1 for u in npcs if u["is_alive"])

    print()
    print("── Summary ────────────────────────────────────────────────")
    print(f"  Players: {alive_players} alive / {len(actual_players)} total")
    print(f"  Enemies: {alive_enemies} alive / {len(enemies)} total")
    print(f"  NPCs:    {alive_npcs} alive / {len(npcs)} total")

    # Flag potential issues
    issues = []
    for u in actual_players:
        if u["cur_hp"] == 0 and u["is_alive"]:
            issues.append(f"  Unit {u['char_name']} has 0 HP but flagged alive")
        if u["char_id"] == 0 and u["char_ptr"] != 0:
            issues.append(f"  Slot {u['slot']}: char_ptr=0x{u['char_ptr']:08X} but deref'd ID=0 (bad pointer?)")

    if issues:
        print()
        print("── Potential Issues ───────────────────────────────────────")
        for issue in issues:
            print(issue)

    print()
    print("=" * 80)


def find_bmst(probe):
    """
    Discover the BmSt (Battle Map State) struct address.

    BmSt is 0x40 bytes and sits immediately before PlaySt in EWRAM.
    Search strategy (multi-signal):
    1. PRIMARY: Find BmSt.playerCursor (+0x14) matching PlaySt cursor
       - Two consecutive s16 values matching (cursor_x, cursor_y)
       - Derive BmSt base = match_addr - 0x14
    2. SECONDARY: Verify camera at +0x0C is plausible pixel coordinates
    3. SHORTCUT: Try PlaySt_base - 0x40 first (BmSt is contiguous with PlaySt)

    Requires the game to be on the tactical map (not title screen).
    """
    game_info = probe.game_info
    addrs = game_info.addresses

    print()
    print("=" * 80)
    print(f"  BmSt Discovery Tool — {game_info.title}")
    print("=" * 80)

    # Read current cursor position from PlaySt
    if addrs.cursor_x == 0:
        print("\n  ERROR: Cursor addresses not configured. Cannot search for BmSt.")
        return

    cursor_x = probe.read_u8(addrs.cursor_x)
    cursor_y = probe.read_u8(addrs.cursor_y)
    print(f"\n  PlaySt cursor: ({cursor_x}, {cursor_y})")

    if cursor_x == 0 and cursor_y == 0:
        print("  WARNING: Cursor at (0,0) — make sure you're on the tactical map!")

    # Compute PlaySt base from known field offsets
    # PlaySt layout: chapter at +0x0E, phase at +0x09, turn at +0x10, cursor at +0x12/0x13
    playst_base = addrs.chapter - 0x0E  # Most reliable derivation
    print(f"  PlaySt base (derived): 0x{playst_base:08X}")

    # Expected camera values (GBA centers camera on cursor)
    expected_cam_x = cursor_x * 16 - 120
    expected_cam_y = cursor_y * 16 - 80
    print(f"  Expected camera (approximate): ({expected_cam_x}, {expected_cam_y})")
    print(f"  Note: Camera is clamped to map bounds; may be (0,0) on small maps.")

    # --- Strategy 1: Try PlaySt - 0x40 directly (BmSt is contiguous) ---
    shortcut_base = playst_base - 0x40
    print(f"\n  Trying shortcut: BmSt = PlaySt - 0x40 = 0x{shortcut_base:08X}")
    shortcut_data = probe.read_memory(shortcut_base, 0x40)

    candidates = []
    if len(shortcut_data) >= 0x40:
        pcursor_x = struct.unpack_from("<h", shortcut_data, 0x14)[0]
        pcursor_y = struct.unpack_from("<h", shortcut_data, 0x16)[0]
        if pcursor_x == cursor_x and pcursor_y == cursor_y:
            candidates.append(("shortcut (PlaySt-0x40)", shortcut_base, shortcut_data))
            print(f"  ✓ Shortcut HIT: playerCursor=({pcursor_x},{pcursor_y}) matches PlaySt!")
        else:
            print(f"  ✗ Shortcut miss: playerCursor=({pcursor_x},{pcursor_y}) != PlaySt ({cursor_x},{cursor_y})")

    # --- Strategy 2: Scan for cursor pattern in wider region ---
    scan_base = playst_base - 0x200
    scan_len = 0x200
    print(f"\n  Scanning EWRAM: 0x{scan_base:08X} to 0x{playst_base:08X} ({scan_len} bytes)")
    scan_data = probe.read_memory(scan_base, scan_len)

    if len(scan_data) >= scan_len:
        for offset in range(0, len(scan_data) - 0x18, 2):
            val_x = struct.unpack_from("<h", scan_data, offset)[0]
            val_y = struct.unpack_from("<h", scan_data, offset + 2)[0]

            # Match: two s16 values == (cursor_x, cursor_y)
            if val_x == cursor_x and val_y == cursor_y:
                addr = scan_base + offset
                # BmSt.playerCursor is at offset +0x14 in the struct
                bm_base = addr - 0x14

                # Skip if base is before scan region or overlaps PlaySt
                if bm_base < scan_base or bm_base + 0x40 > playst_base + 0x20:
                    continue
                # Skip if already found via shortcut
                if any(c[1] == bm_base for c in candidates):
                    continue

                bm_data = probe.read_memory(bm_base, 0x40)
                if len(bm_data) >= 0x40:
                    candidates.append(("cursor scan", bm_base, bm_data))

    if not candidates:
        print("\n  No BmSt candidates found.")
        print("  Make sure you're on the tactical map (not title screen or menus).")
        print("  Move cursor to a non-(0,0) position if possible.")
        # Dump raw hex for manual inspection
        print(f"\n  Raw hex dump (0x{scan_base:08X}, {scan_len} bytes):")
        print(format_hex_dump(scan_data, scan_base))
        return

    # --- Display all candidates, best first ---
    print(f"\n  Found {len(candidates)} candidate(s):")
    for method, bm_base, bm_data in candidates:
        print(f"\n  {'─' * 60}")
        print(f"  BmSt base: 0x{bm_base:08X}  (found via {method})")

        # Parse all fields
        lock_val = bm_data[0x01]
        game_state_bits = bm_data[0x04]
        cam_x = struct.unpack_from("<h", bm_data, 0x0C)[0]
        cam_y = struct.unpack_from("<h", bm_data, 0x0E)[0]
        pcursor_x = struct.unpack_from("<h", bm_data, 0x14)[0]
        pcursor_y = struct.unpack_from("<h", bm_data, 0x16)[0]
        taken_action = bm_data[0x3D]

        print(f"  lock (+0x01):            {lock_val} ({'LOCKED — dialogue/anim active!' if lock_val > 0 else 'free (input accepted)'})")
        print(f"  gameStateBits (+0x04):   0x{game_state_bits:02X}")
        print(f"  camera (+0x0C):          ({cam_x}, {cam_y}) pixels")
        print(f"  playerCursor (+0x14):    ({pcursor_x}, {pcursor_y}) tiles")
        print(f"  taken_action (+0x3D):    {taken_action}")

        # Cross-checks
        cursor_match = (pcursor_x == cursor_x and pcursor_y == cursor_y)
        print(f"\n  Cross-checks:")
        print(f"    playerCursor vs PlaySt: ({pcursor_x},{pcursor_y}) vs ({cursor_x},{cursor_y})"
              f" {'✓ MATCH' if cursor_match else '✗ MISMATCH (tutorial/cutscene)'}")
        print(f"    Distance from PlaySt:   0x{playst_base - bm_base:X} bytes"
              f" {'✓ = 0x40 (expected)' if playst_base - bm_base == 0x40 else ''}")
        cam_plausible = -240 <= cam_x <= 1000 and -160 <= cam_y <= 1000
        print(f"    Camera plausible:       ({cam_x},{cam_y}) {'✓' if cam_plausible else '✗ out of range'}")

        # Print addresses to paste into game_registry.py
        print(f"\n  ── Paste into game_registry.py (GameAddresses) ──")
        print(f"  bm_lock=0x{bm_base + 0x01:08X},")
        print(f"  bm_camera_x=0x{bm_base + 0x0C:08X},")
        print(f"  bm_camera_y=0x{bm_base + 0x0E:08X},")
        print(f"  bm_cursor_x=0x{bm_base + 0x14:08X},")
        print(f"  bm_cursor_y=0x{bm_base + 0x16:08X},")
        print(f"  bm_game_state_bits=0x{bm_base + 0x04:08X},")
        print(f"  bm_taken_action=0x{bm_base + 0x3D:08X},")

        # Raw hex dump
        print(f"\n  Raw BmSt hex dump (0x{bm_base:08X}, 0x40 bytes):")
        print(format_hex_dump(bm_data, bm_base))

    print()
    print("=" * 80)


def find_event_slots(probe, target_x, target_y):
    """
    Discover gEventSlots array address or tutorial target cursor in RAM.

    Comprehensive search across IWRAM and EWRAM using multiple data formats:
    - s32 pairs (event slot style)
    - s16 pairs at 2-byte alignment (struct fields)
    - Pixel coordinates (tile * 16)
    - Packed coordinates in single words

    FE8 decomp: gEventSlots is 14 x s32 at 0x030004B8.
    FE7 address unknown — the tutorial cursor data may live elsewhere.
    """
    game_info = probe.game_info
    addrs = game_info.addresses

    print()
    print("=" * 80)
    print(f"  Tutorial Target / gEventSlots Discovery — {game_info.title}")
    print("=" * 80)
    print(f"\n  Target tile coordinates: ({target_x}, {target_y})")

    # Read current cursor for comparison
    cursor_x = probe.read_u8(addrs.cursor_x) if addrs.cursor_x else 0
    cursor_y = probe.read_u8(addrs.cursor_y) if addrs.cursor_y else 0
    print(f"  Current PlaySt cursor: ({cursor_x}, {cursor_y})")

    # Pixel equivalents
    px_x = target_x * 16
    px_y = target_y * 16
    px_x_center = target_x * 16 + 8  # tile center
    px_y_center = target_y * 16 + 8
    print(f"  Pixel equivalents: top-left=({px_x}, {px_y}), center=({px_x_center}, {px_y_center})")

    # Build all search patterns
    patterns = []

    # s16 pair: (x, y) as two adjacent little-endian s16 — 4 bytes
    pat_s16 = struct.pack("<hh", target_x, target_y)
    patterns.append(("s16 pair (x,y)", pat_s16, 2))

    pat_s16_rev = struct.pack("<hh", target_y, target_x)
    patterns.append(("s16 pair (y,x)", pat_s16_rev, 2))

    # s32 pair: (x, y) as two adjacent s32 — 8 bytes
    pat_s32 = struct.pack("<ii", target_x, target_y)
    patterns.append(("s32 pair (x,y)", pat_s32, 4))

    # Packed s32: x | (y << 16)
    packed_xy = target_x | (target_y << 16)
    patterns.append(("packed x|y<<16", struct.pack("<I", packed_xy), 4))

    # Packed s32: y | (x << 16)
    packed_yx = target_y | (target_x << 16)
    patterns.append(("packed y|x<<16", struct.pack("<I", packed_yx), 4))

    # Pixel coords as s16 pair
    pat_px = struct.pack("<hh", px_x, px_y)
    patterns.append(("pixel s16 (x*16, y*16)", pat_px, 2))

    pat_px_rev = struct.pack("<hh", px_y, px_x)
    patterns.append(("pixel s16 (y*16, x*16)", pat_px_rev, 2))

    # Pixel center coords as s16 pair
    pat_pxc = struct.pack("<hh", px_x_center, px_y_center)
    patterns.append(("pixel-center s16", pat_pxc, 2))

    # u8 pair (just two bytes)
    pat_u8 = bytes([target_x, target_y])
    patterns.append(("u8 pair (x,y)", pat_u8, 1))

    pat_u8_rev = bytes([target_y, target_x])
    patterns.append(("u8 pair (y,x)", pat_u8_rev, 1))

    print(f"\n  Search patterns:")
    for name, pat, _ in patterns:
        print(f"    {name}: {pat.hex()}")

    # ── Scan regions ─────────────────────────────────────────────────
    # Region 1: All of IWRAM (32KB)
    # Region 2: EWRAM around game state (BmSt through unit arrays, ~8KB)
    scan_regions = []

    # IWRAM: full 32KB
    IWRAM_BASE = 0x03000000
    IWRAM_SIZE = 0x8000
    scan_regions.append(("IWRAM", IWRAM_BASE, IWRAM_SIZE))

    # EWRAM: 8KB around BmSt/PlaySt (covers event engine state)
    if addrs.cursor_x:
        playst_base = addrs.chapter - 0x0E if addrs.chapter else addrs.cursor_x - 0x12
        ewram_start = playst_base - 0x1000  # 4KB before PlaySt
        ewram_size = 0x2000                 # 8KB total
        scan_regions.append(("EWRAM (game state region)", ewram_start, ewram_size))

    all_hits = []
    CHUNK_SIZE = 0x1000  # 4KB per socket read

    for region_name, region_base, region_size in scan_regions:
        print(f"\n  Scanning {region_name}: 0x{region_base:08X} - 0x{region_base + region_size - 1:08X} ({region_size // 1024}KB)")

        # Read region in chunks
        region_data = b''
        for chunk_off in range(0, region_size, CHUNK_SIZE):
            addr = region_base + chunk_off
            read_size = min(CHUNK_SIZE, region_size - chunk_off)
            try:
                chunk = probe.read_memory(addr, read_size)
                region_data += chunk
            except Exception as e:
                print(f"    WARNING: Failed to read at 0x{addr:08X}: {e}")
                region_data += b'\x00' * read_size

        # Search for each pattern
        for pat_name, pat_bytes, alignment in patterns:
            pat_len = len(pat_bytes)
            # For u8 pair (2 bytes), too many false positives — only report near known structs
            is_u8 = pat_len == 2 and alignment == 1
            step = alignment if alignment > 0 else 1

            for offset in range(0, len(region_data) - pat_len + 1, step):
                if region_data[offset:offset + pat_len] == pat_bytes:
                    hit_addr = region_base + offset
                    # u8 pair filter: only report if within 0x100 bytes of BmSt or PlaySt
                    if is_u8:
                        near_bmst = addrs.bm_lock and abs(hit_addr - (addrs.bm_lock - 1)) < 0x100
                        near_playst = addrs.chapter and abs(hit_addr - addrs.chapter) < 0x100
                        near_iwram_low = (IWRAM_BASE <= hit_addr < IWRAM_BASE + 0x1000)
                        if not (near_bmst or near_playst or near_iwram_low):
                            continue
                    all_hits.append((pat_name, hit_addr, region_name))

    # ── Display hits ─────────────────────────────────────────────────
    # Remove exact duplicates
    all_hits = list(set(all_hits))
    all_hits.sort(key=lambda h: h[1])

    # Exclude known addresses (cursor in PlaySt/BmSt, camera)
    known_addrs = set()
    if addrs.cursor_x: known_addrs.add(addrs.cursor_x)
    if addrs.cursor_y: known_addrs.add(addrs.cursor_y)
    if addrs.bm_cursor_x: known_addrs.update([addrs.bm_cursor_x, addrs.bm_cursor_y])
    if addrs.bm_camera_x: known_addrs.update([addrs.bm_camera_x, addrs.bm_camera_y])

    # Filter out hits at known cursor/camera addresses (and within 1 byte)
    filtered = []
    for pat_name, hit_addr, region_name in all_hits:
        near_known = any(abs(hit_addr - ka) <= 1 for ka in known_addrs)
        if near_known:
            print(f"    (skip known address: 0x{hit_addr:08X} — {pat_name})")
            continue
        filtered.append((pat_name, hit_addr, region_name))

    print(f"\n  ── Results: {len(filtered)} hits ({len(all_hits)} before filtering known addrs) ──")

    if not filtered:
        print("  No tutorial target coordinates found in any RAM region.")
        print()
        print("  NOTE: For FE7 (Blazing Blade), tutorial/movement/attack range indicators")
        print("  are computed dynamically by the event engine - they are NOT stored in RAM.")
        print("  This is expected behavior. Use hardcoded chapter targets instead.")
        print()
        print("  ── BmSt hex dump for manual inspection ──")
        if addrs.bm_lock:
            bm_base = addrs.bm_lock - 1
            bm_data = probe.read_memory(bm_base, 0x40)
            print(format_hex_dump(bm_data, bm_base))
            # Annotate known fields
            print(f"\n  Known BmSt fields:")
            print(f"    +0x01 lock:       {bm_data[0x01]}")
            print(f"    +0x04 stateBits:  0x{bm_data[0x04]:02X}")
            cam_x = struct.unpack_from("<h", bm_data, 0x0C)[0]
            cam_y = struct.unpack_from("<h", bm_data, 0x0E)[0]
            print(f"    +0x0C camera:     ({cam_x}, {cam_y}) px")
            pc_x = struct.unpack_from("<h", bm_data, 0x14)[0]
            pc_y = struct.unpack_from("<h", bm_data, 0x16)[0]
            print(f"    +0x14 cursor:     ({pc_x}, {pc_y}) tiles")
            # Show ALL s16 pairs in BmSt to find hidden fields
            print(f"\n  All s16 values in BmSt:")
            for off in range(0, 0x40, 2):
                val = struct.unpack_from("<h", bm_data, off)[0]
                if val != 0:
                    marker = ""
                    if val == target_x: marker = f"  ← matches target X!"
                    elif val == target_y: marker = f"  ← matches target Y!"
                    elif val == px_x: marker = f"  ← matches pixel X!"
                    elif val == px_y: marker = f"  ← matches pixel Y!"
                    print(f"      +0x{off:02X}: {val:6d} (0x{val & 0xFFFF:04X}){marker}")
        return

    # Show each hit with surrounding context
    for pat_name, hit_addr, region_name in filtered:
        print(f"\n  {'─' * 60}")
        print(f"  HIT: 0x{hit_addr:08X} — {pat_name} [{region_name}]")

        # Read 32 bytes of context around the hit
        ctx_start = max(hit_addr - 16, 0x02000000 if hit_addr >= 0x02000000 else 0x03000000)
        ctx_data = probe.read_memory(ctx_start, 64)
        print(format_hex_dump(ctx_data, ctx_start))

        # If this looks like an event slot array, show analysis
        if "s32" in pat_name:
            # Try to interpret as 14-slot array
            for slot_guess in range(14):
                base_guess = hit_addr - slot_guess * 4
                try:
                    arr_data = probe.read_memory(base_guess, 56)
                    if len(arr_data) >= 56:
                        slots = [struct.unpack_from("<i", arr_data, i * 4)[0] for i in range(14)]
                        small = sum(1 for s in slots if -256 <= s <= 256)
                        if small >= 7:
                            print(f"\n    Possible event slot array at 0x{base_guess:08X} (target at slot[{slot_guess}]):")
                            for i, val in enumerate(slots):
                                m = " ← TARGET" if i == slot_guess else ""
                                print(f"      [{i:2d}] = {val}{m}")
                            print(f"\n    event_slots_base=0x{base_guess:08X},")
                except Exception:
                    pass

    # For s16/u8/pixel hits, try to identify if it's part of a struct
    # by looking for adjacent coordinate pairs
    s16_hits = [(n, a, r) for n, a, r in filtered if "s16" in n or "u8" in n]
    if s16_hits:
        print(f"\n  ── Struct analysis for s16/u8 hits ──")
        for pat_name, hit_addr, region_name in s16_hits:
            # Read 128 bytes around hit for context
            ctx_base = max(hit_addr - 32, 0x02000000 if hit_addr >= 0x02000000 else 0x03000000)
            ctx_data = probe.read_memory(ctx_base, 128)
            offset_in_ctx = hit_addr - ctx_base
            print(f"\n    0x{hit_addr:08X} ({pat_name}):")
            print(f"    Offset from BmSt base: +0x{hit_addr - (addrs.bm_lock - 1):02X}" if addrs.bm_lock else "")
            print(f"    Offset from PlaySt base: +0x{hit_addr - (addrs.chapter - 0x0E):02X}" if addrs.chapter else "")

    print()
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="GBA Fire Emblem Memory Probe")
    parser.add_argument("--host", default="127.0.0.1", help="mGBA host")
    parser.add_argument("--port", type=int, default=8888, help="mGBA socket port")
    parser.add_argument("--watch", action="store_true", help="Refresh every 2 seconds")
    parser.add_argument("--raw", action="store_true", help="Show raw hex data for each unit")
    parser.add_argument("--diag", action="store_true", help="Diagnostic mode: dump raw hex of key memory regions")
    parser.add_argument("--find-bmst", action="store_true", help="Discover BmSt (Battle Map State) struct address")
    parser.add_argument("--find-event-slots", action="store_true", help="Discover gEventSlots address in IWRAM")
    parser.add_argument("--target-x", type=int, default=0, help="Target X coordinate for event slot search")
    parser.add_argument("--target-y", type=int, default=0, help="Target Y coordinate for event slot search")
    parser.add_argument("--interval", type=float, default=2.0, help="Watch interval (seconds)")
    args = parser.parse_args()

    probe = MemoryProbe(args.host, args.port)
    try:
        probe.connect()
    except (ConnectionRefusedError, OSError) as e:
        print(f"ERROR: Cannot connect to mGBA at {args.host}:{args.port}")
        print(f"  {e}")
        print()
        print("Make sure mGBA is running with the Lua socket server:")
        print(f"  ./scripts/run_mgba.sh {args.port}")
        sys.exit(1)

    # Auto-detect game from ROM header
    print()
    print("── Detecting Game ─────────────────────────────────────────")
    probe.detect_game()

    try:
        if args.find_event_slots:
            if args.target_x == 0 and args.target_y == 0:
                print("\nERROR: --find-event-slots requires --target-x X --target-y Y")
                print("  Example: python tools/memory_probe.py --find-event-slots --target-x 8 --target-y 7")
                sys.exit(1)
            find_event_slots(probe, args.target_x, args.target_y)
        elif args.find_bmst:
            find_bmst(probe)
        elif args.watch:
            while True:
                os.system("clear" if os.name != "nt" else "cls")
                try:
                    print_game_state(probe, args.raw, args.diag)
                except Exception as e:
                    print(f"Error reading state: {e}")
                print(f"\nRefreshing every {args.interval}s... (Ctrl+C to stop)")
                time.sleep(args.interval)
        else:
            print_game_state(probe, args.raw, args.diag)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        probe.disconnect()


if __name__ == "__main__":
    main()
