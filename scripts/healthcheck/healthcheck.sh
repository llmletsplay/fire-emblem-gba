#!/usr/bin/env bash
# healthcheck.sh — verify the FE GBA stream is live on Twitch, post a Discord
# webhook alert when it has been down long enough to matter.
#
# Designed to be triggered by a systemd timer (fe-healthcheck.timer) every 60
# seconds. Idempotent: safe to run as often as you like.
#
# Required env (loaded from /opt/fe-gba/.env via systemd EnvironmentFile=):
#   TWITCH_CLIENT_ID         from https://dev.twitch.tv/console/apps
#   TWITCH_CLIENT_SECRET     same place
#   TWITCH_CHANNEL_LOGIN     your Twitch username (lowercase, no @)
#   DISCORD_WEBHOOK_URL      https://discord.com/api/webhooks/<id>/<token>
#
# Optional (defaults shown):
#   HEALTHCHECK_STATE_FILE          /var/lib/fe-gba/healthcheck.state
#   HEALTHCHECK_TOKEN_CACHE         /var/lib/fe-gba/twitch-token.json
#   HEALTHCHECK_OFFLINE_THRESHOLD   seconds before first DOWN alert    (120)
#   HEALTHCHECK_ALERT_COOLDOWN      seconds between repeat alerts      (600)
#   HEALTHCHECK_TEST_ALERT          "on" → send a TEST UP message on
#                                   first run after install. Useful for
#                                   confirming the Discord webhook works.
#
# Exit codes:
#   0  - state recorded, no action needed (or alert posted successfully)
#   1  - configuration error
#   2  - Twitch API call failed (no alert posted; treat as transient)

set -uo pipefail

: "${TWITCH_CLIENT_ID:?TWITCH_CLIENT_ID required (register app at https://dev.twitch.tv/console/apps)}"
: "${TWITCH_CLIENT_SECRET:?TWITCH_CLIENT_SECRET required}"
: "${TWITCH_CHANNEL_LOGIN:?TWITCH_CHANNEL_LOGIN required (your Twitch username, lowercase)}"
: "${DISCORD_WEBHOOK_URL:?DISCORD_WEBHOOK_URL required (Discord channel webhook)}"

STATE_FILE="${HEALTHCHECK_STATE_FILE:-/var/lib/fe-gba/healthcheck.state}"
TOKEN_CACHE="${HEALTHCHECK_TOKEN_CACHE:-/var/lib/fe-gba/twitch-token.json}"
OFFLINE_THRESHOLD="${HEALTHCHECK_OFFLINE_THRESHOLD:-120}"
ALERT_COOLDOWN="${HEALTHCHECK_ALERT_COOLDOWN:-600}"
TEST_ALERT="${HEALTHCHECK_TEST_ALERT:-off}"
SCREENSHOT_PATH="${HEALTHCHECK_SCREENSHOT_PATH:-/opt/fe-gba/screenshots/latest.png}"
SNAPSHOT_DIR="${HEALTHCHECK_SNAPSHOT_DIR:-/var/log/fe-gba/snapshots}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$TOKEN_CACHE")"
NOW=$(date +%s)

# ---------------------------------------------------------------------------
#  Twitch Client Credentials token (cached to disk, refreshed on expiry)
# ---------------------------------------------------------------------------
get_token() {
    if [[ -f "$TOKEN_CACHE" ]]; then
        local exp token
        exp=$(jq -r '.expires_at // 0' "$TOKEN_CACHE" 2>/dev/null)
        token=$(jq -r '.access_token // ""' "$TOKEN_CACHE" 2>/dev/null)
        if [[ -n "$token" && -n "$exp" && "$exp" -gt $((NOW + 300)) ]]; then
            echo "$token"
            return 0
        fi
    fi
    local resp expires_in expires_at
    resp=$(curl -fsS -X POST \
        "https://id.twitch.tv/oauth2/token" \
        -d "client_id=$TWITCH_CLIENT_ID" \
        -d "client_secret=$TWITCH_CLIENT_SECRET" \
        -d "grant_type=client_credentials") || return 1
    token=$(echo "$resp" | jq -r '.access_token // ""')
    expires_in=$(echo "$resp" | jq -r '.expires_in // 0')
    [[ -z "$token" || "$token" == "null" || -z "$expires_in" ]] && return 1
    expires_at=$((NOW + expires_in))
    jq -nc --arg t "$token" --argjson e "$expires_at" \
        '{access_token:$t, expires_at:$e}' > "$TOKEN_CACHE"
    chmod 600 "$TOKEN_CACHE"
    echo "$token"
}

