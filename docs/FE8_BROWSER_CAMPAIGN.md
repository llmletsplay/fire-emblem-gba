# Play the full FE8 campaign in your browser

The browser player loads your original FE8 USA ROM into real mGBA WebAssembly. Both routes, native battles and normal story save slots use the original game. Campaign play is single-player and independent of the Versus online rooms.

```sh
git submodule update --init --recursive
npm ci --prefix vendor/fire-emblem-versus/browser
npm run fe8:browser:build
npm run fe8:browser
```

Open http://127.0.0.1:5173/campaign.html. The game loads automatically and resumes a compatible previous session. Players do not choose or provide a ROM. The browser distribution bundles the verified decomp-built campaign; the build operator still prepares the upstream asset inputs as described in the [browser build guide](../vendor/fire-emblem-versus/docs/BROWSER_ONLINE.md).

The game runs on your computer. Campaign play does not connect to PartyKit rooms. The page has an emulator toolbar (Pause/Play, Reset, Sound, Theater view and Fullscreen), a keyboard guide and a save manager. Arrows move, X confirms, Z cancels, Enter is Start, Backspace is Select and Q/W are L/R. Click the screen to play. Fullscreen can be exited with Escape.

Use FE8's normal Save command, then **Save to browser** before closing. The latest session restores automatically on reload; **Resume session** restores its checkpoint manually. **Save state / Load state** keep a separate manual checkpoint. Cartridge save **Export / Import** moves native `.sav` files; checkpoint files and previous-save recovery are under the expandable recovery section.

Save data belongs to the exact browser origin; localhost ports and a public deployment have different storage. Browser cleanup can remove it. Export backups before switching devices. Imports accept native 32 KiB SRAM and padded 64 KiB saves. State exports include matching SRAM and are tied to the game and emulator build. Read [all save and recovery behavior](../vendor/fire-emblem-versus/docs/BROWSER_CAMPAIGN.md).

`tools/build_browser.py` stages the campaign automatically. Rebuild the original campaign explicitly with `python3 vendor/fire-emblem-versus/tools/stage_browser_campaign.py --rebuild`. The website build refuses missing or mismatched game data. Generated game assets are excluded from Git and the source package, and included in the deployable `browser/dist/game/` artifact.

The runtime remains real mGBA WebAssembly emulation, rather than directly compiled FE8 C. See the [architecture and native-port work](../vendor/fire-emblem-versus/docs/BROWSER_ARCHITECTURE.md) for the remaining platform and asset dependencies.

Verified: automatic bundled-game loading, normal new-game/story flow, desktop and narrow player layouts, fullscreen, theater view, sound toggling, persistent checkpoint after reload, checkpoint file import/export, `.sav` export/import, real-core SRAM initialization and fresh-core restore, checksum/version rejection and ordered IndexedDB persistence. Existing online Versus protocol and full battle-scene emulator regressions also passed. A complete playthrough of both routes has not been performed. Public hosting still requires the operator's PartyKit authentication/deployment.

Players do not install mGBA: it is a WebAssembly library embedded in the current site. The separate direct native engine target is documented in [native port status](FE8_NATIVE_PORT.md) and is not yet a playable campaign.
