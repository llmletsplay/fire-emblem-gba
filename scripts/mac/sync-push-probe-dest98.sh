#!/usr/bin/env bash
# Run FROM Mac: apply box patch if needed, push branch, scp probe, run dest 9,8 on zephyrus.
set -euo pipefail
REPO="${1:-$HOME/repos/llmletsplay-fire-emblem/fe-gba}"
REMOTE="${ZEPHYRUS_HOST:-zephyrus.thomasjvu.com}"
REMOTE_DIR='C:\Users\thoma\llmletsplay\fire-emblem-gba'
LOGDIR="$REPO/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/sync-push-probe-dest98-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

cd "$REPO"
echo "== git status =="
git status -sb
git fetch origin
git checkout feat/minimax-harness-refresh
# If box patch exists in cwd/uploads apply tip commit; else pull
if [[ -f /tmp/tutorial-harness.bundle ]]; then
  echo "== git pull bundle =="
  git pull /tmp/tutorial-harness.bundle feat/minimax-harness-refresh || git fetch /tmp/tutorial-harness.bundle && git merge FETCH_HEAD
fi
echo "== push =="
git push -u origin feat/minimax-harness-refresh
echo "HEAD=$(git rev-parse HEAD)"

echo "== scp probe files =="
scp lua/socketserver.lua "${REMOTE}:${REMOTE_DIR}\\lua\\socketserver.lua"
scp tools/fe_move_probe6.py "${REMOTE}:${REMOTE_DIR}\\tools\\fe_move_probe6.py"
scp scripts/windows/fe-probe6-run.bat "${REMOTE}:${REMOTE_DIR}\\scripts\\windows\\fe-probe6-run.bat"
scp scripts/windows/fe-probe6-dest98.bat "${REMOTE}:${REMOTE_DIR}\\scripts\\windows\\fe-probe6-dest98.bat"

echo "== remote: nuke watchers, kill mGBA =="
ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && if exist fe-nuke-watch.bat (call fe-nuke-watch.bat)"'
ssh "$REMOTE" 'cmd /c "taskkill /F /IM mGBA.exe 2>nul & taskkill /F /IM python.exe 2>nul"'
sleep 2

ROM_FILE=$(ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && findstr /B ROM_FILE= .env"' | tr -d '\r' | cut -d= -f2-)
ROM_FILE=${ROM_FILE:-FE7.gba}
echo "ROM_FILE=${ROM_FILE}"

echo "== remote: git pull (if repo is a git checkout) =="
ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && git fetch origin && git checkout feat/minimax-harness-refresh && git pull origin feat/minimax-harness-refresh"' || true

echo "== remote: start mGBA with lua =="
ssh "$REMOTE" "cmd /c \"cd /d C:\\Users\\thoma\\llmletsplay\\fire-emblem-gba && start \\\"\\\" \\\"C:\\Program Files\\mGBA\\mGBA.exe\\\" --script lua\\socketserver.lua roms\\${ROM_FILE}\""
sleep 8

echo "== remote: probe dest 9,8 =="
ssh "$REMOTE" 'cmd /c "cd /d C:\Users\thoma\llmletsplay\fire-emblem-gba && call scripts\windows\fe-probe6-dest98.bat"'

echo "== fetch remote logs =="
scp "${REMOTE}:${REMOTE_DIR}\\logs\\probe6_dest9_8_*.txt" "$LOGDIR/" || true
scp "${REMOTE}:${REMOTE_DIR}\\logs\\probe6_dest9_8_*.png" "$LOGDIR/" || true
ls -lt "$LOGDIR"/probe6_dest* 2>/dev/null | head
echo "DONE log=$LOG"
