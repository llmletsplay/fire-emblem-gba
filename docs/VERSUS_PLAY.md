# Playing Fire Emblem Versus

All three modes run the real FE8 ROM hack in two linked mGBA cores. The browser shows native emulator video; the ROM supplies legal actions and confirms outcomes. No physical cable is needed.

| Mode | Controllers | Starting example |
| --- | --- | --- |
| Human vs agent | One native keyboard/controller player and one local baseline or hosted model | `examples/versus-human-agent.json` |
| Agent vs agent | Two or more local baselines or hosted models | `examples/versus-local.json` / `examples/versus-models.json` |
| Human vs human | Two people sharing the native window, alternating turns | `examples/versus-human-human.json` |

Human play now uses normal Fire Emblem controls in the native emulator window. OBS captures that window directly. No web server starts by default. An optional transparent browser layer displays scores and decisions; it does not carry gameplay video. Remote matchmaking and separate remote human clients are not implemented. The legacy terminal selector remains available only with `--terminal-human`.

## Build once

From the `fe-gba` project directory, follow [the build and provider setup guide](VERSUS_TOURNAMENT.md). Initialize the submodule and bootstrap it with your own FE8 USA ROM:

```sh
git submodule update --init --recursive
python3 vendor/fire-emblem-versus/tools/manage.py bootstrap --base /absolute/path/to/fe8-usa.gba --with-tests
# Install SDL2 development headers and pkg-config, then:
python3 vendor/fire-emblem-versus/tools/manage.py desktop
```

On macOS the additional build dependencies are `brew install sdl2 pkg-config`. On Debian/Ubuntu use `libsdl2-dev` and `pkg-config`; Linux has not been verified. The desktop build targets POSIX hosts and does not currently support Windows.

The standalone submodule is private and requires repository access. If you already built a standalone checkout, append `--engine-root /absolute/path/to/fire-emblem-versus/decomp` to any play command below.

## Human vs agent

Start from a terminal. A **Fire Emblem Versus — Native mGBA** window opens; focus it and play there:

```sh
python3 tools/versus_tournament.py examples/versus-human-agent.json --output runtime/human-agent
```

The example puts you on Blue against a deterministic local baseline on Red. It needs no API key. To play a hosted model, copy the JSON to a local file and replace the second entrant with a configured `chutes` or `minimax-api` entrant from [the model guide](VERSUS_TOURNAMENT.md). Supply the exact model ID and credential environment variable; never put keys in the JSON. Run your copied file with a fresh output directory.

## Human vs human

```sh
python3 tools/versus_tournament.py examples/versus-human-human.json --output runtime/human-human
```

Player 1 is Blue and opens; Player 2 is Red. Share the native window and alternate keyboard/controller turns. The game phase identifies the current army; optional overlay nameplates identify the player. A phase can contain several unit actions before the other player takes over. Both players see the public battlefield; this is local hotseat play.

## Native keyboard and controller controls

Focus the emulator window before playing. Keyboard controls:

| Key | GBA control |
| --- | --- |
| Arrow keys | D-pad / cursor |
| X | A / select / confirm |
| Z | B / cancel |
| Enter | Start / minimap |
| Backspace | Select |
| Q | L / cycle units |
| W | R / unit information |
| Q + W + Backspace | Surrender during an idle phase |

Select a unit, choose a destination, then use the real action menu and combat forecast. A on an empty tile or a spent unit opens the map menu; choose End to finish the army phase. Movement previews and cancellation do not count as actions. Waiting at a castle does not capture it; choose Seize when available.

SDL controllers use A/B, D-pad or left stick, Start/Back and shoulders. One controller follows the active human; with two controllers, the first is Blue and the second Red (SDL connection order). Keyboard is shared. Inputs are accepted only on the active human army, so they cannot move agent units. Physical controller hardware has not been verified.

Closing the native window or pressing Ctrl-C stops the runner. This does not score a surrender. Native audio plays from one core to avoid doubling. The completed match stays on screen; use a fresh output directory to rematch, rather than the in-ROM result-menu buttons. The runner owns match setup and scoring.

## Agent vs agent

Local baseline smoke tournament:

```sh
python3 tools/versus_tournament.py examples/versus-local.json --output runtime/agent-agent
```

Hosted models: copy `examples/versus-models.json`, replace placeholders, set credentials as described in [the model guide](VERSUS_TOURNAMENT.md), then run:

```sh
python3 tools/versus_tournament.py /absolute/path/to/models.json --output runtime/models
```

