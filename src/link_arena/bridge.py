"""Small client for the repository's mGBA Lua socket protocol."""

from __future__ import annotations

import socket
import struct
import threading
import time
from pathlib import Path


class BridgeError(RuntimeError):
    """Raised when an mGBA side does not answer its control bridge."""


class SideBridge:
    def __init__(self, port: int, host: str = "127.0.0.1", timeout: float = 8.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._lock = threading.RLock()

    def _connect(self) -> socket.socket:
        if self._socket is not None:
            return self._socket
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
            return self._socket
        except OSError as exc:
            raise BridgeError(f"mGBA bridge {self.host}:{self.port} is unavailable: {exc}") from exc

    def _discard_connection(self) -> None:
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def close(self) -> None:
        with self._lock:
            self._discard_connection()

    @staticmethod
    def _read_exact(sock: socket.socket, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise BridgeError("mGBA closed the socket before completing a response")
            data.extend(chunk)
        return bytes(data)

    def line(self, command: str) -> str:
        with self._lock:
            sock = self._connect()
            try:
                sock.sendall((command.strip() + "\n").encode("ascii"))
                response = bytearray()
                while b"\n" not in response:
                    chunk = sock.recv(4096)
                    if not chunk:
                        raise BridgeError(f"mGBA closed the socket during {command}")
                    response.extend(chunk)
            except (OSError, BridgeError):
                self._discard_connection()
                raise
        return bytes(response).split(b"\n", 1)[0].decode("utf-8", errors="replace").rstrip("\r")

    def binary(self, command: str) -> bytes:
        with self._lock:
            sock = self._connect()
            try:
                sock.sendall((command.strip() + "\n").encode("ascii"))
                header = self._read_exact(sock, 4)
                if header.startswith(b"ERR"):
                    raise BridgeError(header.decode("ascii", errors="replace"))
                size = struct.unpack(">I", header)[0]
                if size > 8 * 1024 * 1024:
                    raise BridgeError(f"mGBA returned an implausible payload size: {size}")
                return self._read_exact(sock, size)
            except (OSError, BridgeError):
                self._discard_connection()
                raise

    def capture(self, retries: int = 3, retry_delay: float = 0.2) -> bytes:
        last_error: BridgeError | None = None
        for attempt in range(retries):
            try:
                return self.binary("CAP")
            except BridgeError as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(retry_delay)
        raise BridgeError(f"capture failed after {retries} attempts: {last_error}") from last_error

    def read_range(self, address: int, length: int) -> bytes:
        return self.binary(f"READRANGE 0x{address:X} {length}")

    def act(self, buttons: list[str], timeout: float = 15.0) -> None:
        # A semicolon selects the queued-input path even for a single button,
        # which is the only path that returns QUEUE_COMPLETE.
        command = ";".join(buttons) + ";"
        with self._lock:
            sock = self._connect()
            old_timeout = sock.gettimeout()
            try:
                sock.settimeout(timeout)
                sock.sendall((command + "\n").encode("ascii"))
                response = bytearray()
                while b"\n" not in response:
                    chunk = sock.recv(256)
                    if not chunk:
                        raise BridgeError("mGBA closed the socket before the action completed")
                    response.extend(chunk)
            except (OSError, BridgeError):
                self._discard_connection()
                raise
            finally:
                if self._socket is sock:
                    sock.settimeout(old_timeout)
        line = bytes(response).split(b"\n", 1)[0].decode("ascii", errors="replace")
        if line != "QUEUE_COMPLETE":
            raise BridgeError(f"unexpected action completion response: {line!r}")

    def wait_until_ready(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                response = self.line("STATE")
                if response and not response.startswith("ERR"):
                    return
            except (BridgeError, OSError) as exc:
                last_error = exc
            time.sleep(0.25)
        raise BridgeError(f"mGBA bridge on port {self.port} did not become ready: {last_error}")


def parse_game_state(raw: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    for item in raw.split("|")[1:]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key == "cursor":
            try:
                fields[key] = [int(part) for part in value.split(",", 1)]
            except ValueError:
                fields[key] = value
        elif key in {"chapter", "turn"}:
            try:
                fields[key] = int(value)
            except ValueError:
                fields[key] = value
        elif key == "locked":
            fields[key] = value == "Y"
        else:
            fields[key] = value
    fields["game"] = raw.split("|", 1)[0]
    return fields


def parse_units(raw: str) -> list[dict[str, object]]:
    import re

    result: list[dict[str, object]] = []
    for match in re.finditer(r"([PEN]):\{([^}]*)\}", raw):
        allegiance, body = match.groups()
        values = dict(re.findall(r"(\w+)=([^,]+)", body))
        unit: dict[str, object] = {"team": {"P": "player", "E": "enemy", "N": "npc"}[allegiance]}
        for source, target in (("id", "character_id"), ("cls", "class_id")):
            if source in values:
                try:
                    unit[target] = int(values[source])
                except ValueError:
                    unit[target] = values[source]
        if "hp" in values:
            try:
                current, maximum = (int(part) for part in values["hp"].split("/", 1))
                unit["hp"] = {"current": current, "max": maximum}
            except (ValueError, TypeError):
                unit["hp"] = values["hp"]
        pos = re.search(r"pos=\((-?\d+),(-?\d+)\)", body)
        if pos:
            unit["position"] = [int(pos.group(1)), int(pos.group(2))]
        if "moved" in values:
            unit["acted"] = values["moved"] == "Y"
        if "ally" in values:
            try:
                unit["allegiance"] = int(values["ally"], 16)
            except ValueError:
                unit["allegiance"] = values["ally"]
        for source, target in (
            ("lv", "level"), ("exp", "experience"), ("str", "strength"),
            ("skl", "skill"), ("spd", "speed"), ("def", "defense"),
            ("res", "resistance"), ("lck", "luck"),
            ("con_bonus", "constitution_bonus"),
            ("mov_bonus", "movement_bonus"),
        ):
            if source in values:
                try:
                    unit[target] = int(values[source])
                except ValueError:
                    unit[target] = values[source]
        if "state" in values:
            try:
                unit["state_flags"] = int(values["state"], 16)
            except ValueError:
                unit["state_flags"] = values["state"]
        inventory = []
        for slot in range(1, 6):
            raw_item = values.get(f"item{slot}")
            if raw_item is None:
                continue
            try:
                word = int(raw_item, 16)
            except ValueError:
                continue
            if word:
                inventory.append({"id": word & 0xFF, "uses": word >> 8,
                                  "raw": word, "slot": slot - 1})
        if inventory or any(f"item{slot}" in values for slot in range(1, 6)):
            unit["inventory"] = inventory
        result.append(unit)
    return result


def argb_to_png(payload: bytes, width: int = 240, height: int = 160) -> bytes:
    """Encode the bridge's big-endian ARGB pixels as a PNG using stdlib only."""
    import zlib

    expected = width * height * 4
    if len(payload) != expected:
        raise BridgeError(f"expected {expected} screenshot bytes, received {len(payload)}")
    rgba_rows = bytearray()
    for y in range(height):
        rgba_rows.append(0)  # PNG filter: none
        for offset in range(y * width * 4, (y + 1) * width * 4, 4):
            alpha, red, green, blue = payload[offset:offset + 4]
            rgba_rows.extend((red, green, blue, alpha))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rgba_rows)))
        + chunk(b"IEND", b"")
    )
