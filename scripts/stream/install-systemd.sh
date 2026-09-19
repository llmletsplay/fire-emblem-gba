#!/usr/bin/env bash
# install-systemd.sh — install + enable the systemd units for the streaming
# stack. Assumes the project has been deployed to $INSTALL_DIR (default
# /opt/fe-gba) and that the user described in $SERVICE_USER exists.
#
# Idempotent: safe to re-run.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/fe-gba}"
SERVICE_USER="${SERVICE_USER:-fe}"
SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_SRC="$SRC_DIR/scripts/systemd"

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "[install] $INSTALL_DIR does not exist. Clone the repo there first." >&2
    exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "[install] creating service user $SERVICE_USER (no login)..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Sync runtime bits
echo "[install] syncing $SRC_DIR -> $INSTALL_DIR"
rsync -a --delete \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='logs' \
    --exclude='screenshots' \
    --exclude='fe-client/public/chronicle' \
    --exclude='assets/chronicle' \
    --exclude='*.gba' \
    --exclude='.env' \
    --exclude='.phantasy' \
    --exclude='config' \
    "$SRC_DIR/" "$INSTALL_DIR/"

# .env stays managed by the operator, but make sure the file exists with safe perms
if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "[install] created $INSTALL_DIR/.env from example — EDIT IT BEFORE STARTING."
fi
chmod 600 "$INSTALL_DIR/.env"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"

# Logging dir
mkdir -p /var/log/fe-gba
chown "$SERVICE_USER":"$SERVICE_USER" /var/log/fe-gba

# Install units
install -m 0644 "$UNIT_SRC/fe-romfetch.service"  /etc/systemd/system/
install -m 0644 "$UNIT_SRC/fe-mgba.service"      /etc/systemd/system/
install -m 0644 "$UNIT_SRC/fe-backend.service"   /etc/systemd/system/
install -m 0644 "$UNIT_SRC/fe-ffmpeg.service"    /etc/systemd/system/
install -m 0644 "$UNIT_SRC/fe-stream.target"     /etc/systemd/system/

systemctl daemon-reload
systemctl enable fe-stream.target
systemctl enable fe-romfetch.service

echo
echo "[install] done. To start the stream:"
echo "    systemctl start fe-stream.target"
echo
echo "[install] To watch the live logs:"
echo "    journalctl -u fe-mgba -u fe-backend -u fe-ffmpeg -f"