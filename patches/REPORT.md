# MiniMax wiring handoff (executor)

## Done on box
- MINIMAX_API_KEY: **set** (from card secrets; never printed)
- Smoke test against `https://api.minimax.io/v1/chat/completions` model `MiniMax-M2.5` max_tokens=1: **OK** (HTTP 200, finish_reason=length)
- Parent already pushed `feat/minimax-harness-refresh` with client_setup MINIMAX + reasoning_split + think-tag strip (commit b222ae85)

## Blocked: Mac machine exec
This executor is **box-scoped**. Shell/Read ignore `machineId` (not in tool schema; `isBoxScopedSubagent` omits ListMachines/machine routing).
Mac `.env` write at `/Users/area/repos/llmletsplay-fire-emblem/fe-gba/.env` **not performed**.
Landing page edits under `/Users/area/repos/@llmletsplay/llm-lets-play` **not performed**.

**Parent action:** re-dispatch Task with `machine: 8958adc4-24ef-4f68-8dc2-5bd09ea6cf53`, then:
1. Export key into Mac env (or CopyFromBox card secret via approved path)
2. `python3 /path/to/write_minimax_env.py`
3. `git -C .../fe-gba apply` the three patches (or cherry-pick content), commit on `feat/minimax-harness-refresh`, push
4. Landing honesty pass on development branch

## Top 3 harness smells
1. **Format schizophrenia:** prompts say `COMMAND:` preferred, then teach dozens of `ACTION: L;L;A;` examples; raw buttons after `COMMAND:` are rejected → wasted turns.
2. **Silent parse rejects:** empty `CommandSequence` on raw-button COMMAND lines with log-only warning; model never sees why.
3. **Triple output schema:** `COMMAND:` / `ACTION:` / JSON `{"action":...}` all live; emergency retry only re-parses ACTION/JSON.

## Fix packaged here
- `0001` reject_reason on CommandSequence
- `0002` inject `command_parse_error` into next game_state
- `0003` hard rule in prompts + document command_parse_error

## Landing
- `llmletsplay.com` returns **403** from fetch (Access-gated) — copy should say Access-gated honestly; repo link https://github.com/llmletsplay/fire-emblem-gba; drop dead public live-stream claims. Needs Mac checkout of `@llmletsplay/llm-lets-play`.

## Next priority
1. Mac-bound agent: write `.env`, apply patches, commit+push harness
2. Landing honesty commit on `development` (no Cloudflare ungate)
3. Later: collapse dual ACTION/COMMAND teaching in prompts (bigger rewrite — out of scope this pass)
