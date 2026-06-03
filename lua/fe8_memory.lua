-- fe8_memory.lua - Fire Emblem 8 Memory Reading Functions
-- Verified against FE8 decomp (fireemblem8u)
-- Add to socketserver.lua or require this file

--------------------------------------------------------------------------
--  FE8 MEMORY ADDRESSES ------------------------------------------------
--------------------------------------------------------------------------
FE8_ADDR = {
    -- Unit Arrays (contiguous in EWRAM, verified from decomp + FEUniverse)
    PLAYER_UNITS = 0x0202BE4C,      -- gUnitArrayBlue[62]
    ENEMY_UNITS  = 0x0202CFBC,      -- gUnitArrayRed[50]  (0x0202BE4C + 62*0x48)
    NPC_UNITS    = 0x0202DDCC,      -- gUnitArrayGreen[20] (0x0202CFBC + 50*0x48)

    -- Game State (addresses verified from diagnostic hex dumps)
    CURRENT_CHAPTER = 0x0202BCFE,   -- verified: 0 in Prologue, 1 in Chapter 1
    GAME_MODE       = 0x0202BCB4,
    CURRENT_TURN    = 0x0202BD00,   -- verified: reads 1 on turn 1 of prologue
    PHASE           = 0x0202BCF9,   -- 0=Player, 1=Enemy, 2=NPC

    -- Cursor (verified: matches unit position when cursor is on unit)
    CURSOR_X = 0x0202BD02,         -- u8, not u16
    CURSOR_Y = 0x0202BD03,         -- u8, not u16

    -- Menu/Battle
    MENU_STATE    = 0x030030C4,
    BATTLE_ACTIVE = 0x0203A4D0,
}

-- Unit struct offsets (0x48 = 72 bytes per unit, verified from bmunit.h)
UNIT = {
    SIZE       = 0x48,  -- 72 bytes, NOT 76
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

-- Max units per array (verified from decomp)
MAX_UNITS = {
    PLAYER = 62,  -- gUnitArrayBlue[62]
    ENEMY  = 50,  -- gUnitArrayRed[50]
    NPC    = 20,  -- gUnitArrayGreen[20]
}

-- Allegiance flags (verified from decomp: FACTION_BLUE=0, GREEN=0x40, RED=0x80)
ALLEGIANCE = {
    PLAYER = 0x00,  -- FACTION_BLUE
    NPC    = 0x40,  -- FACTION_GREEN (ally)
    ENEMY  = 0x80,  -- FACTION_RED
    PURPLE = 0xC0,  -- FACTION_PURPLE
}

-- State flags (from bmunit.h US_ constants)
STATE_FLAGS = {
    HIDDEN       = 0x01,
    DEAD         = 0x02,
    NOT_DEPLOYED = 0x04,
    RESCUING     = 0x10,
    RESCUED      = 0x20,
    HAS_MOVED    = 0x40,
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

    -- Computed flags
    unit.is_dead = bit32.band(state, STATE_FLAGS.DEAD) ~= 0
    unit.is_hidden = bit32.band(state, STATE_FLAGS.HIDDEN) ~= 0
    unit.is_alive = unit.current_hp > 0 and not unit.is_dead and not unit.is_hidden
    unit.has_moved = bit32.band(state, STATE_FLAGS.HAS_MOVED) ~= 0
    unit.is_player = (allegiance == ALLEGIANCE.PLAYER)
    unit.is_enemy = (allegiance == ALLEGIANCE.ENEMY)
    unit.is_npc = (allegiance == ALLEGIANCE.NPC)

    return unit
end

-- Read all player units
function readPlayerUnits()
    local units = {}
    for i = 0, MAX_UNITS.PLAYER - 1 do
        local unit = readUnit(FE8_ADDR.PLAYER_UNITS, i)
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
        local unit = readUnit(FE8_ADDR.ENEMY_UNITS, i)
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
        local unit = readUnit(FE8_ADDR.NPC_UNITS, i)
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
        x = emu:read8(FE8_ADDR.CURSOR_X),
        y = emu:read8(FE8_ADDR.CURSOR_Y),
    }
end

function readChapter()
    return emu:read8(FE8_ADDR.CURRENT_CHAPTER)
end

function readTurn()
    return emu:read8(FE8_ADDR.CURRENT_TURN)
end

function readMenuState()
    return emu:read8(FE8_ADDR.MENU_STATE)
end

function isInBattle()
    local battle = emu:read8(FE8_ADDR.BATTLE_ACTIVE)
    return battle ~= nil and battle ~= 0
end

function getGamePhase()
    if isInBattle() then
        return "battle"
    end

    local chapter = readChapter()
    if chapter == 0 then
        return "start_screen"
    end

    local menu_state = readMenuState()
    if menu_state ~= 0 then
        return "menu"
    end

    local player_units = readPlayerUnits()
    local total_count = 0
    for _, unit in ipairs(player_units) do
        if unit.is_alive then
            total_count = total_count + 1
        end
    end

    if total_count > 0 then
        return "movement"
    end

    return "unknown"
end

--------------------------------------------------------------------------
--  UTILITY FUNCTIONS ---------------------------------------------------
--------------------------------------------------------------------------

function unitToString(unit)
    if not unit then return "nil" end
    return string.format(
        "{id=%d,cls=%d,hp=%d/%d,pos=(%d,%d),moved=%s}",
        unit.char_id,
        unit.class_id,
        unit.current_hp,
        unit.max_hp,
        unit.x,
        unit.y,
        unit.has_moved and "Y" or "N"
    )
end

function getGameStateString()
    local phase = getGamePhase()
    local counts = countUnits()
    local cursor = readCursor()
    local chapter = readChapter()
    local turn = readTurn()

    local parts = {
        "GAMESTATE",
        "phase=" .. phase,
        "chapter=" .. chapter,
        "turn=" .. turn,
        "cursor=" .. cursor.x .. "," .. cursor.y,
        "players=" .. counts.player_alive .. "/" .. counts.player,
        "enemies=" .. counts.enemy_alive .. "/" .. counts.enemy,
        "npcs=" .. counts.npc_alive .. "/" .. counts.npc,
    }

    return table.concat(parts, "|")
end

--------------------------------------------------------------------------
--  SOCKET COMMANDS (Add to parse function) ----------------------------
--------------------------------------------------------------------------

-- Command: GAMESTATE
function sendGameState(sock, sockId)
    console:log("[DEBUG] sendGameState: Socket " .. sockId .. " requested GAMESTATE")
    local state_str = getGameStateString()
    sock:send(state_str .. "\n")
    console:log("[DEBUG] sendGameState: Sent: " .. state_str)
end

-- Command: UNITS
function sendUnits(sock, sockId)
    console:log("[DEBUG] sendUnits: Socket " .. sockId .. " requested UNITS")

    local player_units = readPlayerUnits()
    local enemy_units = readEnemyUnits()
    local npc_units = readNpcUnits()

    local parts = {"UNITS"}

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

--------------------------------------------------------------------------
--  LOGGING & DEBUG -----------------------------------------------------
--------------------------------------------------------------------------

function logGameState()
    console:log("[FE8] " .. getGameStateString())
end

local frame_counter = 0
function periodicStateLog()
    frame_counter = frame_counter + 1
    if frame_counter >= 60 then
        frame_counter = 0
        -- Uncomment to enable periodic logging:
        -- logGameState()
    end
end

-- callbacks:add("frame", periodicStateLog)

console:log("[INFO] FE8 Memory Functions Loaded (decomp-verified)")
