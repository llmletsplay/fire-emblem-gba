#!/usr/bin/env bash
# create-fifos.sh — (re)create the two named pipes consumed by ffmpeg.
#
# Idempotent: removes any existing fifo of the same name before mkfifo.
# Safe to run on every boot via a systemd oneshot.
#
# Override the directory via STREAM_FIFO_DIR (default /tmp).

set -euo pipefail

FIFO_DIR="${STREAM_FIFO_DIR:-/tmp}"
VIDEO_FIFO="${STREAM_VIDEO_FIFO:-$FIFO_DIR/fe-stream.video}"
AUDIO_FIFO="${STREAM_AUDIO_FIFO:-$FIFO_DIR/fe-stream.audio}"

mkdir -p "$FIFO_DIR"

for fifo in "$VIDEO_FIFO" "$AUDIO_FIFO"; do
    if [[ -e "$fifo" && ! -p "$fifo" ]]; then
        echo "[create-fifos] removing non-fifo at $fifo" >&2
        rm -f "$fifo"
    fi
    if [[ ! -p "$fifo" ]]; then
        mkfifo "$fifo"
        echo "[create-fifos] created $fifo"
    else
        echo "[create-fifos] $fifo already exists"
    fi
done

# ffmpeg opens these for reading; mGBA opens them for writing. On Linux a FIFO
# blocks open() until the other side arrives, so order matters: we run this
# before either service starts, then mGBA opens for write, then ffmpeg opens
# for read. systemd's After=fe-mgba.service on the ffmpeg unit guarantees that.