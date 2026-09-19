#!/usr/bin/env bash
# ffmpeg-stream.sh — read raw RGB24 frames + raw s16le audio from FIFOs and
# push H.264/AAC to RTMP. Single-purpose companion for the mGBA Lua wrapper.
#
# Required environment (exported via systemd EnvironmentFile=):
#   RTMP_URL    - e.g. rtmp://live.twitch.tv/app
#                 or    rtmp://a.rtmp.youtube.com/live2
#   STREAM_KEY  - the per-stream ingest key from your platform's dashboard
#
# Optional overrides:
#   STREAM_FIFO_DIR     - directory for the two FIFOs       (default /tmp)
#   STREAM_VIDEO_FIFO   - video FIFO path                   (default fe-stream.video)
#   STREAM_AUDIO_FIFO   - audio FIFO path                   (default fe-stream.audio)
#   STREAM_BITRATE      - target video bitrate, e.g. 6000k  (default 6000k)
#   STREAM_PRESET       - libx264 preset                    (default veryfast)
#   STREAM_RESOLUTION   - WxH of the encoded video          (default 1920x1080)
#   STREAM_FPS          - output frame rate                 (default 60)
#   STREAM_AUDIO_RATE   - AAC bitrate                       (default 128k)
#
# Exit codes:
#   1 - missing config, 2 - FIFO never appeared, 3 - ffmpeg died

set -euo pipefail

: "${RTMP_URL:?RTREAM_URL must be set in .env}"
: "${STREAM_KEY:?STREAM_KEY must be set in .env}"

FIFO_DIR="${STREAM_FIFO_DIR:-/tmp}"
VIDEO_FIFO="${STREAM_VIDEO_FIFO:-$FIFO_DIR/fe-stream.video}"
AUDIO_FIFO="${STREAM_AUDIO_FIFO:-$FIFO_DIR/fe-stream.audio}"
BITRATE="${STREAM_BITRATE:-6000k}"
PRESET="${STREAM_PRESET:-veryfast}"
RESOLUTION="${STREAM_RESOLUTION:-1920x1080}"
FPS="${STREAM_FPS:-60}"
AUDIO_BITRATE="${STREAM_AUDIO_RATE:-128k}"

# ---------------------------------------------------------------------------
#  Wait up to ~30s for the video FIFO to exist (mGBA may still be loading the
#  ROM). Without this we race mGBA and ffmpeg fails immediately.
# ---------------------------------------------------------------------------
echo "[ffmpeg] waiting for video FIFO at $VIDEO_FIFO ..."
deadline=$(( $(date +%s) + 30 ))
while [[ ! -p "$VIDEO_FIFO" ]]; do
    if [[ $(date +%s) -ge $deadline ]]; then
        echo "[ffmpeg] FATAL: video FIFO never appeared after 30s" >&2
        exit 2
    fi
    sleep 1
done

# Compute output video height so that GBA's 3:2 aspect ratio fits exactly.
#   GBA source is 240x160 (3:2 = 1.5)
#   For 1920x1080 (16:9 = 1.78) we scale to height=1080 width=1620 and pad
#   150px black bars on each side.
#   For 1280x720  we scale to height=720  width=1080 and pad 100px each side.
OUT_W="${RESOLUTION%%x*}"
OUT_H="${RESOLUTION##*x}"
GAME_W=$(( OUT_H * 3 / 2 ))   # preserve 3:2, height-pinned
PAD_X=$(( (OUT_W - GAME_W) / 2 ))

echo "[ffmpeg] source 240x160 → ${GAME_W}x${OUT_H} centered in ${OUT_W}x${OUT_H}"
echo "[ffmpeg] rtmp target: ${RTMP_URL%/}/${STREAM_KEY:0:6}..."

# ---------------------------------------------------------------------------
#  ffmpeg invocation
#  - rawvideo 240x160 rgb24 @ 60fps from the video FIFO
#  - s16le 32768 Hz stereo from the audio FIFO
#  - filter: lanczos scale, pad to output resolution, resample audio to 44.1k
#  - libx264 -preset veryfast -tune animation (motion-heavy pixel art)
#  - CBR-ish: -b:v == -maxrate, bufsize 2x bitrate
#  - GOP = 1s (60 frames @ 60fps) so reconnects are quick
#  - yuv420p for max compatibility with Twitch/YouTube ingest
#  - flv muxer (RTMP-friendly)
# ---------------------------------------------------------------------------
exec ffmpeg -hide_banner -loglevel info \
    -f rawvideo -pix_fmt rgb24 -s 240x160 -r "$FPS" \
    -i "$VIDEO_FIFO" \
    -f s16le -ar 32768 -ac 2 \
    -i "$AUDIO_FIFO" \
    -filter_complex "[0:v]scale=${GAME_W}:${OUT_H}:flags=lanczos,pad=${OUT_W}:${OUT_H}:${PAD_X}:0:black,fps=${FPS}[v];[1:a]aresample=44100[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -preset "$PRESET" -tune animation \
    -b:v "$BITRATE" -maxrate "$BITRATE" -bufsize "$(awk -v b="$BITRATE" 'BEGIN{printf "%dk", 2*b}')" \
    -g "$FPS" -bf 2 -pix_fmt yuv420p \
    -c:a aac -b:a "$AUDIO_BITRATE" \
    -f flv "${RTMP_URL%/}/${STREAM_KEY}"