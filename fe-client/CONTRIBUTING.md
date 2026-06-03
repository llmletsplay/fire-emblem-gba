# Contributing To fe-client

See the root `CONTRIBUTING.md` for the full project workflow. This file covers
frontend-specific expectations for the stream overlay.

## Setup

```bash
npm install
npm run dev
```

Run the backend separately when testing live WebSocket data:

```bash
python ../src/core/run.py --auto
```

## Guidelines

- Keep UI copy game-neutral unless the data or asset is specifically FE7 or FE8.
- Keep runtime state types in `src/types/*` aligned with backend WebSocket
  payloads.
- Prefer reusable unit-display components under `src/components/units/*`.
- Treat `../assets/shared` as the canonical source for shared assets.

## Checks

```bash
npm run lint
npm run build
```
