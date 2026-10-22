# Browser runtime and direct native port

## Do players need mGBA installed?

No. The playable campaign and Versus sites run a bundled WebAssembly library inside the browser. Players install no emulator, browser extension, Node, Python or compiler. They also do not supply a ROM: the site includes its game data. mGBA currently provides the GBA CPU, graphics, audio and timing needed to preserve original FE8 behavior.

A direct engine port is a different architecture: compile the FE8 C gameplay code into WebAssembly and replace GBA-specific platform services with browser backends. This removes the emulator dependency, but is not achieved by putting a ROM in the website or compiling a few C files.

## Direct native target: development only

The standalone submodule now has a separate native target with no mGBA dependency, ARM interpreter or runtime ROM load:

```sh
npm run fe8:native:build
npm run fe8:native:test
```

These are developer commands requiring Emscripten, not player setup. The build prepares the pinned source checkout if missing. It compiles original RNG and process-scheduler C plus portable OAM/checksum/tilemap routines. Structure-layout assertions preserve the FE8 wasm32 ABI. The module manifest explicitly says `playable_campaign: false`; it is not the current campaign runtime.

Validated locally: scheduler blocking/sleep/callback order, native browser execution, 24 graphics/checksum cases and 512 RNG steps compared with original ARM routines. The test-only ARM reference uses Unicorn; it is not included in the browser runtime. A ROM-free CI job builds the native C and runs its scheduler/RNG tests.

The portable compilation audit currently accepts 346/359 C translation units. That count is neither linking success nor a gameplay-completion percentage. Remaining work includes compiler-specific C/assembly paths, asset/symbol relocation, video/audio backends, BIOS replacements, input/timing/saves and the complete game loop. The full native campaign is unfinished.

See [native build and differential checks](../vendor/fire-emblem-versus/native/README.md) and [architecture](../vendor/fire-emblem-versus/docs/BROWSER_ARCHITECTURE.md). The existing [playable browser campaign](FE8_BROWSER_CAMPAIGN.md) remains available during this work.
