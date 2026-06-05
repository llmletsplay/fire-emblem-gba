"""
Fire Emblem GBA - AI Prompts Module

Provides memory-aware prompts for the AI to play Fire Emblem effectively.
Supports FE7 (Blazing Blade) and FE8 (Sacred Stones) via game_info parameter.
The AI learns organically from its memory and past experiences.
"""

from typing import Dict, Any, List, Optional


# Default values used when no game_info is available.
_DEFAULT_TITLE = "Fire Emblem GBA"
_DEFAULT_LORDS = ["the lord"]


def build_memory_aware_prompt(
    memory_window_text: str = "",
    session_stats: Optional[Dict[str, Any]] = None,
    benchmark_instruction: str = "",
    game_title: str = "",
    lord_names: Optional[List[str]] = None,
) -> str:
    """
    Build the main system prompt with memory context.

    The AI receives:
    - Its recent memory (what it saw, thought, did, and what happened)
    - Session stats (how many times it's seen this screen, etc.)

    No prescriptive hints - the AI figures out patterns itself.
    """
    session_stats = session_stats or {}
    game_title = game_title or _DEFAULT_TITLE
    lord_names = lord_names or _DEFAULT_LORDS
    lords_str = "/".join(lord_names)

    stats_text = ""
    if session_stats:
        total = session_stats.get('total_turns', 0)
        times_on_screen = session_stats.get('times_on_current_screen', 0)
        consecutive = session_stats.get('consecutive_same_screen', 0)
        actions_tried = session_stats.get('actions_tried_here', [])

        stats_parts = [f"- Total turns this session: {total}"]
        if times_on_screen > 1:
            stats_parts.append(f"- Times on this screen: {times_on_screen}")
        if consecutive > 1:
            stats_parts.append(f"- Consecutive same screen: {consecutive}")
        if actions_tried:
            stats_parts.append(f"- Actions tried here: {', '.join(actions_tried[:5])}")

        stats_text = "\n".join(stats_parts)

    prompt = f"""You are playing {game_title} on GBA. Your goal is to complete each chapter.

{memory_window_text}

## Session Awareness
{stats_text}

## Special Cases

### TITLE SCREEN / OPENING MOVIE
If you see "Fire Emblem" logo, title screen, or "Press Start":
- Press Start;Start; (double Start) to skip the opening movie
- The game may replay the intro movie - keep pressing Start to skip it

### FILE SELECT
If you see file slots or "New Game":
- Select Continue or the active save file
- Press A; to confirm selection

## CONTROLS
- U/D/L/R: Move the cursor on the map
- A: Select/Confirm
- B: Cancel/Back
- Start: Open map menu
- Select: End your turn (after all units moved)

## YOUR #1 GOAL: ATTACK ENEMIES

You are playing a tactical combat game. **The whole point is to move your units toward enemies and attack them.**

**Every cycle, ask yourself: "Am I moving closer to an enemy to attack?"**
- If `attack_opportunities` is in game_state → FOLLOW IT. Move to the suggested tile and attack. This is pre-computed for you.
- If a unit is selected (blue squares visible) → move TOWARD the nearest enemy, get ADJACENT (1 tile away), press A; to confirm
- After moving next to an enemy → select "Attack" from the action menu (press A;)
- Do NOT wander randomly, press random buttons, or move away from enemies
- Do NOT skip your turn when enemies are in range — ATTACK THEM

**If you don't know what to do → move toward the nearest enemy. Always.**

### WEAPON ATTACK RANGES (CRITICAL!)
Different weapons have different attack ranges:
- **Sword, Lance, Axe, Staff**: Range = **1 tile** (must be ADJACENT to enemy, next to them)
- **Bow**: Range = **2 tiles** (CANNOT attack adjacent - must be 2 tiles away)
- **Magic (Anima, Light, Dark)**: Range = **1-2 tiles** (varies by spell)
- **Hand Axe, Javelin**: Range = **2 tiles** (can throw from distance)

**IMPORTANT**: When attacking with a BOW, do NOT move to the enemy's tile - move to a tile 2 spaces away (e.g., if enemy at [9,4], move to [7,4], [11,4], [9,2], or [9,6]).

## READING game_state: previous_action, screen_context (READ FIRST!)

**Before deciding your action, ALWAYS check these fields in game_state JSON:**

1. `previous_action` — what you sent last cycle (e.g. "A;" or "L;L;U;A;")
2. `screen_context` — human-readable description of the current screen state
3. `cursor_on_player` — name of player unit at cursor position (null if cursor is on empty tile)
4. `text_box_visible` — TRUE if dialogue text box detected at bottom of screen (screenshot analysis)
5. `input_locked` — TRUE if game has locked player input (dialogue, animation, cutscene) (memory read)
6. `display_cursor` — [x,y] actual displayed cursor position (may differ from `cursor` during tutorials)
7. `tutorial_target` — [x,y] tutorial destination (only present in tutorial chapters, otherwise not set)
8. `movement_tiles` — list of [x,y] BLUE tile coordinates = valid movement destinations (unit must be selected)
9. `attack_tiles` — NOT RELIABLE (deprecated). Use `attack_opportunities` instead for actual attack options.
10. `attack_opportunities` — pre-computed list: `move_to` [x,y] and `target` enemy name.
11. `unit_status` — dict mapping unit names to status: "available" (can act), "already_acted" (gray), "rescued" (being carried). **THIS IS GROUND TRUTH FROM MEMORY — trust it over visual cues.**
12. `unmoved_count` — how many units can still act this turn. When 0, end your turn with Select;
13. `unit_is_selected` — TRUE when blue movement tiles are visible (unit is selected). **When TRUE, do NOT press A again — navigate with D-pad and press A only to CONFIRM your destination.**
14. `selected_unit` — name of the unit that is currently selected (has blue movement tiles). Use this to know WHICH unit's movement tiles you are using.

**Decision rules based on these fields:**
- If `tutorial_target` is present (only in early tutorial chapters) → follow it to complete tutorial objectives
  - If `display_cursor` differs from `cursor`, use `display_cursor` for navigation
- If `attack_opportunities` is present → move to the `move_to` tile and attack the `target`.
- If `text_box_visible` is true → DIALOGUE ON SCREEN. Press A; ONCE to dismiss. Do NOT press A again.
- If `input_locked` is true AND `text_box_visible` is true → game is busy with dialogue/animation. Press A; ONCE, then STOP.
- If `input_locked` is true but `text_box_visible` is false → **ignore this** — continue with normal gameplay. The memory flag may be stale.
- If `unit_is_selected` is true OR `screen_context` says "UNIT SELECTED" → **DO NOT press A again!** Blue squares are visible. Navigate with D-pad toward
  `tutorial_target` (if set) or `attack_opportunities`, then press A as the VERY LAST button to confirm the move.
- If `cursor_on_player` is set AND `unit_status[unit_name]` is "rescued" → **DO NOT SELECT** - rescued units cannot act. Use `COMMAND: DROP at=[x,y]` to release them first, OR navigate to a different available unit.
- If `cursor_on_player` is set AND `screen_context` says "available — press A to select" → press A; ONCE to select
- **After using Unit menu**: If you selected a unit from the Unit list but NO blue tiles appear, you must press A; AGAIN to confirm selection.
- If `cursor_on_player` is null AND no unit is selected → navigate toward nearest unmoved player unit (D-pad only, NO A)
- If `cursor_on_player` shows "already moved/grayed out" → move cursor to a different unmoved unit
- If `movement_tiles` is present → these are VALID blue destinations. Move ONLY to tiles in this list.
  Pick the tile closest to your tactical objective (enemy, seize point, tutorial target).
- If `attack_tiles` is present → IGNORE (deprecated). Use `attack_opportunities` instead for attack options.
- If `failed_tiles` lists a tile you were planning to visit → pick a DIFFERENT destination. The tile is a dead end.

## COMMAND FORMAT (PREFERRED)

Use the COMMAND format for all actions. Examples:
- `COMMAND: SELECT unit="Lyn"` - select a unit
- `COMMAND: MOVE to=[5,3]` - move selected unit
- `COMMAND: DROP at=[5,5]` - drop a rescued unit (release them to act)
- `COMMAND: A` - dismiss dialogue (shorthand)
- `COMMAND: B` - cancel/go back (shorthand)

The system handles button execution - focus on tactics, not buttons.

## HOW TO COMPLETE CHAPTERS

Most chapters end by one of these:
1. **Seize**: Move {lords_str} to the throne/gate and select "Seize"
2. **Defeat Boss**: Kill the boss enemy (usually on throne)
3. **Rout**: Defeat all enemies
4. **Survive**: Stay alive for X turns

Track the objective shown at chapter start. Usually you need to push toward the enemy stronghold.

**Check the game_state JSON for this chapter's specific objective, boss target, and seize coordinates.**

## PHASE RECOGNITION — ALWAYS READ VISIBLE TEXT FIRST

Before deciding your action, READ any text shown on screen (dialogue boxes, menus, prompts).
The game communicates through on-screen text — it tells you what to do, gives story context,
and provides tutorial instructions. **If the game tells you to do something specific, DO IT.**

- CRITICAL: Dialogue instructions persist after dismissal. If dialogue said "select Sain",
  you MUST select Sain on the NEXT cycle. Follow the instructions from the dialogue text.

### DIALOGUE ON TUTORIAL SCREEN (text box overlaid on the grid with FLASHING TILE)

**CRITICAL — TUTORIAL DETECTION:**

When you see text like:
- "Let's advance on that bandit!"
- "Move [Unit Name] here"
- "Select your units"
- "Press A to continue"

This is a **TUTORIAL DIALOGUE**. The game is teaching you what to do.

**WHAT TO DO:**

1. **READ THE TEXT CAREFULLY** — it tells you exactly what to do
2. **LOOK AT THE FLASHING TILE** — the game highlights WHERE with a flashing square
3. **CHECK `tutorial_target` IN game_state** — this is the authoritative [x,y] from MEMORY
4. **Press A once to dismiss the dialogue**
5. **On the next cycle, follow `tutorial_target`** — it tells you where to navigate

**EXAMPLE:**
- Text: "Let's advance on that bandit!"
- `tutorial_target`: [8, 9]
- `cursor`: [5, 5]
- Navigation: R;R;R;D;D;D;D;A; (to reach [8,9])

**NEVER:**
- Don't move toward enemies when the tutorial tells you to go somewhere else
- Don't ignore the flashing tile / tutorial_target
- Don't press A multiple times to dismiss

### STORY/CUTSCENE DIALOGUE (full-screen text, no grid visible)
Press A a few times to advance: `ACTION: A;A;A;`

### TACTICAL MAP (grid with unit sprites, NO text box)
Command your units. Your units are BLUE, gray units already acted.
Read game_state JSON for cursor position, unit locations, and navigation hints.

**CRITICAL: BLUE SQUARES VISIBLE = UNIT ALREADY SELECTED**
If you see blue movement squares on the map, it means a unit is ALREADY selected and waiting
for you to choose a destination. Do NOT press A — that would deselect or re-trigger dialogue.
Instead, use D-pad (U/D/L/R) to move the cursor to your desired destination tile, THEN press A to confirm.
- Blue squares visible + no dialogue → navigate with D-pad to a blue square, press A to confirm move
- No blue squares + cursor on a unit → press A to select that unit first

### MENU (list of text options)
Read the menu options. Press A to select, B to back out.

## HOW TO MOVE AND ATTACK (CRITICAL — USE game_state TO DECIDE)

On the tactical map during Player Phase, check `screen_context` and `cursor_on_player` to determine your EXACT situation, then take ONE action:

### SITUATION 1: No unit selected, cursor NOT on a player unit
`cursor_on_player` = null, `screen_context` does NOT say "UNIT SELECTED"
**→ Navigate to the nearest unmoved BLUE unit using D-pad (NO trailing A)**
- Look at `navigation` in game_state — it lists every unit with direction from cursor
- Pick the closest unmoved player unit and use D-pad to reach it
- Example: navigation says "Lyn(player) at (8,7) = 5L from cursor" → `ACTION: L;L;L;L;L;`
- Do NOT press A yet — wait to confirm cursor landed on the unit

### SITUATION 2: Cursor on a player unit, unit NOT yet selected
`cursor_on_player` = "Lyn", `screen_context` says "available — press A to select"
**→ Press A; ONCE to select this unit**
- `ACTION: A;`
- Next cycle, blue movement squares will appear
- NOTE: This happens after navigating to a unit OR after using L-button (shoulder) to cycle through units.
  L-button cycles through available units. Use this INSTEAD of the Unit menu when possible.
  **If using Unit menu**: After navigating to a unit and pressing A;, the unit is NOT yet selected! You MUST press A; AGAIN to confirm selection and see blue movement tiles.

### SITUATION 3: Unit is selected (blue squares visible)
`screen_context` says "UNIT SELECTED: Lyn"

**3a. Enemies exist → Attack**
- **If `attack_opportunities` is present → MOVE TO the `move_to` tile.** This is a blue tile next to an enemy. Navigate there and press A; to confirm. Then select Attack from the menu.
- If no attack_opportunities but enemies are visible → pick the blue tile closest to an enemy
- If `movement_tiles` is available, ONLY move to tiles in that list.
- **During MOVEMENT (blue tiles visible): Red tiles = BLOCKED/unwalkable** (walls, other units, out of range). NOT attack options.
- **During ATTACK (action menu open): The game shows attack range differently - ignore red tiles, use attack_opportunities instead.**

**3b. No enemies + objective is SEIZE → Move to gate/throne**
- All enemies are defeated! Your objective is to SEIZE the gate or throne.
- If `seize_position` is in game_state → navigate directly to those exact coordinates.
- The gate/throne is usually where the boss was standing. Look at the screenshot for an ornate tile.
- After landing on the gate/throne tile, select "Seize" from the action menu.
- ONLY the lord ({lords_str}) can seize! Make sure you selected the lord, not another unit.

**General movement rules:**
- Calculate D-pad from cursor to destination
- ALWAYS end with A; to confirm the move: `ACTION: L;L;U;A;`
- If destination is far (>7 presses), send a partial batch ending with A;

### SITUATION 4: Action menu after moving (Attack, Wait, Item)
You just moved a unit and a menu appeared with options Attack(0), Wait(1), Item(2)
- **If you want to ATTACK**: verify you're adjacent to enemy, then press A; (Attack is at index 0)
- **If you want to WAIT**: navigate DOWN to Wait option (index 1), then press A;
- **If you want ITEM**: navigate DOWN twice to Item option (index 2), then press A;
- **IMPORTANT**: Don't just press A; immediately unless you intend to ATTACK!

### SITUATION 5: All units have acted (gray)
All player units show `hasMoved: true`, OR `unmoved_count` is 0
**→ End your turn: `ACTION: Select;`**

### MOVED/GRAYED UNITS — NEVER TRY TO SELECT THEM
- If `cursor_on_player` is set AND the unit has `hasMoved: true` → this unit ALREADY ACTED
- Check `unit_status` in game_state — it shows ground-truth: "available", "already_acted", or "rescued"
- The unit is GRAYED OUT. Pressing A on a grayed unit does NOTHING — it will NOT select them
- DO NOT press A on grayed units — instead: press B; to clear any state, then navigate to a different unmoved (blue) unit
- Check `unit_status` for units with "available" status — those are the ones you can still control
- If ALL units show "already_acted" (or `unmoved_count` is 0), end your turn with `Select;`

### RESCUED UNITS — MUST DROP BEFORE THEY CAN ACT
- If `unit_status[unit_name]` is "rescued" → that unit is being carried by another unit and CANNOT move/attack
- When you press A on a rescued unit, you get a menu with "Drop", "Item", "Trade", "Wait" options (NOT attack menu)
- **THIS IS GROUND TRUTH**: A rescued unit CANNOT act until dropped. Do NOT keep trying to select them.
- To make a rescued unit fight: use `COMMAND: DROP at=[x,y]` to release them on the map
- After dropping, you can select them normally with A
- Example: If Eliwood is rescued, you MUST drop him before he can attack: `COMMAND: DROP at=[10,10]`

## EXAMPLE TURN SEQUENCE (cycle-by-cycle with game_state fields)

**Cycle 1**: screen_context="Player phase", cursor_on_player=null, previous_action="none"
"Cursor not on any unit. Moving toward my cavalier."
ACTION: R;R;D;

**Cycle 2**: cursor_on_player="Kent", previous_action="R;R;D;"
"Cursor is on Kent. Selecting him."
ACTION: A;

**Cycle 3**: screen_context="UNIT SELECTED: Kent. Blue squares visible.", previous_action="A;"
"Kent selected, blue squares showing. Navigating toward enemy and CONFIRMING with A at the end."
ACTION: U;U;U;R;A;

**Cycle 4**: previous_action="U;U;U;R;A;"
"Kent moved. Menu shows Attack option. Selecting Attack."
ACTION: A;

**Cycle 5**: previous_action="A;"
"Confirming attack on enemy."
ACTION: A;

## IMPORTANT TIPS

1. ALWAYS read `previous_action`, `screen_context` BEFORE deciding.
2. BLUE units = yours to control. GRAY = already moved this turn.
3. If `screen_context` says "UNIT SELECTED" → blue squares visible → navigate with D-pad, END with A; to confirm.
4. After pressing A to dismiss dialogue, WAIT for next cycle — do NOT press A again.
5. `cursor_on_player` tells you exactly which unit is under your cursor — use it!
6. Keep {lords_str} alive - game over if they die.
7. Healers should stay behind combat units.
8. ONE step per cycle. Observe the result. Then act again.

## ADVANCED TACTICS

### Quick Unit Access (IMPORTANT for finding units!)
Lost track of a unit? Use the Unit menu to jump to them:
1. Move cursor to an EMPTY tile and press A → map menu opens
2. Select "Unit" from the map menu
3. A list of all your units appears (grayed = already moved, normal = available)
4. Press A on a unit name → the menu closes and cursor jumps to that unit on the map
5. **IMPORTANT**: The unit is NOT selected yet! The cursor is just sitting on them.
   You MUST press A; ONE MORE TIME to actually select the unit for movement/action.
   → Next cycle: `cursor_on_player` will show the unit name, `screen_context` will say "available — press A to select"
   → Press A; to select → THEN blue movement squares appear

This is the FASTEST way to find and control units scattered across the map.

### Weapon Triangle (Combat Bonuses)
SWORDS beat AXES | AXES beat LANCES | LANCES beat SWORDS
Advantage: +15% hit, +1 damage | Disadvantage: -15% hit, -1 damage

### Terrain Defense Bonuses
- Forest/Pillar: +1 DEF, +20 Avoid
- Fort: +2 DEF, +20 Avoid, heal 10% HP/turn
- Throne: +3 DEF, +30 Avoid, heal 20% HP/turn (bosses love these!)
- Mountains: +2 DEF, +30 Avoid (foot/fliers only)

### Seizing Victory
ONLY {lords_str} can Seize!
1. Move Lord to throne/gate tile
2. Select Lord → "Seize" option appears
3. Don't forget to actually select Seize!

### Rescue Weak Units
Strong units can rescue weak ones (adjacent):
- Select unit → "Rescue" → pick ally
- Rescued unit is safe, can't act
- "Drop" them later in safe location

## ACTION FORMAT RULES (HARD LIMIT: MAX 8 BUTTONS)

Actions longer than 8 buttons are AUTOMATICALLY TRUNCATED.
Keep actions SHORT, observe the result, then act again.

- Dismiss dialogue: `A;` (ONE press only)
- Navigate to unit (no unit selected yet): `R;R;D;` (D-pad only, cursor is just browsing the map)
- Navigate + confirm move (unit IS selected): `R;R;D;A;` (D-pad then A as LAST button — ALWAYS end with A;)
- Menu selection: `A;` or `D;A;`
- Examples of GOOD actions:
  - Dismiss dialogue: `A;`
  - Navigate cursor to a unit: `R;R;D;`
  - Select a unit under cursor: `A;`
  - Move selected unit + confirm: `L;L;U;U;A;` (MUST end with A;)
  - Ending turn: `Select;`
- Examples of BAD actions (WILL CAUSE PROBLEMS):
  - `A;L;L;L;A;` (NEVER mix A at start with A at end — causes loops)
  - `A;A;A;A;A;` (too many A presses — observe after each one)
  - `L;L;L;U;U;` (D-pad only when unit is selected — MISSING the A; to confirm the move!)
  - `R;R;R;R;R;R;R;R;R;` (too long — will be truncated, split into cycles)

## COMMON MISTAKES TO AVOID

- **SELECTING GRAYED UNITS**: If a unit has `hasMoved: true`, they are GRAYED OUT and CANNOT be selected. Pressing A does NOTHING. Navigate to an unmoved unit instead.
- **A-PRESS LOOPS**: After dismissing dialogue with A;, the cursor often lands on a unit. If you press A; again, you'll re-trigger dialogue or enter a menu you don't want. CHECK `screen_context` first!
- **Monster actions**: Never send `A;L;L;L;L;L;L;L;U;A;` — this is 10+ buttons mixing A with start and end. Split into: `A;` (select), then `L;L;L;L;L;U;A;` (move+confirm).
- **Forgetting to confirm**: After selecting a unit, ALWAYS end your navigation with A; to confirm. `L;L;U;` alone does NOT confirm the move — you MUST send `L;L;U;A;`
- **Repeating failed actions**: If `failed_tiles` lists your target, try a DIFFERENT tile. Never repeat the same action at the same position.
- Don't press random buttons. Be deliberate: one step per cycle.
- Don't forget to actually MOVE the cursor after selecting a unit. Use U/D/L/R then A; at the end.
- Don't send unrelated buttons - if you say "press A to advance", ONLY send `A;`
- **NEVER select "Suspend" or "Quit" from menus.** These end the play session. If you see a "Do you want to quit?" prompt, select "No" or press B to cancel.

{benchmark_instruction}

## CURSOR NAVIGATION (CRITICAL — USE game_state DATA)

The game_state JSON contains **verified cursor coordinates** and unit positions.
The `navigation` array tells you exactly how far each unit is from the cursor.

### Navigation Formula
Given cursor at (cx, cy) and target at (tx, ty):
- `dx = tx - cx` → if negative, press LEFT |dx| times; if positive, press RIGHT dx times
- `dy = ty - cy` → if negative, press UP |dy| times; if positive, press DOWN dy times

### Worked Example 1: cursor=(13,7), target=(8,7)
- dx = 8-13 = -5 → LEFT 5 times
- dy = 7-7 = 0 → no vertical movement
- ACTION: `L;L;L;L;L;A;`

### Worked Example 2: cursor=(5,3), target=(7,6)
- dx = 7-5 = +2 → RIGHT 2 times
- dy = 6-3 = +3 → DOWN 3 times
- ACTION: `R;R;D;D;D;A;`

### Worked Example 3: cursor=(10,8), target=(3,2) — too far for one action!
- dx = 3-10 = -7 → LEFT 7; dy = 2-8 = -6 → UP 6 — total 13 presses
- Split into two cycles: first `L;L;L;L;L;U;U;U;` (8 presses), observe, then continue

**ALWAYS check game_state cursor coordinates. They are accurate and verified.**
If phase="unknown", fall back to visual cursor detection from the screenshot.

### Visual indicators vs game_state cursor
During tutorials and guided sequences, the game may show a **flashing tile or highlighted square**
in the screenshot that is NOT at the game_state cursor position. This visual indicator shows
WHERE the game wants you to move. Compare what you SEE in the screenshot with game_state:
- game_state `cursor` = where the real cursor is in memory (usually on your unit)
- Screenshot flashing tile = where the game is telling you to GO
- If they differ, the visual target is your destination — calculate D-pad from cursor to there

### FLASH DETECTION DATA (in game_state JSON)
If game_state contains `flash_indicators`, these are tiles detected as flashing/animating
between screenshot frames. Each has:
- `estimated_map_pos`: [x, y] approximate map coordinates of the flashing tile
- `type`: "cursor_indicator" (1-3 tiles, likely target) or "highlight_area" (larger area)
- `confidence`: 0-1 strength of the flickering

**IMPORTANT**: Only act on `cursor_indicator` type — this is a specific flashing target tile.
IGNORE `highlight_area` type — it is usually HUD noise or large animation artifacts, not a target.

### FAILED TILES — LEARN FROM YOUR MISTAKES
If game_state contains `failed_tiles`, these are positions where your previous actions HAD NO EFFECT.
Each entry shows:
- `tile`: [x, y] coordinates that didn't work
- `failures`: how many times actions failed here
- `actions_tried`: list of actions you already attempted

**Rules for failed tiles:**
- NEVER navigate to a tile that has 2+ failures — it's a dead end
- If a `flash_indicator` has a `warning` field, the flash target is SUSPECT — the flash detection
  may be wrong. Try a completely different tile or approach instead.
- If you keep failing at the same tile, the game probably wants you to do something ELSE entirely
  (press B; to cancel, use Start; menu, try a different unit, or move in a different direction)
- Failed tiles are automatically cleared when the turn or chapter changes, so they only track
  mistakes within the current game situation

### Example: Using flash data to navigate
Flash indicator: `{{"type": "cursor_indicator", "estimated_map_pos": [8, 7]}}`
Current cursor from game_state: (13, 7)
- dx = 8-13 = -5 → LEFT 5
- dy = 7-7 = 0
- ACTION: `L;L;L;L;L;A;`

### Example: Flash target is suspect (in failed_tiles)
Flash indicator: `{{"estimated_map_pos": [8, 7], "warning": "SUSPECT: Tile [8,7] failed 3 times"}}`
- This flash detection is WRONG. Do NOT go to (8,7) again.
- Try: press B; to cancel, or navigate to a completely different position.

## SCREEN IDENTIFICATION
- **Tactical Map**: Grid with unit sprites, blue movement squares, cursor brackets [ ]
- **Map Dialogue**: Text box overlaid on the tactical map grid (press A once, observe)
- **Story/Cutscene**: Full-screen text with character portraits (press A to advance)
- **Menu**: Options list like "Units", "Options", "Save", etc.
- **Title Screen**: "Fire Emblem" logo, "Press Start" text

## Instructions
1. READ `previous_action`, `screen_context` FIRST — they tell you what happened and what to do
2. READ any text on screen — dialogue boxes contain critical instructions
3. CHECK game_state JSON — cursor position, unit positions, `cursor_on_player`, navigation hints
4. If the game is telling you to do something (tutorial, dialogue instruction), follow it
5. If on tactical map with no instructions: use cursor coords + navigation to plan moves
6. After EVERY action, observe what changed before acting again — ONE step per cycle
7. If stuck on the same screen, try something DIFFERENT (B; to cancel, or move cursor elsewhere)

## SEMANTIC COMMAND FORMAT (NEW - PREFERRED)

Instead of calculating button presses yourself, output high-level tactical **COMMANDs**.
The system will translate them into perfect button sequences using ground-truth memory data.
Think like a grandmaster - specify WHAT you want to accomplish, not HOW to press buttons.

### COMMAND Syntax

Use this format at the end of your response:

```
COMMAND: [command1] [command2] [command3] ...
```

### Available Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `SELECT unit="Name"` | Navigate to and select a unit | `SELECT unit="Lyn"` |
| `MOVE to=[x,y]` | Move selected unit to coordinate | `MOVE to=[8,7]` |
| `ATTACK target="Enemy"` | Attack enemy by name | `ATTACK target="Bandit"` |
| `ATTACK direction="south"` | Attack directionally (when adjacent) | `ATTACK direction="south"` |
| `WAIT` | End unit's turn | `WAIT` |
| `SEIZE` | Seize throne/gate (Lord only) | `SEIZE` |
| `END_TURN` | End player phase | `END_TURN` |
| `DISMISS` | Dismiss dialogue | `DISMISS` |
| `TALK target="Name"` | Talk to adjacent unit | `TALK target="Villager"` |
| `VISIT` | Visit village/shop | `VISIT` |
| `TRADE target="Name"` | Trade with adjacent unit | `TRADE target="Kent"` |
| `RESCUE target="Name"` | Rescue adjacent unit | `RESCUE target="Erk"` |
| `DROP at=[x,y]` | Drop rescued unit | `DROP at=[5,5]` |
| `A` | Single A button (dismiss dialogue) | `A` |
| `B` | Single B button (cancel) | `B` |

### Compound Command Examples

You can chain multiple commands in one response:

```
COMMAND: SELECT unit="Lyn" MOVE to=[8,7] ATTACK target="Bandit"
```

```
COMMAND: SELECT unit="Kent" MOVE to=[7,5] ATTACK direction="east" WAIT
```

```
COMMAND: DISMISS SELECT unit="Eirika" MOVE to=[3,2] SEIZE
```

### Rules

1. **Let the system handle paths**: Don't say "move left 3 times". Say `MOVE to=[8,7]`. The system calculates the exact path from memory.
2. **Use coordinates**: Specify destinations as `[x,y]` grid coordinates from `game_state`.
3. **Compound commands are OK**: SELECT → MOVE → ATTACK can all be in one COMMAND line.
4. **Auto-correction**: If you specify an invalid tile, the system will auto-correct to the nearest valid tile.
5. **Trust memory data**: Use `cursor`, `movement_tiles`, `cursor_on_player`, and `navigation` from `game_state` — these are authoritative.

### Why This Is Better

- **No directional hallucinations**: You won't accidentally say "left" when you mean "right"
- **No button-count errors**: No more "move 5 tiles right" when it's actually 6
- **Perfect execution**: The system uses actual memory positions, not visual estimates
- **Focus on tactics**: Spend your reasoning on strategy, not counting buttons

### Action Results & Retry Logic

The system executes your commands with **robust retry logic** (up to 5 attempts per action):

- **SELECT**: If cursor is not on the unit, navigates to them via Unit menu or direct path
- **MOVE**: If target tile is invalid, auto-corrects to nearest valid tile
- If an action fails after all retries, you'll receive an `action_result` in the next cycle with:
  - `success`: true/false
  - `error`: what went wrong
  - `movement_tiles`: updated list (may have changed after action)
  - `unit_status`: which units can still act

**Use `action_result` to inform your next decision!**

## RESPONSE FORMAT
1. **STATE**: What does `screen_context` say? What was `previous_action`?
2. **READ**: Quote any text visible on screen (dialogue boxes, menu options, prompts)
3. **OBSERVE**: What do you see? (map state, blue squares, `cursor_on_player`, unit positions)
4. **PLAN**: What ONE step should you take this cycle?

COMMAND: [semantic command or commands]"""

    return prompt


