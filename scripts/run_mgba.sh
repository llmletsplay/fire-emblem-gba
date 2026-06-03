#!/usr/bin/env bash
# run_mgba.sh - Launch mGBA with Fire Emblem ROM and Lua socket server
#
# Usage: ./scripts/run_mgba.sh [port]
#   port: Socket server port (default: 8888)
#
# Set ROM_FILE env var or in .env to choose which game.
#   ROM_FILE=fe7.gba ./scripts/run_mgba.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Source .env if it exists (for ROM_FILE and other settings)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

PORT="${1:-8888}"

if [[ -z "${ROM_FILE:-}" ]]; then
    detected_roms=()
    for candidate in FE7.gba fe7.gba FE8.gba fe8.gba; do
        if [[ -f "$SCRIPT_DIR/roms/$candidate" ]]; then
            detected_roms+=("$candidate")
        fi
    done

    if [[ "${#detected_roms[@]}" -eq 1 ]]; then
        ROM_FILE="${detected_roms[0]}"
    else
        echo "ERROR: ROM_FILE is not configured."
        echo "  Set ROM_FILE in .env or environment to FE7.gba or FE8.gba."
        exit 1
    fi
fi

ROM="roms/${ROM_FILE}"
LUA_SCRIPT="lua/socketserver.lua"

# Find mGBA binary
MGBA=""
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS - check .app bundle first, then PATH
    APP_PATH="/Applications/mGBA.app/Contents/MacOS/mGBA"
    if [[ -x "$APP_PATH" ]]; then
        MGBA="$APP_PATH"
    fi
fi

# Fallback to PATH
if [[ -z "$MGBA" ]]; then
    if command -v mgba-qt &>/dev/null; then
        MGBA="mgba-qt"
    elif command -v mgba &>/dev/null; then
        MGBA="mgba"
    elif command -v mGBA &>/dev/null; then
        MGBA="mGBA"
    fi
fi

if [[ -z "$MGBA" ]]; then
    echo "ERROR: mGBA not found."
    echo "  macOS: Install to /Applications/mGBA.app or add to PATH"
    echo "  Linux: apt install mgba-qt / pacman -S mgba-qt"
    echo "  Or set MGBA_PATH env var to the mGBA binary"
    exit 1
fi

# Allow override via env var
MGBA="${MGBA_PATH:-$MGBA}"

# Check ROM exists
ROM_PATH="$SCRIPT_DIR/$ROM"
LUA_PATH="$SCRIPT_DIR/$LUA_SCRIPT"

if [[ ! -f "$ROM_PATH" ]]; then
    echo "ERROR: ROM not found at $ROM_PATH"
    echo "  Place your ROM at: $ROM_PATH"
    echo "  Set ROM_FILE in .env or environment (current: ${ROM_FILE})"
    exit 1
fi

if [[ ! -f "$LUA_PATH" ]]; then
    echo "ERROR: Lua script not found at $LUA_PATH"
    exit 1
fi

echo "=== mGBA Launch ==="
echo "  Binary:  $MGBA"
echo "  ROM:     $ROM_PATH"
echo "  Script:  $LUA_PATH"
echo "  Port:    $PORT"
echo ""
echo "The Lua socket server will listen on localhost:$PORT"
echo "Connect with: python tools/memory_probe.py --port $PORT"
echo ""

# Export port for the Lua script to pick up (if it reads env)
export FE_SOCKET_PORT="$PORT"

# Launch mGBA with the Lua script
exec "$MGBA" --script "$LUA_PATH" "$ROM_PATH"
