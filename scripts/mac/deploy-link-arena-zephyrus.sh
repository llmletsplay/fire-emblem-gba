#!/usr/bin/env bash
# Prepare an isolated Link Arena work folder on Zephyrus. This only copies the
# FE7 ROM into the lab folder; it does not launch mGBA or touch the campaign save.
set -euo pipefail

REMOTE="${ZEPHYRUS_HOST:-zephyrus.thomasjvu.com}"
REMOTE_REPO='C:\Users\thoma\llmletsplay\fire-emblem-gba'
REMOTE_ROOT='C:\Users\thoma\AppData\Local\FE7-Link-Arena\runner'
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
XPS="$ROOT/roms/fe7-link-arena-maxed.xps"
UNVERIFIED_SAV="$ROOT/roms/fe7-link-arena-maxed-unverified.sav"

if [[ ! -f "$XPS" ]]; then
  echo "Missing candidate save: $XPS" >&2
  exit 2
fi

echo '== create isolated runner folders on Zephyrus =='
ssh "$REMOTE" "cmd /c \"if not exist $REMOTE_ROOT\\tools mkdir $REMOTE_ROOT\\tools & if not exist $REMOTE_ROOT\\src\\link_arena mkdir $REMOTE_ROOT\\src\\link_arena & if not exist $REMOTE_ROOT\\lua mkdir $REMOTE_ROOT\\lua & if not exist $REMOTE_ROOT\\scripts\\windows mkdir $REMOTE_ROOT\\scripts\\windows & if not exist $REMOTE_ROOT\\roms mkdir $REMOTE_ROOT\\roms\""

echo '== copy Link Arena-only runtime files =='
scp "$ROOT/tools/link_arena.py" "$REMOTE:$REMOTE_ROOT\\tools\\link_arena.py"
scp "$ROOT/src/link_arena/__init__.py" "$REMOTE:$REMOTE_ROOT\\src\\link_arena\\__init__.py"
scp "$ROOT/src/link_arena/bridge.py" "$REMOTE:$REMOTE_ROOT\\src\\link_arena\\bridge.py"
scp "$ROOT/src/link_arena/coordinator.py" "$REMOTE:$REMOTE_ROOT\\src\\link_arena\\coordinator.py"
scp "$ROOT/lua/socketserver.lua" "$REMOTE:$REMOTE_ROOT\\lua\\socketserver.lua"
scp "$ROOT/lua/fe7_memory.lua" "$REMOTE:$REMOTE_ROOT\\lua\\fe7_memory.lua"
scp "$ROOT/scripts/windows/Start-Link-Arena.ps1" "$REMOTE:$REMOTE_ROOT\\scripts\\windows\\Start-Link-Arena.ps1"
scp "$XPS" "$REMOTE:$REMOTE_ROOT\\roms\\fe7-link-arena-maxed.xps"

if [[ -f "$UNVERIFIED_SAV" ]]; then
  if ssh "$REMOTE" "cmd /c \"if exist $REMOTE_ROOT\\roms\\fe7.sav exit /b 1\""; then
    echo '== stage the converted candidate as an unverified isolated FE7 save =='
    scp "$UNVERIFIED_SAV" "$REMOTE:$REMOTE_ROOT\\roms\\fe7.sav"
  else
    echo 'An isolated fe7.sav already exists on Zephyrus; preserving it.'
  fi
fi

echo '== copy FE7 ROM into the isolated lab only =='
ssh "$REMOTE" "cmd /c \"copy /Y $REMOTE_REPO\\roms\\fe7.gba $REMOTE_ROOT\\roms\\fe7.gba\""

echo '== remote lab inventory =='
ssh "$REMOTE" "cmd /c \"dir /-C $REMOTE_ROOT\\roms\\fe7.gba $REMOTE_ROOT\\roms\\fe7-link-arena-maxed.xps\""
echo 'The XPS and, when available, an unverified raw save are staged only in the isolated lab. Confirm the roster before starting a match.'
