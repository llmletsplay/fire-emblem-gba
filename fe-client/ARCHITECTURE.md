# fe-client Architecture

`fe-client` is the live overlay/dashboard for the Fire Emblem GBA agent harness.

## Data Source

The app expects runtime telemetry from the Python backend WebSocket server:

```text
ws://localhost:8765
```

The backend emits game state, unit data, current model output, action history,
chronicle entries, and session counters.

## Component Shape

- `src/components/layout/*` renders the stream overlay frame.
- `src/components/game-display/*` renders the current game screen and tactical
  status.
- `src/components/units/*` renders unit cards, portraits, class sprites, and HP.
- `src/components/thought-log/*` renders model reasoning and action history.
- `src/types/*` contains runtime state and WebSocket payload types.

## Game Scope

The backend can report FE7 or FE8. UI copy should avoid assuming FE8 unless the
specific asset or chapter data is FE8-only.

## Assets

Public assets are app-facing copies. `../assets/shared` remains the canonical
source for shared fonts, maps, logos, sprites, portraits, and box art.

## Checks

```bash
npm run lint
npm run build
```
