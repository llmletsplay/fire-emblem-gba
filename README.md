# Fire Emblem GBA AI Agent

An end-to-end harness for LLM-driven play in GBA Fire Emblem games. The project
connects mGBA, Lua memory readers, a Python decision loop, and React frontends so
an agent can observe tactical state, reason about a turn, issue controller
inputs, and stream what it is doing.

The harness supports:

- Fire Emblem 7: The Blazing Blade (`AE7E`)
- Fire Emblem 8: The Sacred Stones (`BE8E`)

FE8 has the richer bundled asset set. FE7 support is built into the memory
reader, game registry, lookup tables, chapter data, Lua reader, and tutorial
handling.

## What This Is

- A GBA Fire Emblem agent harness for emulator control, live memory reading, LLM
  prompting, semantic command execution, and stream telemetry.
- A portfolio-ready full-stack project: Python backend, mGBA Lua socket bridge,
  React stream overlay, and public documentation site.
- A research playground for tactical decision loops in grid-based strategy games.

## What This Is Not

- It does not include ROMs, saves, model checkpoints, or API keys.
- It is not an emulator. It launches and controls mGBA through Lua scripting.
- It is not affiliated with Nintendo or Intelligent Systems.

## Harness Flow

1. mGBA runs the configured FE7 or FE8 ROM with `lua/socketserver.lua`.
2. The Lua socket server exposes screenshot capture, button input, savestate,
   and raw memory reads.
3. `src/data/game_registry.py` identifies the ROM code and selects FE7 or FE8
   addresses.
4. `src/utils/memory_reader.py` reads phase, turn, cursor, unit arrays, terrain,
   UI state, and game-specific fields.
5. `src/game/fe_state.py` converts memory into JSON context for the LLM.
6. `src/core/llmdriver.py` sends context and screenshots to the configured model.
7. `src/game/command_parser.py`, `command_validator.py`, and
   `command_executor.py` translate semantic commands into deterministic button
   input.
8. `src/services/websocket_service.py` streams telemetry to `fe-client`.

## Prerequisites

- Python 3.10+
- Node.js 18+
- mGBA with Lua scripting support
- A legally obtained FE7 or FE8 GBA ROM
- An API key or local endpoint for your chosen LLM provider

## Quick Start

```bash
git clone https://github.com/llmletsplay/fire-emblem-gba.git
cd fire-emblem-gba
pip install -r requirements.txt
cd fe-client && npm install && cd ..
cp .env.example .env
```

Place your ROM in `roms/`:

```bash
cp /path/to/FE7.gba roms/
```

Configure `.env`:

```dotenv
FE_GAME=fe7
ROM_FILE=FE7.gba
LLM_PROVIDER=CUSTOM
CUSTOM_BASE_URL=http://localhost:8080/v1
CUSTOM_MODEL=gpt-4o-mini
```

Then start the stack:

```bash
npm start
```

This starts:

- React stream overlay: `http://localhost:5173`
- WebSocket telemetry: `ws://localhost:8765`
- mGBA Lua socket server: `localhost:8888`
- Python agent loop: `python src/core/run.py --auto`

## Game Selection

Use `ROM_FILE` and `FE_GAME` in `.env`.

```dotenv
# FE7
FE_GAME=fe7
ROM_FILE=FE7.gba

# FE8
FE_GAME=fe8
ROM_FILE=FE8.gba
```

`FE_GAME` can be omitted when the ROM filename is clear, but setting it is
recommended. The runtime also reads the ROM header to verify the active game.


## Tutorial mode / Ch0

FE7 Lyn Mode Prologue (Ch0) is **live-verified**. The autonomous harness hard-prefers
`tutorial_sequence` destinations from `src/data/fe7_chapters.py` and will soft-reject
wrong MOVE tiles the same way the game does.

Verified end-to-end path (see [`docs/fe7-ch0-tutorial-verified.md`](docs/fe7-ch0-tutorial-verified.md)):

1. Load **savestate slot 1** (clean start, Lyn@(13,7)) — `FE_LOAD_SAVESTATE=true`, `FE_SAVESTATE_SLOT=1`
2. MOVE (8,7) → WAIT (brigand → (7,6))
3. MOVE+ATTACK (8,6)
4. MOVE (5,4) → ITEM vulnerary (HP 6→16; mash A through dialogue, do **not** trust `game_state_bits==0`)
5. MOVE+ATTACK (4,2) vs Batta@(3,2) → SEIZE (3,2)

Ch1–10 `tutorial_sequence` entries are **UNVERIFIED placeholders** (empty until live-probed). Keep `FE_TUTORIAL=true` for Lyn Mode; set `FE_TUTORIAL=false` for Eliwood Mode Ch11+.

## Useful Commands

```bash
# Full stack
npm start

# Backend only
python src/core/run.py --auto

# Interactive emulator console
python src/core/run.py

# Stream overlay only
cd fe-client && npm run dev

# Public website only
cd fe-web && npm run dev

# Launch mGBA socket server only
./scripts/run_mgba.sh
```

## Project Structure

```text
fe-gba/
├── src/
│   ├── core/          # Runtime entrypoint and LLM loop
│   ├── data/          # FE7/FE8 lookup tables, chapters, registry
│   ├── game/          # State shaping and command execution
│   ├── llm/           # Provider setup, prompts, compaction, vision helpers
│   ├── services/      # WebSocket, benchmark, interactive services
│   └── utils/         # Memory reader, image capture, sessions, helpers
├── lua/               # mGBA Lua socket and FE7/FE8 memory helpers
├── fe-client/         # React stream overlay / dashboard
├── fe-web/            # React public project site
├── assets/shared/     # Canonical shared FE assets for frontend copies
├── docs/              # Memory maps and architecture documentation
├── tools/             # Memory probes and setup utilities
└── roms/              # Local ROMs and saves, ignored by Git
```

## Supported Providers

The runtime supports OpenAI-compatible clients and direct adapters for common
providers:

- `OPENAI`
- `ANTHROPIC`
- `GEMINI`
- `OLLAMA`
- `LMSTUDIO`
- `GROQ`
- `TOGETHER`
- `GROK`
- `CUSTOM`
- `ZAI`

Configure provider-specific keys and model names in `.env`.

## Verification

Run checks serially so heavy verification does not stack:

```bash
python -m pytest
cd fe-client && npm run lint && npm run build
cd ../fe-web && npm run lint && npm run build
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Memory system guide](docs/MEMORY_SYSTEM_GUIDE.md)
- [FE7/FE8 data coverage](docs/FE7_FE8_DATA_COVERAGE.md)
- [FE7 memory map](docs/FE7_MEMORY_MAP.md)
- [FE8 memory map](docs/FE8_MEMORY_MAP.md)

## Legal Note

Only use ROMs and saves you have a legal right to use. Do not commit or share
ROMs, saves, API keys, private logs, or generated runtime artifacts.

This project is not affiliated with, endorsed by, or sponsored by Nintendo or
Intelligent Systems. Fire Emblem, The Blazing Blade, and The Sacred Stones are
trademarks of their respective owners.
