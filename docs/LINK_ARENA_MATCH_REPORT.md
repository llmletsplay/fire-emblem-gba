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

## Unattended runner validation

On 2026-09-28, match `20260928T153714Z-75c7b5` completed on Zephyrus with
`--auto-minimax`. The runner navigated both clients from the title screen,
confirmed the saved RAGNAROK teams, completed the link handshake, mapped the
1P-first core, and played 31 exchanges with two built-in minimax agents. No
operator supplied gameplay inputs.

FE7's own final ranking screen declared green 2P RAGNAROK the winner:

| Place | Side | Team label | Points |
| --- | --- | --- | ---: |
| 1st | 2P, green | RAGNAROK | 576 |
| 2nd | 1P, blue | RAGNAROK | 288 |

![Unattended FE7 Link Arena final ranking: 2P wins 576 to 288](link_arena_evidence/unattended-final-ranking.png)

The startup and every exchange used the verified one-input controller: it
checked cursor coordinates and menu rows after each button, confirmed the
weapon/status-card gates, and waited for synchronized rosters before either
agent acted again. At the end, both cores confirmed the same terminal roster
across four paired reads spanning 4.7 seconds. During the run, one core briefly
reported zero players while its peer still showed one; the runner logged
`terminal_waiting_for_peer` and continued until the linked views agreed. This
is why the terminal check requires both settled maps instead of trusting a
single transient count.

The run used the separate Zephyrus ROM/save copies. Its match logs and PNG
observations remain under
`%LOCALAPPDATA%\FE7-Link-Arena\20260928T153714Z-75c7b5`. It used bridge ports
18942/18943 and API port 18716. The result screen is captured above;
point/rank extraction into a structured API record remains manual.

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
weapon. With this option, the policy score did not explicitly include a
defender-selected counterweapon; FE7 still resolved the real combat, hit RNG,
survival, points, and final rank. Representative decisions that reached
in-game forecasts included B Hector with Wolf Beil into A Oswin, A Canas with
Luna into B Hector, B Bartre with Basilikos into A Hector, A Canas with Luna
into B Oswin, and B Dorcas with Brave Bow into A Canas.

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
