# FE7 Ch0 Prologue — live-verified tutorial sequence (2026-09-21)

Verified on Zephyrus (mGBA + lua socketserver) against Normal-mode tutorial soft-rejects.
Branch tip at verification: `feat/minimax-harness-refresh` commits `f3de491`, `6851a81`, `32d2e0b`.
Repo: `https://github.com/llmletsplay/fire-emblem-gba` (remote `git@github.com-lite:llmletsplay/fire-emblem-gba.git`).
Mac checkout: `~/repos/llmletsplay-fire-emblem/fe-gba`
Zephyrus: `C:\Users\thoma\llmletsplay\fire-emblem-gba`

## Coordinate notes
- Map is 15×10; coords are engine (x,y) as read from unit struct OFF_X/OFF_Y.
- Tutorial soft-rejects wrong destination tiles on confirm-A (pathing works; Lyn xy does not change).

## End-to-end sequence

| # | Step | Tile / action | Notes |
|---|------|---------------|-------|
| 0 | Start | Lyn@(13,7) | Save slot **1** is clean start. State often `0x00400001`. |
| 1 | MOVE | **(8,7)** | First flashing cursor. Equals “5 spaces left” (TASVideos). Soft-rejects (9,8) etc. |
| 2 | WAIT | end turn | After confirm, action menu → Wait. Enemy phase: brigand advances to **(7,6)**. |
| 3 | MOVE + ATTACK | **(8,6)** | Adjacent to brigand@(7,6). Then Attack. May take 2 rounds (HP 20→6→dead). |
| 4 | MOVE | **(5,4)** | Vulnerary flashing cursor (west / ger). |
| 5 | ITEM | Use Vulnerary | See UI path below. HP **6→16**. |
| 6 | MOVE + ATTACK | **(4,2)** | Adjacent to Batta@(3,2). Multi-round scripted fight. |
| 7 | SEIZE | **(3,2)** | Gate where Batta stood. Clear → Lyn@(255,2) (off-map), often HP17 after level-up. |

## Milestone savestates (Zephyrus)
- **1** — Ch0 start Lyn@(13,7)
- **4** — post-WAIT / brigand approached
- **6** — brigand dead, Lyn@(8,6)
- **7** — post-vulnerary heal HP16 @(5,4)
- **11** — post-heal next player phase
- **12** — mid/post Batta
- **13** — post-seize clear

## Critical UI: vulnerary (was the hard part)

After MOVE confirm onto (5,4):
1. Action menu shows **only “Item”**, but tutorial dialogue is still mid-line (“I'm carrying a couple of…”).
2. Mash **A** through all dialogue (~40 presses). Menu closes (`lock` drops from 2→1).
3. **B** clear, **A** reselect Lyn.
4. **A** → Item (tutorial-only / top option when reselected).
5. **DOWN** once (Iron Sword is first; Vulnerary second).
6. **A** select Vulnerary, **A** Use.
7. HP must rise (6→16). If HP unchanged, dialogue was not finished or wrong menu entry.

Do **not** treat `game_state_bits==0` as “dialogue done” — bits can already be 0 while text is still up.

## Probe tooling
- `tools/fe_move_probe6.py` — MOVE dest sweeps (`--dest X,Y --loadstate N`)
- `tools/fe_ch0_chain.py` / `fe_ch0_item_dialogue2.py` / `fe_ch0_batta_sweep.py` / `fe_ch0_batta_finish.py` — chain probes
- Windows: launch interactive via `schtasks … /IT /RU thoma` (SSH `start` cannot reach desktop session)
- Nuke overlapping Watch-FeHarness before probes (socket fights)

## Autonomous harness wiring goals
1. Default load **slot 1** for clean Ch0 runs (`FE_LOAD_SAVESTATE` / config).
2. `fe7_chapters.py` `tutorial_sequence` already carries verified coords — keep comments accurate.
3. `tutorial_progress` / `legal_moves` — hard-prefer tutorial dest; do not skip attack step solely because start tile overlaps approach list.
4. ITEM path: after tutorial MOVE to item tile, **dialogue mash then Item→Vulnerary→Use** (not bare DOWN on action menu while dialogue is up).
5. WAIT after first MOVE before expecting second MOVE.
6. In-repo at `docs/fe7-ch0-tutorial-verified.md`; cross-linked from README Tutorial mode / Ch0 section.

## Ch1 live-probe update (partial)

The Ch1 generic `tutorial_sequence` is intentionally still empty because the
current harness does not yet have a deterministic trade-item command. The
following route is nevertheless live-verified on Zephyrus (mGBA, 2026-09-21)
and is recorded as `FE7_CHAPTERS[1]["verified_milestones"]`:

| # | Unit | Tile / action | Result |
|---|------|---------------|--------|
| 1 | Sain | MOVE (4,5) → ATTACK | Scripted miss; Sain HP 19→13 |
| 2 | Kent | MOVE (4,7) → ATTACK | Iron Sword; brigand HP 20→11 |
| 3 | Lyn | MOVE (3,6) → ATTACK | Finishes first brigand |
| 4 | Sain | MOVE (5,9) → ATTACK | Woods miss; brigand stays HP 20 |
| 5 | Kent | MOVE (6,8) → ATTACK | Iron Sword; woods brigand HP 20→12 |
| 6 | Lyn | MOVE (5,4) | Highlighted forest; enemy phase reaches turn 3 |
| 7 | Sain | MOVE (5,5) → TRADE | Receives Lyn’s Vulnerary |
| 8 | Sain | ITEM → Vulnerary → Use | HP 13→19 |
| 9 | Sain | MOVE AGAIN (6,5) → WAIT | Mounted-unit tutorial completes |

Remote savestate **21** is the clean Ch1 battle start; **47** is the post-
Move Again tutorial checkpoint. The next implementation step is wiring the
trade sequence into the semantic command executor, then replacing the
milestones with the authoritative `tutorial_sequence`.

## External refs
- Serenes Prologue script
- TASVideos: first move “5 spaces to the left”
- FE Wiki: map 15×10; Hard mode is not the tutorial script
