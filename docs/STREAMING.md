# FE GBA — Live RTMP streaming setup

Push the AI play-through of Fire Emblem GBA to Twitch / YouTube / Kick from
a single small Vultr box. AI inference runs through the MiniMax Code API —
the server only runs mGBA + Python + ffmpeg, no GPU.

## Recommended server

| Plan | vCPU | RAM | Price | Why |
|---|---|---|---|---|
| **vhf-2c-4gb** | 2 | 4 GB | ~$27/mo | Single-thread perf matters (x264, mGBA). 2 cores let one serve ffmpeg, the other serve mGBA + Python. |

Pick a Vultr DC near your viewers (LA / NJ / Chicago for US, Frankfurt for EU,
Tokyo for JP). Ubuntu 24.04 LTS.

## Architecture

```
┌──── Vultr vhf-2c-4gb (Ubuntu 24.04) ────────────────────────────────┐
│                                                                     │
│  mgba-qt  (QT_QPA_PLATFORM=offscreen)                                │
│    └─ lua/stream_wrapper.lua                                         │
│       ├─ dofile("lua/socketserver.lua")  ← existing TCP control      │
│       ├─ frame callback  → raw RGB24 → /tmp/fe-stream.video (fifo)   │
│       └─ samples callback → int16 stereo → /tmp/fe-stream.audio fifo │
│                                                                     │
│  Python  src/core/run.py --auto                                      │
│    └─ Reads game state from TCP socket, calls MiniMax Code API,      │
│       sends button presses back to mGBA                             │
│                                                                     │
│  ffmpeg                                                            │
│    └─ Reads both FIFOs, scales 240×160 → 1920×1080 (lanczos,         │
│       3:2 letterbox), encodes libx264 -preset veryfast, muxes       │
│       AAC audio, pushes FLV to RTMP_URL/STREAM_KEY                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## One-time server setup

```bash
# 1. System packages
sudo apt update && sudo apt install -y --no-install-recommends \
    build-essential cmake pkg-config git ca-certificates \
    libpng-dev libzip-dev libedit-dev libqt5opengl5-dev \
    libSDL2-dev libzstd-dev ffmpeg python3 python3-venv python3-dev \
    rsync
```

```bash
# 2. Build mGBA from source (apt's mGBA is too old for the streaming hooks)
cd /tmp
git clone https://github.com/mgba-emu/mgba.git
cd mgba
cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DBUILD_QT=ON -DBUILD_SDL=ON -DBUILD_LUA=ON
cmake --build build -j$(nproc)
sudo cmake --install build
which mgba-qt   # should print /usr/local/bin/mgba-qt
```

```bash
# 3. Create the service user
sudo useradd --system --no-create-home --shell /usr/sbin/nologin fe
sudo mkdir -p /opt/fe-gba /var/log/fe-gba
sudo chown fe:fe /var/log/fe-gba
```

```bash
# 4. Deploy the repo
sudo rsync -a --delete \
    --exclude='.git' --exclude='venv' --exclude='node_modules' \
    --exclude='logs' --exclude='screenshots' \
    --exclude='.env' --exclude='*.gba' --exclude='.phantasy' --exclude='config' \
    /local/path/to/fire-emblem-gba/ /opt/fe-gba/

# Drop your legally-obtained ROM in place (NOT committed to the repo):
sudo -u fe cp /local/FE7.gba /opt/fe-gba/roms/FE7.gba
sudo chmod 644 /opt/fe-gba/roms/FE7.gba
```

```bash
# 5. Create .env from example and edit it
sudo -u fe cp /opt/fe-gba/.env.example /opt/fe-gba/.env
sudo chmod 600 /opt/fe-gba/.env
sudo -u fe $EDITOR /opt/fe-gba/.env
```

Required entries in `.env`:

```bash
ROM_FILE=FE7.gba
FE_GAME=fe7
LLM_PROVIDER=MINIMAX            # or whatever your inference backend is
MINIMAX_API_KEY=sk-cp-...
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_SUPPORTS_REASONING=true

# Streaming — fill these in
RTMP_URL=rtmp://live.twitch.tv/app
STREAM_KEY=live_1234567890_abcdef...
```

```bash
# 6. Build the Python venv (orchestrator + memory readers)
sudo -u fe bash -c '
  cd /opt/fe-gba
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
'

# 7. Install systemd units
cd /opt/fe-gba
sudo bash scripts/stream/install-systemd.sh
```

## Daily operation

```bash
# Start the whole stack
sudo systemctl start fe-stream.target

# Watch the combined live log
sudo journalctl -u fe-mgba -u fe-backend -u fe-ffmpeg -f

# Or the file logs
sudo tail -F /var/log/fe-gba/{mgba,backend,ffmpeg}.log

# Stop
sudo systemctl stop fe-stream.target

# Status of every component
systemctl status fe-romfetch fe-mgba fe-backend fe-ffmpeg fe-stream.target

