#!/usr/bin/env bash
# supervisor-stream.sh — wraps ffmpeg-stream.sh with auto-restart + backoff +
# rapid-failure circuit breaker. Replaces ffmpeg-stream.sh as the systemd
# ExecStart target so that:
#
#   - ffmpeg dropping the RTMP socket (network hiccup, Twitch ingest
#     failover, key rotation) no longer kills the stream — supervisor
#     restarts ffmpeg from clean state and mGBA just keeps writing frames.
#   - A truly broken config (bad RTMP_URL / STREAM_KEY) is detected via the
#     "rapid failures" counter and surfaced loudly instead of looping
#     forever.
#   - systemd SIGTERM is propagated to ffmpeg for a clean stop.
#
# Tunables (env, with sane defaults):
#   STREAM_BACKOFF_INITIAL  seconds to wait after first ffmpeg exit       (5)
#   STREAM_BACKOFF_MAX      upper bound on backoff between restarts       (60)
#   STREAM_STABLE_RUNTIME   ffmpeg must run at least this long to count   (60)
#                           as "stable"; short runs increment the
#                           rapid-failure counter.
#   STREAM_MAX_RAPID_FAILS  give up after this many consecutive short     (5)
#                           ffmpeg runs. Supervisor exits non-zero →
#                           systemd Restart=on-failure picks it back up
#                           after RestartSec.
#
# All events go to /var/log/fe-gba/supervisor.log (in addition to journalctl).

set -uo pipefail

SUPERVISOR_START=$(date +%s)
SUPERVISOR_PID=$$
STABLE_RUNTIME="${STREAM_STABLE_RUNTIME:-60}"
BACKOFF_INITIAL="${STREAM_BACKOFF_INITIAL:-5}"
BACKOFF_MAX="${STREAM_BACKOFF_MAX:-60}"
MAX_RAPID_FAILS="${STREAM_MAX_RAPID_FAILS:-5}"

LOG_DIR="${LOG_DIR:-/var/log/fe-gba}"
SUP_LOG="$LOG_DIR/supervisor.log"

# Try to make sure the log dir exists (install-systemd.sh already creates it,
# but a manual run might not have it).
mkdir -p "$LOG_DIR" 2>/dev/null || true

log() {
    local ts msg
    ts="$(date -Iseconds)"
    msg="[supervisor $ts] $*"
    echo "$msg" >&2
    echo "$msg" >>"$SUP_LOG" 2>/dev/null || true
}

# Sanity: don't enter the loop without an RTMP target.
: "${RTMP_URL:?RTMP_URL must be set in .env}"
: "${STREAM_KEY:?STREAM_KEY must be set in .env}"

# Propagate SIGTERM/SIGINT to ffmpeg and exit cleanly so systemd marks the
# service as stopped (not failed).
shutdown() {
    log "received signal, killing ffmpeg children and exiting"
    # Kill the whole process group we created with setsid below.
    pkill -TERM -P "$FFMPEG_PID" 2>/dev/null || true
    [[ -n "${FFMPEG_PID:-}" ]] && kill -TERM "$FFMPEG_PID" 2>/dev/null || true
    sleep 1
    [[ -n "${FFMPEG_PID:-}" ]] && kill -KILL "$FFMPEG_PID" 2>/dev/null || true
    exit 0
}
trap shutdown SIGTERM SIGINT

rapid_fails=0
attempt=0

while true; do
    attempt=$((attempt + 1))
    run_start=$(date +%s)

    log "starting ffmpeg (attempt $attempt, rapid_fails=$rapid_fails)"

    # Run ffmpeg-stream.sh in its own process group so we can SIGTERM the
    # whole subtree on shutdown.
    setsid bash scripts/stream/ffmpeg-stream.sh </dev/null
    rc=$?

    run_end=$(date +%s)
    runtime=$((run_end - run_start))

    if [[ $rc -eq 0 ]]; then
        # A clean exit from ffmpeg while RTMP is supposed to be live means
        # the operator asked for it (e.g. via kill -INT). Do NOT restart.
        log "ffmpeg exited cleanly (rc=0) after ${runtime}s; supervisor stopping"
        exit 0
    fi

    log "ffmpeg exited rc=$rc after ${runtime}s"

    if [[ $runtime -lt $STABLE_RUNTIME ]]; then
        rapid_fails=$((rapid_fails + 1))
        log "  ↳ short run ($runtime < $STABLE_RUNTIME); rapid_fails=$rapid_fails/$MAX_RAPID_FAILS"
    else
        # Stable run that died — this is the normal case (Twitch hiccup).
        # Reset the rapid-failure counter and restart quickly.
        rapid_fails=0
        log "  ↳ was stable; resetting rapid_fails=0"
    fi

    if [[ $rapid_fails -ge $MAX_RAPID_FAILS ]]; then
        log "FATAL — $MAX_RAPID_FAILS rapid failures in a row; likely config error"
        log "FATAL — last 30 lines of /var/log/fe-gba/ffmpeg.log:"
        tail -30 "$LOG_DIR/ffmpeg.log" >>"$SUP_LOG" 2>/dev/null || true
        log "FATAL — supervisor exiting non-zero; systemd Restart=on-failure will pick up"
        exit 1
    fi

    # Exponential-ish backoff capped by BACKOFF_MAX, scaled by rapid_fails.
    backoff=$(( BACKOFF_INITIAL * (rapid_fails + 1) ))
    [[ $backoff -gt $BACKOFF_MAX ]] && backoff=$BACKOFF_MAX

    log "  ↳ backing off ${backoff}s before restart"
    sleep "$backoff"
done