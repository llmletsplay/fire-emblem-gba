#!/usr/bin/env python3
"""
fe_move_probe6 — diagnose confirm-A cancel after D-pad pathing.

Hypothesis: after LEFT, PlaySt cursor may still sit on Lyn while BmSt.playerCursor
tracks the destination. If confirm uses a stale cursor, A on own tile cancels.

Modes:
  default     — settle → B → A(select) → dump → LEFT → wait → dump+CAP → A → dump+CAP
  --sync-playst — after LEFT, WRITE8 PlaySt X/Y to match BmSt, then A

Usage (on zephyrus, mGBA with socketserver.lua already loaded):
  python tools\\fe_move_probe6.py
  python tools\\fe_move_probe6.py --sync-playst
  python tools\\fe_move_probe6.py --port 8888
"""

from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import time
from pathlib import Path

# FE7 addresses (same as fe_state / game_registry / prior probes)
PLAYST_CURSOR_X = 0x0202BC0A  # u8
PLAYST_CURSOR_Y = 0x0202BC0B  # u8
BMST_CURSOR_X = 0x0202BBCC  # s16
BMST_CURSOR_Y = 0x0202BBCE  # s16
BMST_LOCK = 0x0202BBB9  # u8
BMST_GAME_BITS = 0x0202BBBC  # u8

# Lyn is typically slot 1 in prologue; slot 0 is empty. Array base 0x0202BD08, stride 0x48.
PLAYER_UNITS = 0x0202BD08
UNIT_SIZE = 0x48
LYN_SLOT = 1
OFF_STATE = 0x0C
OFF_X = 0x10
OFF_Y = 0x11
HAS_MOVED_BIT = 0x40

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"


