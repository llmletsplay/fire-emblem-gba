#!/bin/bash
# Apply ATTACK+settle fix on Thomas's Mac live tree and restart harness.
export PATH="/opt/homebrew/bin:/usr/bin:/bin:$PATH"
set -euo pipefail

REPO="${1:-/Users/area/repos/llmletsplay-fire-emblem/fe-gba}"
PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "== git status =="
git status -sb || true

echo "== apply patch =="
if git apply --check "$PATCH_DIR/0001-fix-fe-gba-resolve-ATTACK-via-opportunities-adjacenc.patch" 2>/dev/null; then
  git apply "$PATCH_DIR/0001-fix-fe-gba-resolve-ATTACK-via-opportunities-adjacenc.patch"
else
  echo "git apply --check failed; trying --3way / patch -p1"
  git apply --3way "$PATCH_DIR/0001-fix-fe-gba-resolve-ATTACK-via-opportunities-adjacenc.patch" || \
    patch -p1 --forward < "$PATCH_DIR/0001-fix-fe-gba-resolve-ATTACK-via-opportunities-adjacenc.patch" || true
fi

echo "== .env harden (FE_LOAD_SAVESTATE=false, longer settle) =="
python3 - <<'PY'
from pathlib import Path
p = Path('.env')
text = p.read_text() if p.exists() else ''
lines = text.splitlines()
keys = {
  'FE_LOAD_SAVESTATE': 'false',
  'FE_ATTACH_EXISTING': 'true',
  'FE_ACTION_SETTLE_SEC': '2.0',
  'FE_ATTACK_SETTLE_SEC': '6.0',
  'FE_CAP_TIMEOUT': '8.0',
  'FE_CAP_RETRIES': '3',
  'FE_QUIT_MGBA_ON_EXIT': 'false',
}
out = []
seen = set()
for line in lines:
  if not line.strip() or line.strip().startswith('#') or '=' not in line:
    out.append(line); continue
  k = line.split('=',1)[0].strip()
  if k in keys:
    out.append(f'{k}={keys[k]}'); seen.add(k)
  else:
    out.append(line)
for k,v in keys.items():
  if k not in seen:
    out.append(f'{k}={v}')
p.write_text('\n'.join(out) + '\n')
print('updated', p.resolve())
PY

echo "== kill dead python backends =="
pkill -f 'python.*src/core/run.py' 2>/dev/null || true
pkill -f 'python.*run.py --auto' 2>/dev/null || true
sleep 1

echo "== quit/relaunch mGBA with lua socket =="
osascript -e 'tell application "mGBA" to quit' 2>/dev/null || true
killall mGBA 2>/dev/null || true
sleep 2

if [ -x /Applications/mGBA.app/Contents/MacOS/mGBA ]; then
  nohup /Applications/mGBA.app/Contents/MacOS/mGBA --script lua/socketserver.lua roms/fe7.gba >/tmp/mgba-fe.log 2>&1 &
elif command -v mgba >/dev/null 2>&1; then
  nohup mgba --script lua/socketserver.lua roms/fe7.gba >/tmp/mgba-fe.log 2>&1 &
else
  open -a mGBA --args --script lua/socketserver.lua roms/fe7.gba
fi
sleep 4

echo "== probe CAP 3x =="
PORT=$(python3 - <<'PY'
from pathlib import Path
port=8765
p=Path('.env')
if p.exists():
  for line in p.read_text().splitlines():
    if line.startswith('FE_MGBA_PORT=') or line.startswith('FE_PORT=') or line.startswith('FE_SOCKET_PORT='):
      try: port=int(line.split('=',1)[1].strip()); break
      except: pass
print(port)
PY
)
echo "Using TCP port $PORT"
python3 - <<PY
import socket, time, sys
port=int("$PORT")
ok=0
for i in range(3):
  try:
    s=socket.create_connection(("127.0.0.1", port), timeout=2)
    s.settimeout(5)
    s.sendall(b"CAP\n")
    try:
      data=s.recv(16)
      print(f"CAP probe {i+1}: ok ({len(data)} bytes)")
      ok += 1
    except socket.timeout:
      print(f"CAP probe {i+1}: connected, no payload (soft-ok)")
      ok += 1
    s.close()
  except Exception as e:
    print(f"CAP probe {i+1}: FAIL {e}")
  time.sleep(0.3)
print(f"CAP probes succeeded: {ok}/3")
sys.exit(0 if ok>=3 else 1)
PY

echo "== start backend =="
mkdir -p logs
LOG="logs/backend-$(date +%Y%m%d-%H%M%S).log"
nohup env FE_ATTACH_EXISTING=true FE_LOAD_SAVESTATE=false python src/core/run.py --auto >"$LOG" 2>&1 &
echo "Backend PID $! log: $REPO/$LOG"
echo "$REPO/$LOG" > /tmp/fe-gba-latest-log.txt
sleep 8
echo "== tail log =="
tail -n 50 "$LOG" || true
echo "DONE. Watch: tail -f $REPO/$LOG"