# ---------------------------------------------------------------------------
#  State file — small key=value log, written atomically
# ---------------------------------------------------------------------------
#   last_state    live | offline | idle | unknown
#   last_change   epoch when last_state last transitioned
#   last_alert    epoch when the last Discord alert was sent
read_state() {
    S_LAST_STATE="unknown"
    S_LAST_CHANGE=0
    S_LAST_ALERT=0
    [[ -f "$STATE_FILE" ]] || return 0
    while IFS='=' read -r k v; do
        case "$k" in
            last_state)  S_LAST_STATE="$v" ;;
            last_change) S_LAST_CHANGE="$v" ;;
            last_alert)  S_LAST_ALERT="$v" ;;
        esac
    done < "$STATE_FILE"
}

write_state() {
    local tmp="$STATE_FILE.tmp.$$"
    {
        echo "last_state=$1"
        echo "last_change=$2"
        echo "last_alert=$3"
    } > "$tmp"
    mv -f "$tmp" "$STATE_FILE"
    chmod 644 "$STATE_FILE"
}

# ---------------------------------------------------------------------------
#  Discord webhook (fire-and-forget; failures logged to stderr)
# ---------------------------------------------------------------------------
discord_post() {
    local content="$1"
    curl -fsS -X POST \
        -H "Content-Type: application/json" \
        -d "$(jq -nc --arg c "$content" '{content: $c}')" \
        "$DISCORD_WEBHOOK_URL" >/dev/null 2>&1 || \
        echo "[healthcheck] Discord post failed" >&2
}

# discord_post_with_image  - same as discord_post, but attaches a single PNG
# (Discord webhook multipart form upload). Falls back to text-only post if the
# image is missing or empty. 8MB upload limit per Discord webhook.
discord_post_with_image() {
    local content="$1" image_path="$2"

    if [[ ! -s "$image_path" ]]; then
        echo "[healthcheck] no screenshot at $image_path; posting text only" >&2
        discord_post "$content"
        return
    fi

    # Discord expects the JSON body under the field name "payload_json" when
    # uploading alongside a file.
    local payload
    payload=$(jq -nc --arg c "$content" '{content: $c}')

    if curl -fsS -X POST \
        -F "file=@${image_path}" \
        -F "payload_json=${payload}" \
        "$DISCORD_WEBHOOK_URL" >/dev/null 2>&1; then
        return 0
    fi

    echo "[healthcheck] Discord post with image failed; falling back to text" >&2
    discord_post "$content"
}

