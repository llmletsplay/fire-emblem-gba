# FE7 Link Arena stream screen

The Link Arena runner serves a 1920×1080 stream screen from its local API.
It combines the FE7 battle view, 1P/2P team status, turn and active phase,
match timer, verified inputs, policy exchanges, recent agent choices, and a
reserved Twitch chat panel. The stream page reads a separate token-free,
read-only endpoint; it does not use either agent's bearer token.

## Start a match with a Twitch channel

On Zephyrus, start the isolated runner as usual. The launcher defaults to the
`llmletsplay` Twitch channel and prints the exact overlay URL after it starts.
Pass `-TwitchChannel otherhandle` to override it:

```powershell
& "$env:LOCALAPPDATA\FE7-Link-Arena\runner\scripts\windows\Start-Link-Arena.ps1" `
  -RepoRoot "$env:LOCALAPPDATA\FE7-Link-Arena\runner" `
  -Save "$env:LOCALAPPDATA\FE7-Link-Arena\runner\roms\fe7.sav" `
  -AutoMinimax
```

The same stream screen works for a supervised match; omit `-AutoMinimax` and
use the same `-TwitchChannel` option. To run an autonomous series, add
`-AutoMinimax -Continuous`; the match runner reloads fresh copies of the
prepared save between verified wins and records a persistent series W–L–D
score. Hosted Chutes/MiniMax policies can be supplied with `-AgentA` or
`-AgentB` plus the matching `-ModelA`/`-ModelB`; the runner starts them only
when the corresponding API key is available. The scheduled task supports the
same provider/model and per-policy-slot MiniMax reasoning settings. Use the encrypted
credential prompt documented in [`LINK_ARENA.md`](LINK_ARENA.md#stage-and-start-on-zephyrus)
to make those keys available to unattended runs. See
[`LINK_ARENA.md`](LINK_ARENA.md#stage-and-start-on-zephyrus) for examples. The
local URL follows this shape:

```text
http://127.0.0.1:18700/stream?channel=llmletsplay
```

The API port changes if the runner uses a non-default `-ApiPort`; use the URL
printed by that runner. Open it in OBS on the same computer as mGBA. The API
binds to `127.0.0.1`; keep it local and do not forward the port to the internet.

## Ready-made OBS scene collection

The repository includes [FE7 Link Arena.json](../assets/obs/FE7%20Link%20Arena.json),
a 1920×1080 OBS scene collection with a full-screen Link Arena Browser Source
and a separate Twitch chat Browser Source. Copy it to
`%APPDATA%\obs-studio\basic\scenes\FE7 Link Arena.json` while OBS is closed.
On the next launch, select **FE7 Link Arena** from OBS's Scene Collection menu.
The screen source uses screenshot preview mode, so it displays both linked FE7
views and live metrics as soon as the runner starts. The chat source is placed
over the overlay's chat panel. Its source URL and placement are already set for
`@llmletsplay`.

## Keep the stream running on Zephyrus

After deploying the isolated runner files, install the interactive logon tasks
for the streaming Windows user:

```powershell
& "$env:LOCALAPPDATA\FE7-Link-Arena\runner\scripts\windows\Install-Link-Arena-Stream.ps1" `
  -RunnerRoot "$env:LOCALAPPDATA\FE7-Link-Arena\runner" `
  -Save "$env:LOCALAPPDATA\FE7-Link-Arena\runner\roms\fe7.sav" `
  -TwitchChannel llmletsplay -RestartNow
```

`-RestartNow` replaces the current isolated match and starts the configured
continuous policy series and OBS watchdog immediately (local minimax on both
seats by default). An incomplete match is retained in its match data folder
but is not added to the series score. Both tasks are
interactive logon tasks with no 12-hour execution limit. Leave the Zephyrus
streaming user signed in and keep Windows awake.
Zephyrus AC sleep and hibernate timeouts are set to **Never** so the logon
tasks and stream do not pause when the display is idle.