class MgbaClient:
    def __init__(self, host: str, port: int, timeout: float = 8.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        print(f"[probe6] connected {self.host}:{self.port}")

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _recv_exact(self, n: int) -> bytes:
        assert self.sock is not None
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("socket closed")
            buf += chunk
        return buf

    def _flush(self) -> None:
        assert self.sock is not None
        self.sock.setblocking(False)
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    break
        except (BlockingIOError, OSError):
            pass
        finally:
            self.sock.settimeout(self.timeout)

    def send_line(self, line: str, expect_text: bool = False) -> str:
        assert self.sock is not None
        self._flush()
        self.sock.sendall((line.strip() + "\n").encode("utf-8"))
        if not expect_text:
            return ""
        data = bytearray()
        while True:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if b"\n" in chunk:
                break
        return data.decode("utf-8", errors="replace").rstrip("\n")

    def readrange(self, addr: int, length: int) -> bytes:
        assert self.sock is not None
        self._flush()
        self.sock.sendall(f"READRANGE {hex(addr)} {length}\n".encode("utf-8"))
        hdr = self._recv_exact(4)
        size = struct.unpack(">I", hdr)[0]
        return self._recv_exact(size)

    def write8(self, addr: int, value: int) -> str:
        return self.send_line(f"WRITE8 {hex(addr)} {value & 0xFF}", expect_text=True)

    def cap_png(self, out_path: Path) -> None:
        """Request CAP (ARGB8888) and write a minimal PNG via stdlib only."""
        assert self.sock is not None
        self._flush()
        self.sock.sendall(b"CAP\n")
        hdr = self._recv_exact(4)
        if hdr.startswith(b"ERR"):
            rest = self.sock.recv(256)
            raise RuntimeError(f"CAP error: {hdr + rest!r}")
        size = struct.unpack(">I", hdr)[0]
        data = self._recv_exact(size)
        # Guess dimensions: GBA = 240x160 = 153600 pixels * 4 = 614400
        if size % 4 != 0:
            raise RuntimeError(f"CAP size not divisible by 4: {size}")
        pixels = size // 4
        if pixels == 240 * 160:
            w, h = 240, 160
        else:
            # fallback square-ish
            w = int(pixels ** 0.5)
            h = pixels // w
        raw = bytearray()
        # CAP is ARGB big-endian per pixel; PNG wants RGBA
        for i in range(0, size, 4):
            a, r, g, b = data[i], data[i + 1], data[i + 2], data[i + 3]
            raw.extend((r, g, b, a))
        _write_png(out_path, w, h, bytes(raw))
        print(f"[probe6] CAP -> {out_path} ({w}x{h})")

    def wait_queue_complete(self, timeout: float = 8.0) -> bool:
        assert self.sock is not None
        deadline = time.monotonic() + timeout
        buf = bytearray()
        old = self.sock.gettimeout()
        try:
            while time.monotonic() < deadline:
                self.sock.settimeout(min(1.0, max(0.05, deadline - time.monotonic())))
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    return False
                buf.extend(chunk)
                if b"QUEUE_COMPLETE" in buf:
                    return True
            return False
        finally:
            try:
                self.sock.settimeout(old)
            except OSError:
                pass

    def loadstate(self, slot: int = 0) -> str:
        return self.send_line(f"LOADSTATE {slot}", expect_text=True)

    def press(self, key: str, wait: float = 0.35) -> None:
        # Trailing semicolon puts the key on the lua input queue (QUEUE_COMPLETE).
        token = key if key.endswith(";") else f"{key};"
        self.send_line(token)
        ok = self.wait_queue_complete(timeout=max(4.0, wait + 3.0))
        if not ok:
            print(f"[probe6] WARN: no QUEUE_COMPLETE after {token!r}")
        time.sleep(wait)


def _write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    stride = width * 4
    raw = b"".join(b"\x00" + rgba[y * stride : (y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def u8(data: bytes, off: int = 0) -> int:
    return data[off]


def s16(data: bytes, off: int = 0) -> int:
    return struct.unpack_from("<h", data, off)[0]


def dump_state(client: MgbaClient, label: str) -> dict:
    play = client.readrange(PLAYST_CURSOR_X, 2)
    bm = client.readrange(BMST_CURSOR_X, 4)
    lock = client.readrange(BMST_LOCK, 1)
    bits = client.readrange(BMST_GAME_BITS, 1)
    unit_base = PLAYER_UNITS + LYN_SLOT * UNIT_SIZE
    unit = client.readrange(unit_base, UNIT_SIZE)
    state = struct.unpack_from("<I", unit, OFF_STATE)[0]
    info = {
        "label": label,
        "playst": (u8(play, 0), u8(play, 1)),
        "bmst": (s16(bm, 0), s16(bm, 2)),
        "lock": u8(lock),
        "game_bits": u8(bits),
        "lyn_xy": (unit[OFF_X], unit[OFF_Y]),
        "lyn_state": state,
        "lyn_hasMoved": bool(state & HAS_MOVED_BIT),
        "lyn_base": hex(unit_base),
    }
    line = (
        f"[{label}] PlaySt={info['playst']} BmSt={info['bmst']} "
        f"lock={info['lock']} bits=0x{info['game_bits']:02X} "
        f"Lyn@={info['lyn_xy']} hasMoved={info['lyn_hasMoved']} state=0x{state:08X}"
    )
    print(line)
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("FE_MGBA_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("FE_MGBA_PORT", "8888")))
    ap.add_argument("--sync-playst", action="store_true", help="WRITE8 PlaySt to BmSt after LEFT")
    ap.add_argument("--left-count", type=int, default=1, help="How many LEFT presses before confirm")
    ap.add_argument("--loadstate", type=int, default=0, help="LOADSTATE slot after connect (-1 to skip)")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    mode = "sync" if args.sync_playst else "plain"
    log_path = LOG_DIR / f"probe6_{mode}_{ts}.txt"
    dumps: list[dict] = []

    client = MgbaClient(args.host, args.port)
    try:
        client.connect()
        if args.loadstate >= 0:
            print(f"[probe6] LOADSTATE {args.loadstate}")
            try:
                print(" ", client.loadstate(args.loadstate))
            except Exception as e:
                print(f"[probe6] LOADSTATE failed: {e}")
            time.sleep(1.5)
        print("[probe6] settle 1.0s")
        time.sleep(1.0)

        print("[probe6] B (cancel any selection)")
        client.press("B", 0.6)
        time.sleep(0.4)

        print("[probe6] A (select unit under cursor)")
        client.press("A", 0.5)
        time.sleep(1.0)
        dumps.append(dump_state(client, "after_select"))

        for i in range(args.left_count):
            print(f"[probe6] LEFT ({i + 1}/{args.left_count})")
            client.press("LEFT", 0.45)
        print("[probe6] wait 1.5s after LEFT for cursor/path settle")
        time.sleep(1.5)
        dumps.append(dump_state(client, "after_LEFT"))
        client.cap_png(LOG_DIR / f"probe6_{mode}_afterLEFT_{ts}.png")

        if args.sync_playst:
            bx, by = dumps[-1]["bmst"]
            # clamp to u8 tile coords
            bx_u8, by_u8 = bx & 0xFF, by & 0xFF
            print(f"[probe6] WRITE8 PlaySt <- BmSt ({bx_u8},{by_u8})")
            print(" ", client.write8(PLAYST_CURSOR_X, bx_u8))
            print(" ", client.write8(PLAYST_CURSOR_Y, by_u8))
            time.sleep(0.2)
            dumps.append(dump_state(client, "after_playst_sync"))

        print("[probe6] A (confirm move)")
        client.press("A", 0.5)
        print("[probe6] wait 2.5s after confirm A")
        time.sleep(2.5)
        dumps.append(dump_state(client, "after_confirm_A"))
        client.cap_png(LOG_DIR / f"probe6_{mode}_afterA_{ts}.png")

    finally:
        client.close()

    lines = []
    for d in dumps:
        lines.append(
            f"{d['label']}: PlaySt={d['playst']} BmSt={d['bmst']} "
            f"Lyn={d['lyn_xy']} hasMoved={d['lyn_hasMoved']} lock={d['lock']}"
        )
    summary = "\n".join(lines) + "\n"
    log_path.write_text(summary + "\nraw=" + repr(dumps) + "\n", encoding="utf-8")
    print(f"[probe6] wrote {log_path}")
    print("--- SUMMARY ---")
    print(summary)

    # Success heuristic for parent agent
    if len(dumps) >= 2:
        before = next(d for d in dumps if d["label"] == "after_LEFT")
        after = dumps[-1]
        moved = after["lyn_xy"] != before["lyn_xy"] or after["lyn_hasMoved"]
        print(f"[probe6] lyn_moved_or_hasMoved={moved}")
        if before["playst"] != before["bmst"]:
            print(
                f"[probe6] CURSOR_DESYNC after LEFT: PlaySt {before['playst']} vs BmSt {before['bmst']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
