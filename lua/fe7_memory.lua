-- fe7_memory.lua - Fire Emblem 7 Memory Reading Functions
-- Verified against FE7 (Blazing Blade) from live memory probes
-- Add to socketserver.lua or require this file

--------------------------------------------------------------------------
--  FE7 MEMORY ADDRESSES (VERIFIED via live probes) --------------------
--------------------------------------------------------------------------
FE7_ADDR = {
    -- Unit Arrays (verified from diagnostic hex dumps)
    PLAYER_UNITS = 0x0202BD08,      -- gUnitArrayBlue[62] (CONFIRMED: Lyn at slot 1)
    ENEMY_UNITS  = 0x0202CE78,      -- gUnitArrayRed[50]  (COMPUTED from player + 62*0x48)
    NPC_UNITS    = 0x0202DC88,      -- gUnitArrayGreen[20] (COMPUTED from enemy + 50*0x48)

    -- Game State (addresses verified from live hex dumps)
    CURRENT_CHAPTER = 0x0202BC06,   -- verified: reads 1 for Chapter 1
    CURRENT_TURN    = 0x0202BC08,   -- verified: 01→05 across turns
    PHASE           = 0x0202BC07,   -- verified: allegiance encoding (0x00=player, 0x80=enemy, 0x40=NPC)

    -- Cursor (verified: matches unit positions)
    CURSOR_X = 0x0202BC0A,         -- verified: PlaySt+0x12
    CURSOR_Y = 0x0202BC0B,         -- verified: PlaySt+0x13

    -- BmSt (Battle Map State) - verified via --find-bmst probe
    BM_LOCK          = 0x0202BBB9,  -- verified: lock=1 during "Let's advance on that bandit!" dialogue
    BM_CAMERA_X      = 0x0202BBC4,
    BM_CAMERA_Y      = 0x0202BBC6,
    BM_CURSOR_X      = 0x0202BBCC,  -- verified: playerCursor matches PlaySt cursor
    BM_CURSOR_Y      = 0x0202BBCE,
    BM_STATE_BITS    = 0x0202BBBC,
    BM_TAKEN_ACTION  = 0x0202BBF5,
}

-- Unit struct offsets (0x48 = 72 bytes per unit, verified from bmunit.h)
UNIT = {
    SIZE       = 0x48,  -- 72 bytes
    CHAR_PTR   = 0x00,  -- 4-byte pointer to CharacterData in ROM
    CLASS_PTR  = 0x04,  -- 4-byte pointer to ClassData in ROM
    LEVEL      = 0x08,  -- s8
    EXP        = 0x09,  -- u8
    AI_FLAGS   = 0x0A,  -- u8
    INDEX      = 0x0B,  -- s8 (bits 6-7 = allegiance)
    STATE      = 0x0C,  -- u32 (state bitmask)
    POS_X      = 0x10,  -- s8
    POS_Y      = 0x11,  -- s8
    MAX_HP     = 0x12,  -- s8
    CURRENT_HP = 0x13,  -- s8
    STR        = 0x14,  -- s8
    SKL        = 0x15,  -- s8
    SPD        = 0x16,  -- s8
    DEF        = 0x17,  -- s8
    RES        = 0x18,  -- s8
    LCK        = 0x19,  -- s8
    CON_BONUS  = 0x1A,  -- s8
    RESCUE     = 0x1B,  -- u8
    BALLISTA   = 0x1C,  -- u8
    MOV_BONUS  = 0x1D,  -- s8
    ITEMS      = 0x1E,  -- u16[5] (10 bytes)
    RANKS      = 0x28,  -- u8[8] (8 bytes)
    STATUS     = 0x30,  -- u8 (bits 0-3: effect, bits 4-7: duration)
}

-- Max units per array
MAX_UNITS = {
    PLAYER = 62,  -- gUnitArrayBlue[62]
    ENEMY  = 50,  -- gUnitArrayRed[50]
    NPC    = 20,  -- gUnitArrayGreen[20]
}

-- Allegiance flags (verified from decomp)
ALLEGIANCE = {
    PLAYER = 0x00,  -- FACTION_BLUE
    NPC    = 0x40,  -- FACTION_GREEN (ally)
    ENEMY  = 0x80,  -- FACTION_RED
    PURPLE = 0xC0,  -- FACTION_PURPLE
}

-- State flags (from bmunit.h)
STATE_FLAGS = {
    HIDDEN       = 0x01,
    DEAD         = 0x02,
    NOT_DEPLOYED = 0x04,
    RESCUING     = 0x10,
    RESCUED      = 0x20,
    HAS_MOVED    = 0x40,
    HAS_ACTED    = 0x02,  -- FE7-specific: bit 0x02 = has acted (vs dead in FE8)
}