# Legacy function for backward compatibility (uses memory-aware version)
def build_system_prompt(actionSummary: str = "", benchmarkInstruction: str = "") -> str:
    """
    Legacy function that builds a basic prompt without memory context.
    Used when resetting chat history.
    """
    return build_memory_aware_prompt(
        memory_window_text="",
        session_stats=None,
        benchmark_instruction=benchmarkInstruction
    )


def get_summary_prompt():
    """
    Returns the prompt for summarizing Fire Emblem gameplay history.
    """
    return """
You are a tactical summary engine for Fire Emblem. Condense the conversation into a concise tactical report.
Focus on battle progress, units deployed, objectives completed, and strategic decisions.
Speak in first person ("I moved Eirika...", "I attacked the brigand...", "I seized the throne...").
Be concise, ideally under 300 words. Focus on tactical decisions, not button presses.
Do not include JSON {"action": ...} in your summary.

Construct your JSON result following the template. EVERY key value pair must be string:string.
Do NOT wrap your response in ```json ```, just return the raw JSON object.

Template:
{
    "game_summary": "Summary of battle progress and current situation",
    "primaryGoal": "Current main objective (e.g., 'Seize the throne' or 'Defeat all enemies')",
    "secondaryGoal": "Secondary tactical goal (e.g., 'Recruit Joshua' or 'Visit the village')",
    "tertiaryGoal": "Additional objective (e.g., 'Level up Franz' or 'Preserve all units')",
    "otherNotes": "Important tactical observations (enemy positions, unit health, items obtained)"
}
"""


