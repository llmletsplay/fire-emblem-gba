# FE GBA ATTACK (3,9) + CAP settle — box-prepared

## Root cause of `ATTACK target: Unit 0x3E at 3,9` after MOVE to (8,4)
**Not an x/y swap.** Unit POS_X=0x10 / POS_Y=0x11 are correct for party and enemies; movement_tiles orientation matches.

**Wrong unit match:** `get_enemy_by_name` used weak `needle in name` and returned the **first** enemy named `Unit 0x3E`. Char id `0x3E` is absent from FE7_CHARACTERS (gap 0x3D Wire → 0x3F Zagan), so multiple generics share the fallback name `Unit 0x3E`. First list hit at (3,9) → direction DOWN from (8,4) (matches backend-20260916-194055.log). Expected tile was the adjacent same-named enemy near (9,4)/(9,3).

**Also:** `attack_opportunities` (with correct `enemy_at` for the chosen `move_to`) lived only on `llm_input_state`; ATTACK executed against `current_mGBA_state` without that list, so the executor could not use opportunity adjacency.

## Files changed (box commit `a7b24ee` on `/workspace/fe-gba`)
- `src/game/command_executor.py` — tightened exact/id match + cursor tie-break; `resolve_attack_target_tile` prefers opportunities → adjacent Manhattan-1 → raw xy; logs `from-cursor` / `to-tile` / `source`
- `src/core/llmdriver.py` — copy `attack_opportunities` onto executor state; combat-aware settle via `FE_ATTACK_SETTLE_SEC`
- `src/core/config.py` — `ACTION_SETTLE_SEC` default 2.0; `ATTACK_SETTLE_SEC` default 6.0; `LOAD_SAVESTATE` stays false; `ATTACH_EXISTING` true
- CAP resilience (same commit): `run.py` / `image_utils.py` / `socket_utils.py` / `file_utils.py` — no LOADSTATE on attach, CAP retries, soft reconnect without killing loop

Offline proof: `test_attack_resolve.py` → `PASS A;RIGHT;A; … source=attack_opportunities` for duplicate Unit 0x3E at (3,9) vs (9,4) with cursor (8,4).

## CAP / Cycle 2 on Mac
**Not verified.** This executor is box-scoped; Shell cannot reach machineId `8958adc4-24ef-4f68-8dc2-5bd09ea6cf53` (macbook-lite.local). Parent must re-dispatch machine-bound and run:

```bash
# copy /workspace/fe-gba-attack-fix to Mac, then:
./APPLY_AND_RESTART_ON_MAC.sh /Users/area/repos/llmletsplay-fire-emblem/fe-gba
```

Or manually: apply `0001-fix-fe-gba-resolve-ATTACK-via-opportunities-adjacenc.patch`, set env, quit/relaunch mGBA with `--script lua/socketserver.lua roms/fe7.gba`, CAP-probe 3× on :8765, `FE_ATTACH_EXISTING=true FE_LOAD_SAVESTATE=false python src/core/run.py --auto`, watch newest `logs/backend-*.log` through Cycle 2.

Prior evidence log: `logs/backend-20260916-194055.log` (MOVE:m2 ok; ATTACK 3,9+DOWN; Cycle 2 CAP timeout; Lua socket dead / connection refused while mGBA PID up).

## Remaining blockers
1. Machine-bound apply + mGBA relaunch + CAP 3× + backend start
2. Confirm Cycle 2 CAP+LLM after combat settle; confirm ATTACK log shows `source=attack_opportunities` or `adjacent_to_cursor` (not raw first-list 3,9)
3. If Lua socket dies post-combat again: quit mGBA, relaunch with script, re-probe CAP, attach with FE_LOAD_SAVESTATE=false