--------------------------------------------------------------------------
--  UNIT READING FUNCTIONS ----------------------------------------------
--------------------------------------------------------------------------

-- Dereference a ROM pointer to get the ID (number field at +0x04)
-- CharacterData and ClassData both have their ID at offset 0x04
function derefId(pointer)
    if pointer < 0x08000000 or pointer > 0x09FFFFFF then
        return 0
    end
    return emu:read8(pointer + 0x04)
end

-- Read a single unit from memory
-- @param baseAddr: Base address of unit array
-- @param index: Unit index
-- @return: Unit table or nil if unit doesn't exist
function readUnit(baseAddr, index)
    local offset = baseAddr + (index * UNIT.SIZE)

    -- Check if unit exists (null CharacterData pointer = empty slot)
    local char_ptr = emu:read32(offset + UNIT.CHAR_PTR)
    if char_ptr == 0 then
        return nil
    end

    local class_ptr = emu:read32(offset + UNIT.CLASS_PTR)

    -- Dereference ROM pointers to get actual IDs
    local char_id = derefId(char_ptr)
    local class_id = derefId(class_ptr)

    -- Read allegiance from index byte bits 6-7
    local index_byte = emu:read8(offset + UNIT.INDEX)
    local allegiance = bit32.band(index_byte, 0xC0)

    -- Read state bitmask
    local state = emu:read32(offset + UNIT.STATE)

    local unit = {
        index = index,
        char_id = char_id,
        class_id = class_id,
        char_ptr = char_ptr,
        class_ptr = class_ptr,
        level = emu:read8(offset + UNIT.LEVEL),
        exp = emu:read8(offset + UNIT.EXP),
        allegiance = allegiance,
        max_hp = emu:read8(offset + UNIT.MAX_HP),
        current_hp = emu:read8(offset + UNIT.CURRENT_HP),
        str = emu:read8(offset + UNIT.STR),
        skl = emu:read8(offset + UNIT.SKL),
        spd = emu:read8(offset + UNIT.SPD),
        -- 'def' is a Lua keyword, use 'defense' instead
        defense = emu:read8(offset + UNIT.DEF),
        res = emu:read8(offset + UNIT.RES),
        lck = emu:read8(offset + UNIT.LCK),
        x = emu:read8(offset + UNIT.POS_X),
        y = emu:read8(offset + UNIT.POS_Y),
        status = emu:read8(offset + UNIT.STATUS),
        state = state,
    }

    -- Computed flags (FE7-specific: HAS_ACTED is bit 0x02)
    unit.is_dead = bit32.band(state, STATE_FLAGS.DEAD) ~= 0
    unit.is_hidden = bit32.band(state, STATE_FLAGS.HIDDEN) ~= 0
    unit.is_alive = unit.current_hp > 0 and not unit.is_dead and not unit.is_hidden
    unit.has_moved = bit32.band(state, STATE_FLAGS.HAS_MOVED) ~= 0
    unit.has_acted = bit32.band(state, STATE_FLAGS.HAS_ACTED) ~= 0
    unit.is_player = (allegiance == ALLEGIANCE.PLAYER)
    unit.is_enemy = (allegiance == ALLEGIANCE.ENEMY)
    unit.is_npc = (allegiance == ALLEGIANCE.NPC)

    return unit
end

-- Read all player units
function readPlayerUnits()
    local units = {}
    for i = 0, MAX_UNITS.PLAYER - 1 do
        local unit = readUnit(FE7_ADDR.PLAYER_UNITS, i)
        if unit then
            table.insert(units, unit)
        end
    end
    return units
end

-- Read all enemy units
function readEnemyUnits()
    local units = {}
    for i = 0, MAX_UNITS.ENEMY - 1 do
        local unit = readUnit(FE7_ADDR.ENEMY_UNITS, i)
        if unit then
            table.insert(units, unit)
        end
    end
    return units
end

-- Read all NPC units
function readNpcUnits()
    local units = {}
    for i = 0, MAX_UNITS.NPC - 1 do
        local unit = readUnit(FE7_ADDR.NPC_UNITS, i)
        if unit then
            table.insert(units, unit)
        end
    end
    return units
end

-- Count units by allegiance
function countUnits()
    local counts = {
        player = 0, enemy = 0, npc = 0,
        player_alive = 0, enemy_alive = 0, npc_alive = 0,
    }

    for _, unit in ipairs(readPlayerUnits()) do
        counts.player = counts.player + 1
        if unit.is_alive then counts.player_alive = counts.player_alive + 1 end
    end

    for _, unit in ipairs(readEnemyUnits()) do
        counts.enemy = counts.enemy + 1
        if unit.is_alive then counts.enemy_alive = counts.enemy_alive + 1 end
    end

    for _, unit in ipairs(readNpcUnits()) do
        counts.npc = counts.npc + 1
        if unit.is_alive then counts.npc_alive = counts.npc_alive + 1 end
    end

    return counts
