# FE8 browser runtimes and native port

Players install no emulator, extension, compiler or other application, and supply no ROM. The default campaign and Versus still use the bundled mGBA WASM reference runtime. The separate native campaign verification build compiles FE8 C directly to WASM and loads its original data pack without ARM emulation.

## Native campaign verification build

The standalone submodule now strictly links all 364 adapted C units with no unresolved symbols. Actual native execution reaches the title/New Game menu, campaign introduction, prologue map and full battle scene. A 9,000-frame test exercises that path. Native browser visual/playability verification and the production migration remain incomplete.

Developer commands, from the standalone checkout:

```sh
python3 tools/compile_native_engine.py
python3 tools/verify_native_data_abi.py
python3 tools/verify_native_ram_abi.py
python3 tools/link_native_engine.py --adapted
python3 tools/stage_native_game.py
cd browser
npm run test:native
npm run dev -- --port 1999
```

Open `/campaign.html?engine=native`. That URL loads a native engine module and Web Audio host; it downloads no `.gba` and initializes no mGBA core. The existing player controls/save manager support it. Native and reference saves use separate storage keys; portable `.sav` files can transfer between engines. Native checkpoints bind the exact WASM build and do not include immutable assets.

The build requires Emscripten and the local matching source/data build. Those are developer requirements, not player setup. The smaller `npm run fe8:native:build` / `npm run fe8:native:test` commands remain ROM-free diagnostics, with `playable_campaign: false` in their diagnostic manifest. They are distinct from the full engine above.

## Verification evidence

- 10,380 native C initializer objects and 24,030 explicit pointer fields match original bytes. The data exporter retains 1,259 original data sections and excludes executable ARM text.
- 422 emitted RAM object sizes checked; one private boolean narrowing retains its original pooled allocation. All 640 original RAM aliases are preserved.
- 61 save record sizes, alignments and offsets match the original agbcc compiler, including Dungeon bitfields crossing storage-unit boundaries. The native save writer calculates SRAM offsets explicitly instead of truncating native pointers.
- 149 MP2K command cases, 317 PCM mixer/VSync cases, 258 sequencer/note-allocation cases and 42 text/sprite/movement assembly cases match original ARM execution. Reference execution is test-only.
- All 34 synthetic video scenes pass complete-frame and scanline rendering. A separate fixture checks a mid-frame affine reference reload.
- Actual-engine host tests verify music reaches output, deterministic checkpoint continuation, fresh-instance checkpoint/SRAM restoration and original save packing/loading of a prologue unit. The fixture checkpoint is about 1.75 MiB.
- Browser unit tests, TypeScript validation and production build pass. This does not replace visual interaction or a complete campaign playthrough.

## Remaining completion gates

Verify the native browser player visually, including input, audio, full combat, reset and save-manager persistence. Exercise campaign route/chapter events and gameplay against the reference. Integrate the native Versus overlay/online transport and tournament controls. Promote the verified native campaign as the default and package its final distribution. A complete two-route campaign playthrough has not been verified.

See [native build details](../vendor/fire-emblem-versus/native/README.md), [browser architecture](../vendor/fire-emblem-versus/docs/BROWSER_ARCHITECTURE.md) and [current campaign setup](FE8_BROWSER_CAMPAIGN.md).