The default round-robin format crosses both seat assignments and both opening armies: four games per pair, scenario and repetition. More than two models are supported. A `local` entrant is a baseline, not a hosted model. Each hosted agent receives structured public state and ROM-generated legal actions; it chooses action IDs rather than pressing gamepad buttons.

## Match settings and victory

Copy an example to change map, presets, objective or player names. Human examples use `"format": "single"`: exactly two entrants, one scenario and one repetition, one game, first entrant Blue, second Red, Blue opens. Swap entrant order to play Red. Remove `format` or use `"round-robin"` for the balanced tournament schedule; human players then participate in every scheduled game involving them.

The built `decomp/build/versus/catalog.json` lists valid map and party IDs. Current maps: `forest-forts`, `woodland`, `crossroads`, `open-field`, `twin-groves`, `central-keep`, `forest-ring`, `fort-race`. All eighteen presets have level-20 units with fixed stats. Presets and class matchups remain experimental; use equal parties for a symmetric roster comparison.

Objectives are `elimination`, `seizure` or `either`. Elimination disables capture. Seizure/Either permit an explicit Seize at the enemy castle gate. Losing all surviving units loses in every mode; surrender concedes. Mutual elimination or the native thirty-round limit draws. A runner error or host action limit is incomplete, not an automatic loss/draw.

Use a fresh output directory for a new match. Reusing a completed output displays its stored result; it does not start a rematch. Restarting an incomplete match with the same config and ROM restarts that game; completed tournament results are retained. Changed config/ROM requires a new directory. Leave the runner open after completion to keep the result visible, or use `--exit-on-complete` for batch runs. Only one runner can own an output directory. If port 8770 is occupied, add `--port 8771` and open that URL instead.

See [OBS setup](VERSUS_OBS.md) for direct capture and an optional information overlay. Play inside the native window; OBS displays and records it. Evidence lives in the output directory (`results.json`, per-game `events.jsonl` and `decisions.jsonl`). Native human actions record the confirmed sequence and a short public summary. The `native-ui` action ID is a host log marker, not a ROM legal-action ID. Native human events record the confirmed sequence/hash and observations show the resulting public state.

## Verification

`python3 -m unittest tests.test_versus_tournament -q` covers human input rejection, confirmation/cancellation, closed stdin and single-match scheduling, alongside the existing tournament checks. The standalone desktop regression exercised inactive-seat rejection, movement cancellation, both armies’ move/Wait, End, agent handoff, surrender and peer hashes through real linked cores. Visible macOS keyboard play also confirmed the movement/action menus, Wait and End; the local agent played Red and returned control to Blue. Actual OBS recording, physical controllers and paid hosted providers remain unverified.

## Legacy terminal controls

Add `--terminal-human` to use the old action selector. With `--headless --browser-video`, the legacy browser shows game screenshots at up to ten FPS. This is not the normal emulator play path. Each prompt uses the current ROM observation and lists twenty legal actions at a time.

| Input | Effect |
| --- | --- |
| `units` | Show unit IDs, positions, health and roster fields |
| `/attack`, `/seize`, `/heal`, `/wait`, `/end`, `/surrender` | Filter the current legal-action JSON by that text |
| `/text` | Search any text, including an actor ID or coordinate field |
| `next` | Show the next twenty filtered actions; wrap at the end |
| `all` | Clear the filter and return to the first page |
| Displayed number or exact action ID | Select that current legal action |
| `y` / `yes` at the confirmation prompt | Submit the selected action |
| Anything else at confirmation | Cancel selection and keep choosing |
| Ctrl-C | Stop the runner; does not score a surrender |

Action numbers retain their original indices when filtered. Coordinates are zero-based: x increases rightward and y downward. Blue deploys at the bottom, Red at the top. Use `actor`, `target`, `x` and `y` in the displayed JSON to distinguish destinations and targets. A legal `wait` moves to its destination and waits; `end` ends the whole army phase. Attack/heal destinations and target combinations are listed explicitly. `seize` is an explicit action: waiting on the enemy gate does not capture it. Confirm `surrender` only when you intend to concede. Search can return no matches when an action is unavailable.

The controller submits the chosen action through the same native command path as an agent. Closing stdin stops the game with an input error; launch human matches in a terminal that accepts keyboard input.

See [native frontend evidence](evidence/versus-native-frontend.json) and [the native window screenshot](evidence/versus-native-keyboard.png).