The scheduled installer defaults to the local minimax-vs-minimax stream. It
can instead be installed with fixed hosted policies. Save credentials once as
the streaming Windows user, then install the chosen seats/models with a
separate data directory for that experimental condition. The following IDs
are illustrative current provider choices, not a frozen confirmatory
protocol:

```powershell
$runner = "$env:LOCALAPPDATA\FE7-Link-Arena\runner"
$experiment = "$env:LOCALAPPDATA\FE7-Link-Arena\experiments\glm51-vs-minimax-m31-low"
& "$runner\scripts\windows\Install-Link-Arena-Stream.ps1" `
  -RunnerRoot $runner `
  -Save "$runner\roms\fe7.sav" `
  -DataDir $experiment `
  -AgentA chutes -ModelA 'zai-org/GLM-5.1-TEE' `
  -AgentB minimax-api -ModelB 'MiniMax-M3.1-Flash-Preview' `
  -MinimaxThinkingB adaptive -MinimaxReasoningEffortB low `
  -AlternateAgentSeats -SeatOrderSeed 20260928 `
  -TwitchChannel llmletsplay
```

`-AlternateAgentSeats` makes policy slots A and B swap runner seats across
successive verified matches, in two-match blocks. The seeded first orientation
and exact slot assignment are written into each match's `session.json`, so the
schedule survives a runner restart. Use one dedicated experiment data directory
per frozen provider/model pairing and seed. This balances seat allocation but
does not reset or pair FE7 combat RNG; analyses must treat RNG as a remaining
source of variation and report incomplete matches separately.

Installing without `-RestartNow` updates task registration but leaves running
processes alone; the new policy takes effect at the next task start/logon. A
provider switch in the current stream still requires a controlled
between-match handoff. `-RestartNow` stops mGBA and OBS immediately, so use it
only at a verified safe boundary. Hosted calls use the selected provider
account's quota or balance; confirm model access and budget before a pilot.
The default public stream remains local minimax until its task is
intentionally reconfigured.

The runner writes process output to `stream-runner.log` and Python errors to
`stream-runner-errors.log` in `%LOCALAPPDATA%\FE7-Link-Arena`.

The OBS watchdog opens the **FE7 Link Arena** collection and scene in normal
mode, minimizes OBS to the tray, and starts the saved Twitch output. OBS 32's
Safe Mode prompt is triggered by an unclean-shutdown marker; for unattended
stream recovery, the watchdog archives that marker under
`%LOCALAPPDATA%\FE7-Link-Arena\obs-recovery` before relaunching. It records each
recovery and exit in `obs-startup.log`, then retries with backoff. This keeps a
recovery dialog from taking the stream offline; inspect the archived marker
and the latest OBS log after an unexpected restart.

## OBS scene

Set the OBS canvas to **1920×1080**. Add the sources in this order, from bottom
to top:

1. **mGBA capture** — add a Game Capture or Window Capture for the linked FE7
   session. Fit/crop the game image into the large left-hand gameplay frame.
   This is the full-motion path for smooth battle animations.
2. **Link Arena overlay** — add a Browser Source using the printed URL with
   `&capture=obs` added, for example
   `http://127.0.0.1:18700/stream?channel=llmletsplay&capture=obs`. Set its
   dimensions to 1920×1080. The overlay is transparent over the gameplay
   frame and draws the FE7 sword header, team trim, live metrics, lower third,
   and chat frame.
3. **Twitch chat** — on a local HTTP overlay, add a second Browser Source using
   `https://www.twitch.tv/popout/llmletsplay/chat?popout=`. Size it to about
   **447×550** and place it inside the right-hand LIVE CHAT frame (at the
   default 1920×1080 canvas, approximately x=1448, y=143). Keep it above the
   Link Arena overlay so its chat messages cover the setup prompt in that
   frame. The launcher uses `llmletsplay` unless overridden with
   `-TwitchChannel`.

