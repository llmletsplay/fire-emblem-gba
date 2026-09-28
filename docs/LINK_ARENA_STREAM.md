# FE7 Link Arena stream screen

The Link Arena runner serves a 1920×1080 stream screen from its local API.
It combines the FE7 battle view, 1P/2P team status, turn and active phase,
match timer, verified inputs, minimax exchanges, recent agent choices, and a
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
use the same `-TwitchChannel` option. The local URL follows this shape:

```text
http://127.0.0.1:18700/stream?channel=llmletsplay
```

The API port changes if the runner uses a non-default `-ApiPort`; use the URL
printed by that runner. Open it in OBS on the same computer as mGBA. The API
binds to `127.0.0.1`; keep it local and do not forward the port to the internet.

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

- **Turn / phase** comes from FE7's live turn and phase bytes. The player phase
  is labeled 1P; the NPC phase is labeled 2P.
- **Standing / HP / KO** are derived from the FE7 player and NPC rosters. KO
  count is total roster size minus surviving units.
- **Verified inputs** counts completed controller button pulses recorded by
  the runner. **Exchanges** counts completed minimax matchup submissions.
- **Last eval** is the minimax policy's estimated matchup value. It is not a
  game score, damage total, or win probability.
- **Recent exchanges** shows each agent's selected attacker, defender, weapon,
  and policy estimate. Unit IDs are shown because the Link Arena memory bridge
  does not yet expose localized character names.
- **Match winner** appears when unattended play reaches the runner's verified
  synchronized terminal state. The runner does not yet read FE7's final points
  table into a live score. The overlay therefore shows KOs and roster/HP
  metrics rather than inventing a point score.
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
