#!/usr/bin/env bash
# Apply CAP/LOADSTATE/attach fixes on Thomas's Mac checkout, restart backend, verify 2 cycles.
set -euo pipefail
REPO="${1:-/Users/area/repos/llmletsplay-fire-emblem/fe-gba}"
PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "== git status =="
git status -sb || true

echo "== applying patch (3-way; may need manual merge if local diverge) =="
if git apply --check "$PATCH_DIR/0001-cap-loadstate-attach-settle.patch" 2>/tmp/fe-patch-check.err; then
  git apply "$PATCH_DIR/0001-cap-loadstate-attach-settle.patch"
  echo "Patch applied cleanly."
else
  echo "Clean apply failed; trying 3-way..."
  cat /tmp/fe-patch-check.err || true
  git apply --3way "$PATCH_DIR/0001-cap-loadstate-attach-settle.patch" || {
    echo "FAILED to apply. Manual merge needed against local Mac tree."
    exit 1
  }
fi

# Ensure .env knobs
ENV_FILE="$REPO/.env"
touch "$ENV_FILE"
ensure_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    # leave existing
    true
  else
    echo "${key}=${val}" >> "$ENV_FILE"
    echo "Added ${key}=${val}"
  fi
}
ensure_env FE_LOAD_SAVESTATE false
ensure_env FE_ATTACH_EXISTING true
ensure_env FE_QUIT_MGBA_ON_EXIT false
ensure_env FE_ACTION_SETTLE_SEC 1.5
ensure_env FE_CAP_TIMEOUT 5
ensure_env FE_CAP_RETRIES 2

echo "== socket 8888 =="
if lsof -iTCP:8888 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8888 listening — will attach; skip mGBA restart unless wedged."
  WEDGED=0
  # quick CAP probe
  python3 - <<'PY' || WEDGED=1
import socket, struct, sys
s=socket.create_connection(('127.0.0.1',8888),timeout=2)
s.settimeout(5)
s.sendall(b'CAP\n')
hdr=s.recv(4)
if not hdr or len(hdr)<4:
    sys.exit(2)
if hdr.startswith(b'ERR'):
    sys.exit(3)
size=struct.unpack('>I', hdr)[0]
got=0
while got<size:
    chunk=s.recv(min(65536,size-got))
    if not chunk: sys.exit(4)
    got+=len(chunk)
print(f'CAP_OK size={size}')
s.close()
PY
  if [[ "$WEDGED" != 0 ]]; then
    echo "CAP probe failed — restarting mGBA via open -a"
    # Prefer not kill unless necessary; if CAP fails, restart
    pkill -x mGBA 2>/dev/null || true
    sleep 1
    open -a mGBA --args --script lua/socketserver.lua roms/fe7.gba
    sleep 4
  fi
else
  echo "Port 8888 not listening — starting mGBA"
  open -a mGBA --args --script lua/socketserver.lua roms/fe7.gba
  sleep 4
fi

echo "== stop old backend =="
pkill -f 'src/core/run.py --auto' 2>/dev/null || true
sleep 1

TS=$(date +%Y%m%d-%H%M%S)
LOG="$REPO/logs/backend-$TS.log"
mkdir -p "$REPO/logs"
echo "== start backend -> $LOG =="
cd "$REPO"
# shellcheck disable=SC1091
source venv/bin/activate
export LLM_PROVIDER=MINIMAX
export PYTHONUNBUFFERED=1
nohup python src/core/run.py --auto >"$LOG" 2>&1 &
BPID=$!
echo "backend pid=$BPID"
sleep 8

echo "== wait for 2 cycles (up to ~8 min) =="
deadline=$((SECONDS+480))
ok1=0; ok2=0
while (( SECONDS < deadline )); do
  if ! kill -0 "$BPID" 2>/dev/null; then
    echo "BACKEND_DEAD"
    tail -80 "$LOG"
    exit 2
  fi
  # Cycle markers: "--- Loop Cycle N ---" and action sent
  c1=$(grep -c '--- Loop Cycle 1 ---' "$LOG" || true)
  c2=$(grep -c '--- Loop Cycle 2 ---' "$LOG" || true)
  a1=$(grep -c "Action '.*' sent to mGBA" "$LOG" || true)
  echo "t=${SECONDS}s cycles1=$c1 cycles2=$c2 actions=$a1 alive=yes"
  if [[ "$c2" -ge 1 && "$a1" -ge 2 ]]; then
    echo "SUCCESS: Cycle1+2 with actions"
    rg -n 'Loop Cycle|Requesting game state|sent to mGBA|settle|Skipping LOADSTATE|attaching|LOADSTATE|CAP timeout|DEAD' "$LOG" | tail -60
    exit 0
  fi
  # softer success: 2 cycles started and at least 1 action
  if [[ "$c2" -ge 1 && "$a1" -ge 1 ]]; then
    echo "PARTIAL_OK: Cycle2 started with >=1 action; waiting briefly for 2nd action..."
  fi
  sleep 15
done
echo "TIMEOUT waiting for 2 cycles"
tail -100 "$LOG"
exit 3