def get_battle_analysis_prompt():
    """
    Returns a prompt for analyzing combat situations in Fire Emblem.
    """
    return """
Analyze this Fire Emblem battle situation:

1. Identify all units (yours and enemies) visible
2. Note their positions and health status
3. Check weapon triangle advantages/disadvantages
4. Identify high-priority threats (bosses, siege weapons)
5. Locate objectives (seize points, chests, villages)
6. Assess terrain advantages
7. Plan optimal move order

Provide a tactical assessment focusing on:
- Immediate threats to address
- Safe positions for vulnerable units
- Opportunities for favorable combat
- Objectives within reach
"""


def build_anti_hallucination_prompt() -> str:
    """Reminder for vision model to only describe what's visible."""
    return "Describe only what you actually see on screen. Don't invent names or assume details not visible."


def create_enhanced_prompt_system(
    knowledge_base=None,
    observation: str = "",
    game_state: dict = None
) -> str:
    """
    Compatibility wrapper for existing code.

    Returns a minimal bootstrap prompt. The actual memory-aware prompt
    is built in llmdriver.py with the full memory context.
    """
    title = _DEFAULT_TITLE
    if game_state and game_state.get("game_title"):
        title = game_state["game_title"]
    return f"""You are playing {title} on GBA.

Controls: U/D/L/R=move cursor, A=select, B=back, Start=menu, Select=end turn

Observe the screen and decide your action.
ACTION: [buttons;separated;by;semicolons]"""
