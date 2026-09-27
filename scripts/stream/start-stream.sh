#!/usr/bin/env bash
# start-stream.sh — bring up the whole streaming stack without systemd.
# Useful for one-off runs, debugging, or running inside a tmux session.
#
# Spawns three background processes:
#   1. mGBA headless with lua/stream_wrapper.lua
#   2. Python orchestrator (src/core/run.py --auto)
#   3. ffmpeg reading the two FIFOs and pushing RTMP
#
# Ctrl-C (SIGINT) tears them all down cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# Load .env (same convention as start.sh)
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

: "${ROM_FILE:?ROM_FILE must be set in .env}"

# Ensure venv
if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate

# Ensure node deps for fe-client (so the live web viewer works if you want it)
if [[ -d fe-client && ! -d fe-client/node_modules ]]; then
    (cd fe-client && npm install --silent)
fi

# Pip deps
pip install -q -r requirements.txt 2>/dev/null || true

bash scripts/stream/create-fifos.sh

PIDS=()
cleanup() {
    echo
    echo "[start-stream] shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait "${PIDS[@]}" 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1) mGBA — headless via Qt's offscreen platform plugin
echo "[start-stream] launching mGBA..."
QT_QPA_PLATFORM=offscreen \
    mgba-qt --script lua/stream_wrapper.lua "roms/${ROM_FILE}" \
    >>/tmp/fe-mgba.log 2>&1 &
PIDS+=("$!")

# 2) Python orchestrator
echo "[start-stream] launching Python backend..."
python src/core/run.py --auto \
    >>/tmp/fe-backend.log 2>&1 &
PIDS+=("$!")

# 3) ffmpeg
echo "[start-stream] launching ffmpeg RTMP push..."
bash scripts/stream/ffmpeg-stream.sh \
    >>/tmp/fe-ffmpeg.log 2>&1 &
PIDS+=("$!")

# Tail logs forever
echo "[start-stream] all three running. tailing combined logs. Ctrl-C to stop."
tail -F /tmp/fe-mgba.log /tmp/fe-backend.log /tmp/fe-ffmpeg.log