# snapshot_archive - copy the live screenshot into a date-stamped history file
# so we keep a record of what the AI was doing when the alert fired. Best-effort.
snapshot_archive() {
    local src="$SCREENSHOT_PATH" tag="$1"
    [[ -s "$src" ]] || return 0
    mkdir -p "$SNAPSHOT_DIR" 2>/dev/null || return 0
    cp -f "$src" "$SNAPSHOT_DIR/${tag}-${NOW}.png" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
#  "Should we expect to be live right now?" — only alert if the stream is
#  supposed to be running. If fe-stream.target is inactive, we're intentionally
#  offline and the state machine resets to 'idle'.
# ---------------------------------------------------------------------------
expecting_live() {
    systemctl is-active --quiet fe-stream.target 2>/dev/null
}

read_state

if ! expecting_live; then
    if [[ "$S_LAST_STATE" != "idle" ]]; then
        write_state "idle" "$NOW" "$S_LAST_ALERT"
        if [[ "$S_LAST_STATE" == "live" ]]; then
            discord_post "⏸️ **$TWITCH_CHANNEL_LOGIN stream stopped** (fe-stream.target is inactive)."
        fi
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
#  Query Twitch Helix /streams
# ---------------------------------------------------------------------------
token=$(get_token) || {
    echo "[healthcheck] failed to obtain Twitch token" >&2
    exit 1
}

streams_resp=$(curl -fsS -G \
    -H "Authorization: Bearer $token" \
    -H "Client-Id: $TWITCH_CLIENT_ID" \
    --data-urlencode "user_login=$TWITCH_CHANNEL_LOGIN" \
    "https://api.twitch.tv/helix/streams") || {
    echo "[healthcheck] Twitch /streams call failed" >&2
    exit 2
}

is_live=$(echo "$streams_resp" | jq -r '.data | length')
title=$(echo "$streams_resp" | jq -r '.data[0].title // ""')
viewer_count=$(echo "$streams_resp" | jq -r '.data[0].viewer_count // 0')

# ---------------------------------------------------------------------------
#  State machine
# ---------------------------------------------------------------------------
if [[ "$is_live" -gt 0 ]]; then
    # ---- LIVE ----
    if [[ "$S_LAST_STATE" == "offline" ]]; then
        # Recovery
        duration_offline=$((NOW - S_LAST_CHANGE))
        discord_post_with_image "✅ **$TWITCH_CHANNEL_LOGIN stream is BACK** after ${duration_offline}s offline. Viewers: $viewer_count. Title: $title" "$SCREENSHOT_PATH"
        snapshot_archive "back"
        write_state "live" "$NOW" "$S_LAST_ALERT"
    elif [[ "$S_LAST_STATE" != "live" ]]; then
        # First time going live (e.g. fresh boot, or recovered from idle)
        if [[ "$TEST_ALERT" == "on" ]]; then
            discord_post_with_image "✅ **$TWITCH_CHANNEL_LOGIN stream is LIVE** (healthcheck initialised). Viewers: $viewer_count. Title: $title" "$SCREENSHOT_PATH"
        fi
        write_state "live" "$NOW" "$S_LAST_ALERT"
    else
        # Still live — no state change. Touch nothing.
        :
    fi
    exit 0
fi

# ---- OFFLINE ----
if [[ "$S_LAST_STATE" != "offline" ]]; then
    # First detection of offline — just record, don't alert yet (avoids
    # alerting on a one-off Twitch API blip).
    write_state "offline" "$NOW" "$S_LAST_ALERT"
    exit 0
fi

offline_duration=$((NOW - S_LAST_CHANGE))

# First DOWN alert when threshold is crossed.
if [[ $offline_duration -ge $OFFLINE_THRESHOLD && $S_LAST_ALERT -lt $S_LAST_CHANGE ]]; then
    diag=$(systemctl is-active fe-mgba fe-backend fe-ffmpeg 2>&1 | tr '\n' ' ')
    discord_post_with_image "🔴 **$TWITCH_CHANNEL_LOGIN stream is DOWN** — ${offline_duration}s offline. Services: \`$diag\`. Check \`/var/log/fe-gba/supervisor.log\`." "$SCREENSHOT_PATH"
    snapshot_archive "down"
    write_state "offline" "$S_LAST_CHANGE" "$NOW"
    exit 0
fi

# Escalation: still offline past cooldown, send a reminder.
# Skip the screenshot here — repeats are just noise and we'd be re-attaching
# the same frame.
time_since_alert=$((NOW - S_LAST_ALERT))
if [[ $time_since_alert -ge $ALERT_COOLDOWN ]]; then
    diag=$(systemctl is-active fe-mgba fe-backend fe-ffmpeg 2>&1 | tr '\n' ' ')
    discord_post "⚠️ **$TWITCH_CHANNEL_LOGIN still offline** — ${offline_duration}s total. Services: \`$diag\`."
    write_state "offline" "$S_LAST_CHANGE" "$NOW"
    exit 0
fi

exit 0