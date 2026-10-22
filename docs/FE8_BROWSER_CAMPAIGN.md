# Play the full FE8 campaign in your browser

The browser player loads your original FE8 USA ROM into real mGBA WebAssembly. Both routes, native battles and normal story save slots use the original game. Campaign play is single-player and independent of the Versus online rooms.

```sh
git submodule update --init --recursive
npm ci --prefix vendor/fire-emblem-versus/browser
npm run fe8:browser:build
npm run fe8:browser
```

Open http://127.0.0.1:5173/campaign.html. Supply the clean 16 MiB USA ROM with SHA-1 `c25b145e37456171ada4b0d440bf88a19f4d509f`. Build prerequisites (including the local ROM, Arm tools and Emscripten) follow the [browser build guide](../vendor/fire-emblem-versus/docs/BROWSER_ONLINE.md). The development server serves files; the game runs on your computer. Campaign play does not connect to PartyKit rooms.

Click the game: arrows move, X confirms, Z cancels, Enter is Start, Backspace is Select, Q/W are L/R. Use FE8's normal Save command, then **Save to browser** before closing. On another visit choose the ROM again; native saves load automatically and **Resume session** restores the latest checkpoint. **Save state / Load state** keep a separate manual checkpoint.

Export `.sav` for portable backups. Save data belongs to the exact browser origin; localhost ports and a public deployment have different storage. Browser cleanup can remove it. Imports accept native 32 KiB SRAM and padded 64 KiB saves. State exports include matching SRAM and are tied to the ROM and emulator build. Read [all save and recovery behavior](../vendor/fire-emblem-versus/docs/BROWSER_CAMPAIGN.md) before moving saves between devices.

Verified: original-ROM boot and native menus in the browser, persistent manual checkpoint after reload, actual `.sav` export/import, real-core SRAM initialization and fresh-core restore, checksum/version rejection and ordered IndexedDB persistence. Existing online Versus protocol and full battle-scene emulator regressions also passed. A complete playthrough of both routes has not been performed. Public hosting still requires the operator's PartyKit authentication/deployment.