# Just the supervisor's restart decisions
sudo tail -F /var/log/fe-gba/supervisor.log
```

## Smoke-test the pipeline WITHOUT going live

If you want to verify the encode path before pointing at Twitch:

```bash
# Run the stream pipeline against a local file instead of RTMP
RTMP_URL="" STREAM_KEY="" \
ffmpeg -hide_banner \
    -f rawvideo -pix_fmt rgb24 -s 240x160 -r 60 -i /tmp/fe-stream.video \
    -f s16le -ar 32768 -ac 2 -i /tmp/fe-stream.audio \
    -filter_complex "[0:v]scale=1620:1080:flags=lanczos,pad=1920:1080:150:0:black[v];[1:a]aresample=44100[a]" \
    -map "[v]" -map "[a]" \
    -c:v libx264 -preset veryfast -tune animation \
    -b:v 6000k -maxrate 6000k -bufsize 12000k -g 60 -pix_fmt yuv420p \
    -c:a aac -b:a 128k \
    /tmp/test-stream.mp4
```

If a 30-second sample of `/tmp/test-stream.mp4` looks right, you're good.

## Tuning notes

| Knob | What it does | Where |
|---|---|---|
| `STREAM_BITRATE` | Output video bitrate. 6000k is a sweet spot for 1080p; drop to 4500k if Twitch caps you. | `.env` |
| `STREAM_PRESET` | x264 speed/quality tradeoff. `veryfast` is the floor; `superfast`/`ultrafast` if the box struggles. | `.env` |
| `STREAM_RESOLUTION` | Output canvas. Use `1280x720` for low-bandwidth restreams. | `.env` |
| `STREAM_FPS` | 30 vs 60. GBA is 59.7 fps native; 60 is fine but 30 halves encode cost. | `.env` |
| `STREAM_AUDIO_RATE` | AAC bitrate. 128k is overkill for GBA chiptune; 96k is fine. | `.env` |
| GOP (`-g` in ffmpeg) | Currently fixed to `STREAM_FPS` (1-second GOP). Faster reconnects on viewer side. | ffmpeg-stream.sh |
| `STREAM_TUNE` | x264 `-tune`. `animation` (default, best for game art) or `zerolatency` (disables lookahead). | `.env` |
| `STREAM_LOW_LATENCY` | `on` flips to `-bf 0 -flush_packets 1 -tune zerolatency` for ~2-3s RTMP latency. | `.env` |

## Low-latency mode

Set `STREAM_LOW_LATENCY=on` in `.env` when you want chat to react to the AI's
in-game moves within a couple of seconds. Three things change:

| Flag | Default | Low-latency | Effect |
|---|---|---|---|
| `-bf` | 2 | 0 | Removes B-frame reordering delay (~40ms at 60fps) |
| `-flush_packets` | (default) | `1` | Forces ffmpeg to flush the muxer after each packet instead of batching |
| `-tune` | `animation` | `zerolatency` | Disables lookahead, motion estimation skips for low-latency modes |

Trade-off: ~10-15% worse compression at the same bitrate. If you start seeing
Twitch capping you at 6000 kbps, lower `STREAM_BITRATE` to 4500k.

> **True sub-2-second latency** requires Twitch Enhanced Broadcasting (LL-HLS
> over WebSocket) which is a completely different ingest protocol. RTMP with
> these settings is the practical floor for an ffmpeg-only pipeline.

## Supervisor — auto-restart on RTMP drop

The systemd unit `fe-ffmpeg.service` no longer runs ffmpeg directly. It runs
`scripts/stream/supervisor-stream.sh`, a thin wrapper that:

- Restarts ffmpeg on any non-zero exit (network hiccup, Twitch ingest failover,
  brief server restart, etc.) with exponential backoff capped at `STREAM_BACKOFF_MAX`.
- Tracks "stable runtime" — only runs lasting less than `STREAM_STABLE_RUNTIME`
  (default 60s) increment a rapid-failure counter.
- After `STREAM_MAX_RAPID_FAILS` consecutive short runs (default 5), the
  supervisor tails the last 30 lines of `ffmpeg.log` to its own log, then exits
  non-zero. systemd's `Restart=on-failure` then schedules another full restart
  after `RestartSec`, so the stream recovers automatically once the operator
  fixes whatever's wrong (bad `RTMP_URL`, expired `STREAM_KEY`, etc.).
- Forwards SIGTERM from systemd to ffmpeg so a clean `systemctl stop` ends
  the ffmpeg child instead of orphaning it.

Watch the supervisor's decisions:

```bash
sudo tail -F /var/log/fe-gba/supervisor.log
```

A healthy run looks like:

```
[supervisor 2026-09-19T12:00:00-04:00] starting ffmpeg (attempt 1, rapid_fails=0)
[supervisor 2026-09-19T14:23:11-04:00] ffmpeg exited rc=1 after 8191s
[supervisor 2026-09-19T14:23:11-04:00]   ↳ was stable; resetting rapid_fails=0
[supervisor 2026-09-19T14:23:11-04:00]   ↳ backing off 5s before restart
[supervisor 2026-09-19T14:23:16-04:00] starting ffmpeg (attempt 2, rapid_fails=0)
```

A bad-config loop looks like:

```
[supervisor 2026-09-19T14:23:11-04:00] starting ffmpeg (attempt 1, rapid_fails=0)
[supervisor 2026-09-19T14:23:11-04:00] ffmpeg exited rc=1 after 2s
[supervisor 2026-09-19T14:23:11-04:00]   ↳ short run (2 < 60); rapid_fails=1/5
[supervisor 2026-09-19T14:23:11-04:00]   ↳ backing off 10s before restart
... (5x) ...
[supervisor 2026-09-19T14:23:11-04:00] FATAL — 5 rapid failures in a row; likely config error
[supervisor 2026-09-19T14:23:11-04:00] FATAL — supervisor exiting non-zero; systemd Restart=on-failure will pick up
```

After seeing the FATAL line, check `ffmpeg.log` for the actual reason, fix
`.env`, then `systemctl reset-failed fe-ffmpeg && systemctl start fe-stream.target`.

## Troubleshooting

**No video on stream:**
1. Check `journalctl -u fe-mgba` — should see `[STREAM] hooks registered.` and `[STREAM] video FIFO open`.
2. Check `journalctl -u fe-ffmpeg` — should see `Stream mapping:` and `frame= ...`.
3. `ls -la /tmp/fe-stream.video` — should be a FIFO (`p` in mode).
4. `cat /tmp/fe-stream.video | wc -c` while streaming — should be growing fast. If zero, mGBA isn't writing.

**Stream connects but is black:**
- `QT_QPA_PLATFORM=offscreen` is missing from the environment. Verify with `systemctl show fe-mgba -p Environment`.
- mGBA window is rendering to a real but invisible GL context — if your Qt install lacks the offscreen platform plugin (`libqt5gui5`), reinstall Qt.

**Audio glitches / out of sync:**
- The mGBA `samples` callback granularity (~32 ms) doesn't perfectly align with video frames. ffmpeg's `aresample=44100` handles drift, but if drift grows over time, raise `-bufsize` in ffmpeg-stream.sh.
- For tighter sync, force audio buffer flush via `-af "aresample=async=1:first_pts=0"` instead of bare `aresample=44100`.

**Emulator freezes on a frame:**
- The video FIFO is full because ffmpeg stalled. Check `journalctl -u fe-ffmpeg` for `Conversion failed!` or dropped frames.
- Quick fix: lower `STREAM_BITRATE` to 4500k or raise `STREAM_PRESET` to `superfast`.

**CPU pinned at 100%:**
- `CPUQuota=200%` on the ffmpeg unit caps it. If you're regularly hitting that, your box is undersized for the chosen preset. Move to `vhf-4c-8gb` or drop to 720p.

**Stream keeps dropping and reconnecting every few minutes:**
- Likely a Twitch ingest issue or upstream network blip. The supervisor will keep restarting, so the stream stays up — but check `supervisor.log` for restart frequency.
- If restarts are every ~5-10s, the box can't keep up — drop `STREAM_PRESET` to `superfast` or `STREAM_RESOLUTION` to `1280x720`.
- If restarts are every few hours, that's normal Twitch behavior and the supervisor is doing its job.

**Supervisor FATAL'd — 5 rapid failures:**
- See the section above. Read `/var/log/fe-gba/ffmpeg.log` (last 30 lines were also captured in `supervisor.log`), fix the root cause in `.env`, then `systemctl reset-failed fe-ffmpeg && systemctl start fe-stream.target`.

## Files added by this setup

```
lua/stream_wrapper.lua                 # mGBA entry point — dofile()s socketserver.lua
scripts/stream/create-fifos.sh         # one-shot FIFO maker (systemd oneshot)
scripts/stream/ffmpeg-stream.sh        # the ffmpeg invocation (called by supervisor)
scripts/stream/supervisor-stream.sh    # wraps ffmpeg with restart + backoff + circuit breaker
scripts/stream/start-stream.sh         # manual stack launcher (no systemd)
scripts/stream/install-systemd.sh      # copies units into /etc/systemd/system/
scripts/systemd/fe-romfetch.service    # one-shot: FIFOs + log dir
scripts/systemd/fe-mgba.service        # mGBA + Lua wrapper
scripts/systemd/fe-backend.service     # Python orchestrator
scripts/systemd/fe-ffmpeg.service      # supervisor-stream.sh (not raw ffmpeg)
scripts/systemd/fe-stream.target       # rolls the four services up into one start/stop
docs/STREAMING.md                      # this file
.env.example                           # extended with STREAM_* + RTMP_* keys
```

The existing `lua/socketserver.lua` (TCP control), `src/core/run.py --auto`
(Python orchestrator), and the local `fe-client` web viewer are untouched —
streaming is purely additive.