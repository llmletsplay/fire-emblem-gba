# Fire Emblem Versus in OBS

Start a native emulator tournament from the project directory:

```sh
python tools/versus_tournament.py examples/versus-maps.json --output runtime/versus-maps
```

A built standalone checkout can be selected with `--engine-root /absolute/path/to/fire-emblem-versus/decomp`. Keep each tournament's output directory: it stores resumable results and match evidence. Use a new output directory for a fresh tournament. Keep the runner open after completion to display final standings.

## Scene setup

Create an OBS scene named **Versus — Match**. Add a Browser Source named **Fire Emblem Versus** with the following settings. The reusable [source settings](../examples/obs/versus-browser-source.json) are a configuration reference, not an importable scene collection.

| Setting | Value |
| --- | --- |
| URL | `http://127.0.0.1:8770/` |
| Local file | Off |
| Width / height | 1920 / 1080 |
| Custom frame rate | On, 30 FPS |
| Custom CSS | Empty |
| Shutdown source when not visible | Off |
| Refresh browser source when scene becomes active | Off |

Set the OBS base canvas to 1920×1080. Reset the source transform and fit it to the canvas with no crop, then lock the source. The game is a native 240×160 frame displayed at exactly 5× inside the canvas. Smaller previews letterbox the entire scene without stretching it. Keep scene switching from resetting the browser so decisions remain visible.

The property names and behavior are documented in the [official OBS Browser Source guide](https://obsproject.com/kb/browser-source).

## Before going live

Check that both army names and presets fit, the active army is highlighted, the objective and round are visible, and the game animates independently of model decisions. Blue and Red summaries show public rationales only. For hosted models, configure the provider examples and credentials in the runner environment; no credentials belong in OBS.

Record a short local test before starting the broadcast. Check the resulting recording for sharp game pixels, legible text and complete scene edges. The browser video is sampled at up to 10 FPS; setting OBS to 30 FPS does not create extra game frames. Native audio is not exported. Add commentary or music as separate OBS audio sources if wanted.

## Recovery

If the stream reports disconnected, verify that the runner is still listening on the selected port. Start it again with the same configuration/output to resume durable results. The browser retries automatically. If assets changed during development, use **Refresh cache of current page** in the source properties. When changing the port, update the source URL too.

OBS and the runner must be on the same machine because the server binds to loopback. End the broadcast before closing the runner. Source refresh/reload is read-only and does not submit gameplay actions.

The standings rotate through groups of four entrants every ten seconds. Public decisions show up to four lines so longer model output cannot displace the match panel; hover in the browser to read the full rationale, or inspect the tournament decision logs. Run `node tests/versus/overlay-state.test.cjs` to check waiting/thinking/completed/draw states and twelve-entrant pagination.
