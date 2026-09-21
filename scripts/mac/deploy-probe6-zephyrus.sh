#!/usr/bin/env bash
# Run FROM Mac: scp lua/probe to zephyrus, nuke watchers, restart mGBA, run probe6.
set -euo pipefail
REPO="${1:-$HOME/repos/llmletsplay-fire-emblem/fe-gba}"
REMOTE="${ZEPHYRUS_HOST:-zephyrus.thomasjvu.com}"
REMOTE_DIR='C:\Users\thoma\llmletsplay\fire-emblem-gba'

cd "$REPO"
echo "== git status =="
git status -sb

echo "== scp files =="
scp lua/socketserver.lua "${REMOTE}:${REMOTE_DIR}\\lua\\socketserver.lua"
scp tools/fe_move_probe6.py "${REMOTE}:${REMOTE_DIR}\\tools\\fe_move_probe6.py"
scp scripts/windows/fe-probe6-run.bat "${REMOTE}:${REMOTE_DIR}\\scripts\\windows\\fe-probe6-run.bat"
scp scripts/windows/fe-probe6-sync.bat "${REMOTE}:${REMOTE_DIR}\\scripts\\windows\\fe-probe6-sync.bat"

echo "== remote: nuke watchers, kill mGBA =="
ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && if exist fe-nuke-watch.bat (call fe-nuke-watch.bat)"'
ssh "$REMOTE" 'cmd /c "taskkill /F /IM mGBA.exe 2>nul"'
sleep 2

echo "== remote: read ROM_FILE =="
ROM_FILE=$(ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && findstr /B ROM_FILE= .env"' | tr -d '\r' | cut -d= -f2-)
ROM_FILE=${ROM_FILE:-FE7.gba}
echo "ROM_FILE=${ROM_FILE}"

echo "== remote: start mGBA with lua =="
ssh "$REMOTE" "cmd /c \"cd /d C:\\Users\\thoma\\llmletsplay\\fire-emblem-gba && start \\\"\\\" \\\"C:\\Program Files\\mGBA\\mGBA.exe\\\" --script lua\\socketserver.lua roms\\${ROM_FILE}\""
sleep 7

echo "== remote: run probe6 =="
ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && call scripts\windows\fe-probe6-run.bat"'
