-- stream_wrapper.lua  ── adds live RTMP streaming on top of socketserver.lua
--
-- This script is a thin mGBA entry point. It:
--   1. Loads the existing TCP control server (socketserver.lua + memory readers).
--   2. Hooks per-frame callbacks that dump the framebuffer as raw RGB24 into a
--      named pipe (default: /tmp/fe-stream.video).
--   3. Hooks per-audio-buffer callbacks that dump int16 stereo samples into a
--      second named pipe (default: /tmp/fe-stream.audio).
--
-- ffmpeg consumes both pipes and pushes RTMP to Twitch / YouTube / Kick.
-- See scripts/systemd/* for the systemd unit layout.
--
-- Override defaults via environment:
--   STREAM_FIFO_DIR   - directory for the two FIFOs (default /tmp)
--   STREAM_VIDEO_FIFO - video FIFO path (default $STREAM_FIFO_DIR/fe-stream.video)
--   STREAM_AUDIO_FIFO - audio FIFO path (default $STREAM_FIFO_DIR/fe-stream.audio)
--   STREAM_VIDEO      - "on" (default) / "off" to disable video dump
--   STREAM_AUDIO      - "on" (default) / "off" to disable audio dump
--
-- Launch from the project root so the dofile() paths resolve:
--   mgba-qt --script lua/stream_wrapper.lua roms/FE7.gba

local env = os.getenv

local FIFO_DIR     = env("STREAM_FIFO_DIR") or "/tmp"
local VIDEO_FIFO   = env("STREAM_VIDEO_FIFO") or (FIFO_DIR .. "/fe-stream.video")
local AUDIO_FIFO   = env("STREAM_AUDIO_FIFO") or (FIFO_DIR .. "/fe-stream.audio")
local VIDEO_ON     = (env("STREAM_VIDEO") or "on") ~= "off"
local AUDIO_ON     = (env("STREAM_AUDIO") or "on") ~= "off"

local VIDEO_W, VIDEO_H = 240, 160   -- GBA native framebuffer

console:log("[STREAM] wrapper booting, fifos: " .. VIDEO_FIFO .. " + " .. AUDIO_FIFO)

-- ---------------------------------------------------------------------------
--  Load the existing TCP server + memory readers. They bind to LISTEN_PORT
--  (default 8888) and the Python orchestrator talks to that port. We do not
--  touch any of the existing logic — this wrapper only adds streaming hooks.
-- ---------------------------------------------------------------------------
dofile("lua/socketserver.lua")

console:log("[STREAM] socketserver.lua loaded, attaching streaming hooks.")

-- ---------------------------------------------------------------------------
--  Lookup tables for fast RGB serialization (avoid string.format per pixel).
-- ---------------------------------------------------------------------------
local rgb_lookup = {}
for i = 0, 255 do rgb_lookup[i] = string.char(i) end

local video_file, audio_file
local frames_written = 0
local audio_bytes    = 0

local function open_video_pipe()
    if not VIDEO_ON then return end
    video_file = io.open(VIDEO_FIFO, "wb")
    if not video_file then
        console:log("[STREAM] ERROR: cannot open video FIFO " .. VIDEO_FIFO)
        return
    end
    video_file:setvbuf("no")   -- flush every frame immediately
    console:log("[STREAM] video FIFO open (unbuffered): " .. VIDEO_FIFO)
end

local function open_audio_pipe()
    if not AUDIO_ON then return end
    audio_file = io.open(AUDIO_FIFO, "wb")
    if not audio_file then
        console:log("[STREAM] ERROR: cannot open audio FIFO " .. AUDIO_FIFO)
        return
    end
    audio_file:setvbuf("no")
    console:log("[STREAM] audio FIFO open (unbuffered): " .. AUDIO_FIFO)
end

local function close_pipes()
    if video_file then pcall(function() video_file:close() end); video_file = nil end
    if audio_file then pcall(function() audio_file:close() end); audio_file = nil end
end

-- ---------------------------------------------------------------------------
--  Per-frame hook: serialize current framebuffer as raw RGB24 (3 bytes/pixel)
--  row-major, top-to-bottom. Total payload: 240 * 160 * 3 = 115_200 bytes.
-- ---------------------------------------------------------------------------
local function stream_frame()
    if not video_file then return end
    local img = emu:screenshotToImage()
    if not img then return end
    local w, h = img.width, img.height
    if w ~= VIDEO_W or h ~= VIDEO_H then
        -- Only warn once per size mismatch
        if frames_written == 0 then
            console:log(string.format(
                "[STREAM] frame size mismatch: got %dx%d, expected %dx%d",
                w, h, VIDEO_W, VIDEO_H))
        end
        return
    end
    local parts = {}
    for y = 0, h - 1 do
        for x = 0, w - 1 do
            local argb = img:getPixel(x, y)         -- 0xAARRGGBB
            local r = (argb >> 16) & 0xFF
            local g = (argb >>  8) & 0xFF
            local b =  argb        & 0xFF
            parts[#parts + 1] = rgb_lookup[r]
            parts[#parts + 1] = rgb_lookup[g]
            parts[#parts + 1] = rgb_lookup[b]
        end
    end
    -- Blocking write. If ffmpeg stalls for >~16ms this will freeze mGBA. On
    -- the recommended vhf-2c-4gb this is not expected to happen; if it ever
    -- does, drop a frame here and re-issue the write on the next tick.
    local ok, err = pcall(function()
        video_file:write(table.concat(parts))
    end)
    if ok then
        frames_written = frames_written + 1
    else
        console:log("[STREAM] video write failed: " .. tostring(err))
        pcall(function() video_file:close() end)
        video_file = nil
    end
end

-- ---------------------------------------------------------------------------
--  Per-audio-buffer hook. mGBA calls this with a table containing:
--     buf.count   - samples per channel (e.g. 1024)
--     buf.buffer  - raw int16 stereo, L/R interleaved, little-endian
--  Native GBA sample rate is 32768 Hz; mGBA forwards at that rate.
--  Total payload per call: count * 2 channels * 2 bytes.
-- ---------------------------------------------------------------------------
local function stream_samples(buf)
    if not audio_file then return end
    if not buf or not buf.buffer or not buf.count or buf.count <= 0 then return end
    local ok, err = pcall(function()
        audio_file:write(buf.buffer)
    end)
    if ok then
        audio_bytes = audio_bytes + #buf.buffer
    else
        console:log("[STREAM] audio write failed: " .. tostring(err))
        pcall(function() audio_file:close() end)
        audio_file = nil
    end
end

-- ---------------------------------------------------------------------------
--  Lifecycle: open pipes after the emulator finishes loading the ROM,
--  close them on shutdown so ffmpeg sees EOF and exits cleanly.
-- ---------------------------------------------------------------------------
callbacks:add("start",  function() open_video_pipe(); open_audio_pipe() end)
callbacks:add("frame",  stream_frame)
callbacks:add("samples", stream_samples)
callbacks:add("shutdown", close_pipes)

-- Periodic self-report so you can see the counters in mGBA's log without
-- attaching a debugger. Every ~10 seconds at 60fps.
local report_every = 600
local since_report = 0
callbacks:add("frame", function()
    since_report = since_report + 1
    if since_report >= report_every then
        since_report = 0
        console:log(string.format(
            "[STREAM] alive — %d frames, %d audio bytes written",
            frames_written, audio_bytes))
    end
end)

console:log("[STREAM] hooks registered. Streaming "
    .. (VIDEO_ON and "video" or "no video") .. " + "
    .. (AUDIO_ON and "audio" or "no audio") .. ".")