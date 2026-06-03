# Contributing

This project builds an AI agent harness for FE7 and FE8 on mGBA. Contributions
are welcome across Python runtime code, memory maps, frontend telemetry, docs,
and tooling.

## Prerequisites

- Python 3.10+
- Node.js 18+
- mGBA with Lua scripting support
- `.env` created from `.env.example`
- A legally obtained FE7 or FE8 ROM placed in `roms/`

## Getting Started

```bash
pip install -r requirements.txt
cd fe-client && npm install && cd ..
cp .env.example .env
```

Configure game selection in `.env`:

```dotenv
FE_GAME=fe7
ROM_FILE=FE7.gba
```

Run the stack:

```bash
npm start
```

Useful focused commands:

```bash
python src/core/run.py --auto
python src/core/run.py
cd fe-client && npm run dev
cd fe-web && npm run dev
```

## Development Workflow

- Keep PRs focused and explain behavioral changes.
- Prefer existing module boundaries over broad refactors.
- Keep FE7 and FE8 behavior explicit when changing memory addresses, lookup
  tables, prompts, or command execution.
- Do not commit ROMs, saves, screenshots, logs, local `.env` files, or generated
  runtime artifacts.

## Checks

Run heavy checks one at a time:

```bash
python -m pytest
cd fe-client && npm run lint && npm run build
cd ../fe-web && npm run lint && npm run build
```

For memory-map changes, also run the relevant `tools/memory_probe.py` command
against a live mGBA session and include the observed ROM/game/chapter context in
the PR.

## Pull Requests

- Describe the user-visible behavior and the harness surface affected.
- Mention whether the change impacts FE7, FE8, or both.
- Attach screenshots only when they are needed to explain a frontend change; do
  not commit generated screenshots.
- Update docs when behavior, setup, or supported memory fields change.
