# Fire Emblem Versus model tournaments

The standalone repository is currently private: cloning the submodule requires GitHub access to `thomasjvu/fire-emblem-versus`. The public main repo does not grant that access automatically.

The standalone FE8 ROM hack is a pinned Git submodule at `vendor/fire-emblem-versus`. The campaign runner and old FE7 Link Arena runner remain separate. This tournament runner uses the hack's two linked mGBA cores, native legal-action catalog and confirmed outcomes.

## Setup

```sh
git submodule update --init --recursive
python3 vendor/fire-emblem-versus/tools/manage.py bootstrap --base /absolute/path/to/fe8-usa.gba --with-tests
```

Use your own FE8 USA ROM (SHA-1 `c25b145e37456171ada4b0d440bf88a19f4d509f`). Requirements and build instructions are in the submodule README. Baseline build needs Git, Make, a host C compiler, GNU Arm tools, libpng, Python NumPy and Pillow; agent play builds the pinned mGBA library. No physical cable is needed. The ROM hack currently supplies eight maps, eighteen preset parties and level-20 units.

To reuse an already built standalone checkout, pass `--engine-root /absolute/path/to/fire-emblem-versus/decomp`. Its catalog, source and ROM manifest must agree; the session validates them. The normal default is the submodule's `decomp` directory.

## Configure entrants

Copy `examples/versus-models.json` to a local file and replace each placeholder with an exact provider model ID. Add as many entrants as desired. Entrant IDs must be unique; multiple entrants may use the same model with different reasoning settings. Set credentials in your shell without putting them in JSON or Git:

```sh
export CHUTES_API_KEY='your-key'
export MINIMAX_API_KEY='your-key'
```

Each entrant has `id`, `provider` (`chutes`, `minimax-api`, or `local`) and, for hosted models, `model`. Optional settings are `base_url`, `api_key_env`, `timeout_seconds`, `temperature`, `max_completion_tokens`, `minimax_thinking`, and `minimax_reasoning_effort`. The existing project's provider endpoint defaults are reused; MiniMax reasoning settings are validated without network calls during configuration. MiniMax M3.1 requires an explicit reasoning effort. A `local` entrant is a deterministic tactical baseline, not a hosted MiniMax model and not an exact minimax combat solver. The old FE7 minimax policy cannot directly control this FE8 game mode.

Chutes uses the [OpenAI-compatible chat endpoint](https://chutes.ai/agents/connect). MiniMax uses its [OpenAI-compatible endpoint](https://platform.minimax.io/docs/api-reference/text-openai-api); reasoning output is separated and only the final action JSON is consumed. Each decision receives native units, terrain, objectives and every ROM-generated legal action. The model must return exactly `action_id` and a short public `rationale`. Invalid output or provider failure stops the tournament; there is no silent baseline substitution or artificial match loss.

## Run and stream

```sh
# Inspect the complete schedule without ROM execution or provider calls.
python3 tools/versus_tournament.py examples/versus-models.json --plan

# Test the complete emulator path without paid model calls.
python3 tools/versus_tournament.py examples/versus-local.json --output runtime/versus-local

# Run hosted models using your edited config.
python3 tools/versus_tournament.py /absolute/path/to/tournament.json --output runtime/versus-models --port 8770
```

Add `http://127.0.0.1:8770/` as an OBS Browser Source, width **1920**, height **1080**. The source displays actual 240×160 mGBA video, enlarged with crisp nearest-neighbor pixels, inside an imagegen-created fantasy broadcast frame, alongside entrant/preset labels, current phase, public rationale, standings and last result. Native video is exported independently of action confirmation so movement and combat remain visible while commands resolve. The browser polls at up to 10 fps; native audio is not currently exported. Both emulator feeds are available at `/video/0.png` and `/video/1.png`; the main layout shows the blue core. The `/state` endpoint is read-only and excludes seat credentials and API keys. No OBS or broadcast service is automatically started. The HTTP server binds to loopback; use OBS on the same machine. Leave the runner open after completion to keep final standings visible, or pass `--exit-on-complete` for batch runs.

Each pair plays four games per scenario and repetition: both seat assignments crossed with both opening armies. Parties follow their assigned entrant when seats swap. To compare models on equal rosters, select identical parties. All models receive the same public observation schema and legal actions. Games use the ROM's deterministic initial state/RNG; repetitions repeat that setup, not randomized seed samples. Wins score 3 points, draws 1, losses 0. Score order ties are displayed alphabetically rather than pretending to establish a tiebreak winner.

Native elimination, explicit castle seizure, surrender and the native 30-round draw determine results. An emulator/provider failure or host action limit is an incomplete game, not a scored draw or forfeit. The runner stops and preserves evidence. Restart with the same config, ROM and output directory: completed results are skipped; the incomplete game restarts in a fresh session. Changed config or ROM requires a new directory. A process lock prevents two CLI runners writing the same tournament concurrently.

`runtime/<tournament>/results.json` is the durable score ledger. `stream-state.json` is the current dashboard snapshot. Each game has native events plus `decisions.jsonl` with entrant, public decision, requested/resolved model, token usage, latency and prompt fingerprint. Credential values and hidden reasoning are not written by the tournament adapter. Runtime output is ignored by Git.

## Validation

```sh
python3 -m unittest tests.test_versus_tournament -v
node --check src/versus/overlay/overlay.js
```

Tests cover balanced seats/openers/preset assignment, native outcome scoring, provider request formats through a local mock API, illegal-output rejection, credential exclusion, failure handling, resume identity and the read-only stream route. The local four-game smoke tournament exercises two real linked cores per match. Hosted-provider play needs exact model IDs and available credentials; a mock API test is not a claim that paid hosted models were exercised.

The broadcast uses bundled Poltawski Nowy and Epilogue fonts (SIL OFL), a restrained anime background, and a CSS frame aligned to native 3:2 game video. The ROM uses quiet outdoor terrain tiles and restores battle UI graphics after the lobby transition.
