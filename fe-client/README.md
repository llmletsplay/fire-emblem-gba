# fe-client

React + Vite stream overlay and live dashboard for the Fire Emblem GBA agent.

## Role

`fe-client` is the operational frontend. It connects to the backend WebSocket
server, renders the current FE7/FE8 game state, shows model thoughts/actions,
and provides a stream-friendly overlay layout.

## Development

```bash
npm install
npm run dev
```

The backend broadcasts on `ws://localhost:8765` by default.

## Checks

```bash
npm run lint
npm run build
```

## Assets

Runtime frontend assets are copied into `public/`, but `../assets/shared` is the
canonical source for shared sprites, maps, logos, and fonts.
