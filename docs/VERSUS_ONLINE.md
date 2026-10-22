# Fire Emblem Versus Online

The standalone submodule includes a real browser port: mGBA WebAssembly runs FE8 locally, with full battle scenes and native controls. PartyKit hosts shared rooms, Blue/Red seats, spectators, ordered commands, state-hash agreement and reconnect replay. This first browser release is human vs human plus spectators. The existing native model tournaments remain available; hosted-model agents are not yet connected to browser rooms.

## Setup from this project

```sh
git submodule update --init --recursive
python3 vendor/fire-emblem-versus/tools/manage.py bootstrap --base /absolute/path/to/fe8-usa.gba --with-tests
# Install and activate Emscripten, CMake and Node 22.19+ first.
npm --prefix vendor/fire-emblem-versus/browser ci
npm run versus:online:build
npm run versus:online
```

Open `http://127.0.0.1:1999/`. One local PartyKit process serves the production website and room WebSockets. Choose your clean FE8 USA ROM; patching and verification happen locally and ROM bytes never go to the room server. Pick the map, two parties, objective and opening army, join, then copy the invite. Each participant supplies their own ROM. Keyboard and touch controls operate the real native menus.

A hosted deployment uses the same website and room service from one PartyKit hostname:

```sh
cd vendor/fire-emblem-versus/browser
npx partykit login
npm run deploy
```

The CLI was not signed in during implementation, so no public URL has been deployed. The local two-client production build is verified. A localhost invite only works on the same machine; deploy the project before inviting someone across the internet.

## Play and recovery

Focus the game: arrows move, X confirms, Z cancels, Enter is Start, Backspace is Select, Q/W are L/R. Enable sound with the separate button. Blue and Red each control only their active army. Both emulators execute and confirm each command before the next action unlocks. A held confirm is blocked until release at that boundary.

The room waits when a player disconnects. The same tab's private seat credential permits reconnect; the client replays confirmed commands and resumes a pending action. Spectators replay the same transcript. Use Leave / new match and a fresh room code for a rematch. A true state mismatch stops the room rather than inventing a result. Browser suspension can delay confirmation until the tab resumes.

The room coordinates and verifies peer reports; it does not run an authoritative game emulator on the edge. This is cooperative play, not ranked anti-cheat. Keep hosted model/API credentials in the native/server runner rather than exposing them in the browser.

The complete [standalone browser guide](../vendor/fire-emblem-versus/docs/BROWSER_ONLINE.md) covers build dependencies, native controls, hosting, protocol, trust limits and verification commands. [Browser evidence](evidence/browser-online.json) records WASM, WebSocket, native regression and two-client UI checks.

For the original single-player FE8 game, see [browser campaign setup](FE8_BROWSER_CAMPAIGN.md).
