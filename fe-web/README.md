# fe-web

React + Vite public website for the Fire Emblem GBA agent project.

## Role

`fe-web` is the portfolio/public-facing surface. It explains the FE7+FE8 harness,
shows benchmarks and docs, and hosts FE8-specific downloadable asset bundles
where applicable.

It is separate from `fe-client`, which is the live stream overlay connected to
runtime WebSocket telemetry.

## Development

```bash
npm install
npm run dev
```

## Checks

```bash
npm run lint
npm run build
```

## Assets

`../assets/shared` is the canonical source for shared project assets. Files in
`public/` are app-facing copies or distributable bundles.
