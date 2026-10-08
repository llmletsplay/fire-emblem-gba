# Fire Emblem Versus in OBS

The game runs in the **Fire Emblem Versus — Native mGBA** window. OBS captures that window and its audio directly. The default runner starts no web server and exports no screenshot files. Human players use the keyboard/controller in the emulator; agents control the same running ROM. See [play modes and controls](VERSUS_PLAY.md).

## Start the native game

Build the native frontend once with `python3 vendor/fire-emblem-versus/tools/manage.py desktop` after bootstrapping the ROM and pinned mGBA library. Then run from the project directory:

```sh
python3 tools/versus_tournament.py examples/versus-human-agent.json --output runtime/human-agent
# Or examples/versus-human-human.json, versus-local.json, or your hosted-model config.
```

Use `--engine-root /absolute/path/to/fire-emblem-versus/decomp` for another built checkout. Keep the terminal process running. Focus the native window to play; do not launch a second stock emulator expecting it to attach to this match.

## Direct capture

Create an OBS scene named **Versus — Native**. Add a capture source for **Fire Emblem Versus — Native mGBA**. On macOS use **macOS Screen Capture**, choosing the native application or window; on macOS 13+ that source can also capture audio ([official OBS guide](https://obsproject.com/kb/macos-screen-capture-source)). For other platforms use the supported native window/application capture source. This frontend build is currently verified on macOS; Linux is unverified and Windows desktop compilation is not supported by its build script.

Capture the game client area. Crop the title bar or any letterbox margins before scaling. The ROM frame is 240×160 at a 3:2 ratio, with integer nearest-neighbor scaling in the native window. The frontend paces both cores at approximately 59.73 FPS; use a 60 FPS OBS capture when desired. This is a presentation target, not a measured dropped-frame/latency guarantee. Use OBS Point scaling for the source to retain sharp pixels.

Native audio plays from the Blue core using mGBA’s SDL audio/resampler backend. Capture that application audio once; avoid adding a duplicate desktop-audio source. If an audio device fails, the game continues and `emulator.log` records the failure. Make a short local recording to verify audio and sync before streaming.

Normal native tournaments retain the same process and window across games, while resetting the two cores and assigning a fresh match identity. OBS keeps its capture target across map/seat changes. Test capture once before an unattended tournament. Legacy browser-video mode creates separate windows and may require reselecting a capture source. The final result window remains open until the next game, window close or runner shutdown. Reopening a completed output directory restores the score ledger, not a live emulator results window; start a fresh output directory for a playable rematch.

## Optional scores and decision overlay

To add standings, player labels and public decisions above the direct native capture:

```sh
python3 tools/versus_tournament.py examples/versus-local.json --output runtime/obs-native --overlay
```

Add a Browser Source **Versus information** using `http://127.0.0.1:8770/?overlay=1`, width **1920**, height **1080**, custom FPS **30**, empty custom CSS, shutdown when hidden **off**, refresh when active **off**. This layer has a transparent game area and does not request game screenshots. Only public tournament state is polled. No provider secrets belong in OBS. See [source settings](../examples/obs/versus-browser-source.json) and [native scene layout reference](../examples/obs/versus-native-layout.json); these are configuration references, not importable OBS scene collections.

Use a 1920×1080 OBS canvas. Layer order, bottom to top:

1. Background: a dark navy Color Source (`#101a2a`) or your chosen static art.
2. Native game capture: crop to the game client, set position **x=56, y=196**, size **1200×800** (5× native pixels), Point scaling, lock it.
3. Optional transparent information Browser Source: full canvas, position **0,0**, no crop, lock it.

The information layer uses bundled monospace typography, navy/gold framing and separate Blue/Red decision cards. The active army is highlighted; human turns show **YOUR TURN** and model turns **THINKING**. Standings rotate groups of four entrants every ten seconds. Decisions display four lines, with full public rationale available by hover in a browser or in the logs.

The small loopback server is optional and outside the native video/input/audio path. Its overhead has not been benchmarked; disabling the layer does not change gameplay. For no server at all, omit `--overlay` and use direct capture plus OBS text/image sources. Durable results and `stream-state.json` are still written to the output directory.

## Recovery and legacy mode

If the native window closes during a game, the incomplete match is not scored. Restart with the same config/ROM/output to restart that game and retain completed results. Changed config or ROM requires a new output directory. Ctrl-C ends the runner. If optional overlay assets changed, refresh the Browser Source cache. Update the source URL if using another `--port`.

`--headless` is for agent batches with no window. `--terminal-human` explicitly enables the old action selector. `--browser-video` enables the old PPM→PNG screenshot server and full browser scene, with video sampled at up to ten FPS and no browser audio. Those options exist for compatibility; use native capture for normal play and streaming.

## Verified scope

The desktop linked-core regression passed native controls, cancellation, Blue/Red movement/Wait, End, agent handoff, surrender and matching peer hashes. Visible macOS keyboard selection, Wait and End were checked; the local agent played Red and returned control to Blue. Main-project tests check native human dispatch, final-window retention, cleanup and overlay states. No actual OBS recording, physical controller session or paid hosted-provider run is claimed. Recording preflight remains required before broadcast.

See [native frontend evidence](evidence/versus-native-frontend.json) and [the native window screenshot](evidence/versus-native-keyboard.png).
