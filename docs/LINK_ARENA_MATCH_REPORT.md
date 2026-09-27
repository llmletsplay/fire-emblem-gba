# FE7 Link Arena minimax match

## Result

The first complete match through the Zephyrus harness finished on 2026-09-27.
FE7's own result screen declared green side 2P the winner:

| Place | Side | Team label | Points |
| --- | --- | --- | ---: |
| 1st | 2P, green | RAGNAROK | 520 |
| 2nd | 1P, blue | RAGNAROK | 346 |

The last live board had one survivor per side at 31 HP. The final result screen
and the ranking screen are saved from the Zephyrus API captures:

![FE7 Link Arena final result screen](link_arena_evidence/final-result.png)

![FE7 Link Arena ranking screen](link_arena_evidence/ranking.png)

## Reproduction details

- Match ID: `20260927T171244Z-c0eba3`
- Host: Zephyrus, Windows, mGBA 0.11 development portable build
- Save: GameFAQs Action Replay XPS `4120.xps`, imported by mGBA into an
  isolated 32 KB battery save
- Game mode: Linked Battle, Link Arena chapter 65, RAGNAROK teams
- Side A / 1P: bridge port 18888, blue team
- Side B / 2P: bridge port 18889, green team
- Local agent API: `127.0.0.1:18700`; each side acted with its own bearer token
- ROM and save were copied to match-local runner folders. The campaign save
  `roms/fe7.sav` was not opened or modified by this run.

Both sides used `MinimaxAgent(side, defender_auto_weapon=True)` against the
current side-scoped unit observations. Decisions selected both a matchup and a
weapon; FE7 resolved the combat, hit RNG, survival, points, and final rank. A
few representative decisions that reached in-game forecasts were B Hector with
Wolf Beil into A Oswin, A Canas with Luna into B Hector, B Bartre with Basilikos
into A Hector, A Canas with Luna into B Oswin, and B Dorcas with Brave Bow into
A Canas.

The harness actions and observations used the per-side HTTP API and token
files. The operator handled the setup menus, weapon-row confirms, and turn
handoff while consulting the live `DETAIL` cursor. One early grouped movement
overshot and caused A's 1 HP Oswin to attack B's Bartre instead of the planned
Hector/Oswin matchup; that exchange is part of this completed game. Afterward,
cursor movements were checked live and the later matchups followed the
minimax-selected units and weapons. This is a verified agent-driven match, but
not yet an unattended autoplay run.

The result screen is not currently parsed into a terminal outcome by the API.
The match was considered complete only after FE7 displayed the 2P 1st-place
screen and the ranking table showing 520 points versus 346.