For a quick preview without setting up a game capture, omit `&capture=obs`.
The page then displays the linked 1P and 2P bridge screenshots side by side.
This fallback updates four times per second; use mGBA capture sources for
full-motion combat animations.

Twitch's embedded chat requires a secure parent domain and a matching
`parent` parameter. The runner is intentionally loopback HTTP, so the direct
Twitch popout Browser Source above is the local OBS setup. If the overlay is
hosted on a compliant HTTPS domain instead, its chat panel can use Twitch's
chat embed with that exact domain as `parent` ([Twitch embed requirements and
chat URL](https://dev.twitch.tv/docs/embed/chat/)).

## What the live metrics mean

- **Turn / phase** labels the player phase 1P and the NPC phase 2P. When FE7's
  chapter-65 turn field is zero or unavailable, the overlay shows a benchmark
  round based on paired 1P/2P exchanges; it is not presented as FE7's internal
  turn byte.
- **Standing / HP / KO** are derived from the FE7 player and NPC rosters. KO
  count is total roster size minus surviving units.
- **Verified inputs** counts completed controller button pulses recorded by
  the runner. **Exchanges** counts completed policy matchup submissions.
- **Last eval** is the minimax policy's estimated matchup value when that
  policy is in use. Hosted models have no comparable evaluation unless their
  action contract is extended; blank values are not zero scores.
- **Recent exchanges** shows each agent's selected attacker, defender, weapon,
  policy/model label, brief user-visible rationale when supplied, and minimax
  estimate when available. It does not display provider-private reasoning.
  Unit IDs are shown because the Link Arena memory bridge does not yet expose
  localized character names.
- **Series record** shows 1P and 2P wins, draws, games played, latest results,
  and cumulative FE7 points from verified result screens. Outcomes and score
  evidence are appended to `series/results.jsonl`, so they survive restarts.
  Scores remain blank when either linked result is missing, disagreeing, or
  unrecognized; blank is not zero. FE7 point totals remain distinct from the
  W–L–D record and minimax evaluation.
- **Decision history** is persisted in `series/decisions.jsonl`. Policy choices
  include each side's structured observation and input hash; hosted choices
  also retain the exact structured prompt input, validated visible completion,
  rationale, request/model metadata, usage, and latency. Verified button
  presses, replans, and interrupted decisions link to the choice by ID. Hidden
  chain-of-thought and provider-only reasoning fields are not collected. Older
  per-match logs are imported on runner startup. The benchmark draft explains
  what this trace can and cannot establish.
- **Match winner** appears when unattended play reaches the runner's verified
  synchronized terminal state. Minimax evaluation remains a policy estimate,
  never a game score.
- **Arena state / data health** reports setup, active play, supervision needed,
  and linked-core coherence. A supervision stop appears as a visible warning.

The page polls match telemetry once per second and screenshots four times per
second. In `capture=obs` mode, it skips screenshot polling, so OBS handles the
smooth game picture while the API only supplies state and metrics. Screenshot
requests are read-only; they never advance the emulator or consume an agent
observation.

## Runner telemetry endpoint

`GET /v1/stream` returns the stream snapshot without authentication because the
server only binds to loopback. `GET /v1/stream?frame=0` skips PNG capture for
OBS capture mode; `GET /v1/stream/frames` returns the paired 1P/2P screenshots.
The snapshot contains `match`, `game`, `teams`, and `metrics` objects. It omits
session tokens, raw bridge responses, and agent credentials.

The static screen is served at `/stream`, `/stream.css`, and `/stream.js` by the
same runner process. The Windows deploy script copies these assets into the
isolated Zephyrus runner alongside its Python modules.

With `-Continuous`, the HTTP server stays up while the finished mGBA process
closes and the next isolated match initializes. During that short setup window,
the overlay holds the final frame and series result, then reconnects to the new
match telemetry without OBS source changes.