end

--------------------------------------------------------------------------
--  GAME STATE FUNCTIONS ------------------------------------------------
--------------------------------------------------------------------------

function readCursor()
    return {
        x = emu:read8(FE7_ADDR.CURSOR_X),
        y = emu:read8(FE7_ADDR.CURSOR_Y),
    }
end

function readChapter()
    return emu:read8(FE7_ADDR.CURRENT_CHAPTER)
end

function readTurn()
    return emu:read8(FE7_ADDR.CURRENT_TURN)
end

function readPhase()
    -- FE7 uses allegiance encoding (unlike FE8's sequential 0/1/2)
    local phase_val = emu:read8(FE7_ADDR.PHASE)
    if phase_val == 0x00 then
        return "player"
    elseif phase_val == 0x80 then
        return "enemy"
    elseif phase_val == 0x40 then
        return "npc"
    else
        return "unknown"
    end
end

function readBmLock()
    return emu:read8(FE7_ADDR.BM_LOCK)
end

function readBmCamera()
    return {
        x = emu:read16(FE7_ADDR.BM_CAMERA_X),
        y = emu:read16(FE7_ADDR.BM_CAMERA_Y),
    }
end

function readBmCursor()
    return {
        x = emu:read16(FE7_ADDR.BM_CURSOR_X),
        y = emu:read16(FE7_ADDR.BM_CURSOR_Y),
    }
end

function readBmStateBits()
    return emu:read32(FE7_ADDR.BM_STATE_BITS)
end

function readBmTakenAction()
    return emu:read8(FE7_ADDR.BM_TAKEN_ACTION)
end

function isInputLocked()
    return readBmLock() ~= 0
end

function getGamePhase()
    -- Check if input is locked during animation/dialogue
    if isInputLocked() then
        local phase_ally = readPhase()
        if phase_ally == "player" then
            return "player_animation"
        elseif phase_ally == "enemy" then
            return "enemy_animation"
        end
        return "animation"
    end

    local chapter = readChapter()
    if chapter == 0 then
        return "start_screen"
    end

    local phase_val = emu:read8(FE7_ADDR.PHASE)
    if phase_val == 0x00 then
        return "player_phase"
    elseif phase_val == 0x80 then
        return "enemy_phase"
    elseif phase_val == 0x40 then
        return "npc_phase"
    end

    return "unknown"
end

--------------------------------------------------------------------------
--  TODO: Tutorial Target Detection (event_slots) -----------------------
--------------------------------------------------------------------------
-- NOTE: event_slots_base is currently UNKNOWN for FE7
-- gEventSlots in FE8 is at 0x030004B8 (14 x s32 in IWRAM)
-- FE7 may have a similar structure, but the address needs verification
-- Use memory_probe --find-event-slots to discover the FE7 address
--
-- Once found, add:
-- EVENT_SLOTS_BASE = 0x03000???  -- TODO: verify address
--
-- function readEventSlots()
--     local slots = {}
--     for i = 0, 13 do
--         local addr = EVENT_SLOTS_BASE + (i * 4)
--         slots[i] = emu:read32(addr)
--     end
--     return slots
-- end
--
-- function getTutorialTargetFromEventSlots()
--     local slots = readEventSlots()
--     Scan slots for coordinate pairs (x, y) that match typical tutorial positions
-- end
--------------------------------------------------------------------------

--------------------------------------------------------------------------
--  UTILITY FUNCTIONS ---------------------------------------------------
--------------------------------------------------------------------------

function unitToString(unit)
    if not unit then return "nil" end
    return string.format(
        "{id=%d,cls=%d,hp=%d/%d,pos=(%d,%d),moved=%s,ally=%02X}",
        unit.char_id,
        unit.class_id,
        unit.current_hp,
        unit.max_hp,
        unit.x,
        unit.y,
        (unit.has_moved or unit.has_acted) and "Y" or "N",
        unit.allegiance
    )
end

function getGameStateString()
    local phase = getGamePhase()
    local counts = countUnits()
    local cursor = readCursor()
    local chapter = readChapter()
    local turn = readTurn()
    local is_locked = isInputLocked()

    local parts = {
        "FE7",
        "phase=" .. phase,
        "chapter=" .. chapter,
        "turn=" .. turn,
        "cursor=" .. cursor.x .. "," .. cursor.y,
        "locked=" .. (is_locked and "Y" or "N"),
        "players=" .. counts.player_alive .. "/" .. counts.player,
        "enemies=" .. counts.enemy_alive .. "/" .. counts.enemy,
        "npcs=" .. counts.npc_alive .. "/" .. counts.npc,
    }

    return table.concat(parts, "|")
end

-- Detailed state dump for debugging
function getDetailedStateString()
    local phase = readPhase()
    local counts = countUnits()
    local cursor = readCursor()
    local bm_cursor = readBmCursor()
    local bm_camera = readBmCamera()
    local bm_state = readBmStateBits()
    local taken_action = readBmTakenAction()

    local parts = {
        "FE7_DETAIL",
        "phase_raw=" .. string.format("%02X", emu:read8(FE7_ADDR.PHASE)),
        "phase_name=" .. phase,
        "chapter=" .. readChapter(),
        "turn=" .. readTurn(),
        "cursor=" .. cursor.x .. "," .. cursor.y,
        "bm_cursor=" .. bm_cursor.x .. "," .. bm_cursor.y,
        "bm_camera=" .. bm_camera.x .. "," .. bm_camera.y,
        "bm_state=" .. string.format("%08X", bm_state),
        "taken_action=" .. taken_action,
        "locked=" .. readBmLock(),
        "players_alive=" .. counts.player_alive,
        "enemies_alive=" .. counts.enemy_alive,
    }

    return table.concat(parts, "|")
end

--------------------------------------------------------------------------
--  SOCKET COMMANDS (Add to parse function) ----------------------------
--------------------------------------------------------------------------

-- Command: GAMESTATE
function sendGameState(sock, sockId)
    console:log("[DEBUG] sendGameState: Socket " .. sockId .. " requested FE7 GAMESTATE")
    local state_str = getGameStateString()
    sock:send(state_str .. "\n")
    console:log("[DEBUG] sendGameState: Sent " .. state_str)
end

-- Command: UNITS
function sendUnits(sock, sockId)
    console:log("[DEBUG] sendUnits: Socket " .. sockId .. " requested FE7 UNITS")

    local player_units = readPlayerUnits()
    local enemy_units = readEnemyUnits()
    local npc_units = readNpcUnits()

    local parts = {"FE7_UNITS"}

    for _, unit in ipairs(player_units) do
        if unit.is_alive then
            table.insert(parts, "P:" .. unitToString(unit))
        end
    end

    for _, unit in ipairs(enemy_units) do
        if unit.is_alive then
            table.insert(parts, "E:" .. unitToString(unit))
        end
    end

    for _, unit in ipairs(npc_units) do
        if unit.is_alive then
            table.insert(parts, "N:" .. unitToString(unit))
        end
    end

    local response = table.concat(parts, "|")
    sock:send(response .. "\n")
    console:log("[DEBUG] sendUnits: Sent " .. #player_units + #enemy_units + #npc_units .. " units")
end

-- Command: DETAIL
function sendDetailedState(sock, sockId)
    console:log("[DEBUG] sendDetailedState: Socket " .. sockId .. " requested FE7 DETAIL")
    local detail_str = getDetailedStateString()
    sock:send(detail_str .. "\n")
    console:log("[DEBUG] sendDetailedState: Sent " .. detail_str)
end

-- Add to parse() function in socketserver.lua:
--
-- if line_upper == "GAMESTATE" then
--     sendGameState(sock, sockId)
--     return
-- end
--
-- if line_upper == "UNITS" then
--     sendUnits(sock, sockId)
--     return
-- end
--
-- if line_upper == "DETAIL" then
--     sendDetailedState(sock, sockId)
--     return
-- end

--------------------------------------------------------------------------
--  LOGGING & DEBUG -----------------------------------------------------
--------------------------------------------------------------------------

function logGameState()
    console:log("[FE7] " .. getGameStateString())
end

function logDetailedState()
    console:log("[FE7] " .. getDetailedStateString())
end

local frame_counter = 0
function periodicStateLog()
    frame_counter = frame_counter + 1
    if frame_counter >= 120 then  -- Log every 2 seconds (60 fps)
        frame_counter = 0
        -- Uncomment to enable periodic logging:
        -- logGameState()
    end
end

-- callbacks:add("frame", periodicStateLog)

console:log("[INFO] FE7 Memory Functions Loaded (verified via live probes)")
console:log("[INFO] FE7 Unit Arrays: Player=" .. string.format("0x%08X", FE7_ADDR.PLAYER_UNITS))
console:log("[INFO] FE7 Unit Arrays: Enemy=" .. string.format("0x%08X", FE7_ADDR.ENEMY_UNITS))
console:log("[INFO] FE7 Unit Arrays: NPC=" .. string.format("0x%08X", FE7_ADDR.NPC_UNITS))
console:log("[TODO] FE7 event_slots_base needs verification via memory_probe --find-event-slots")
