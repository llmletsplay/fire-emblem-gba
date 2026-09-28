"""Small client for the repository's mGBA Lua socket protocol."""

from __future__ import annotations

import socket
import struct
import threading
import time
import zlib
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

    def act(
        self,
        buttons: list[str],
        timeout: float = 15.0,
        *,
        hold_frames: int | None = None,
    ) -> None:
        # A semicolon selects the queued-input path even for a single button,
        # which is the only path that returns QUEUE_COMPLETE.
        suffix = f"@{hold_frames}" if hold_frames is not None else ""
        command = ";".join(f"{button}{suffix}" for button in buttons) + ";"
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


def parse_ui_state(
    raw: str,
    *,
    game_state: dict[str, object] | None = None,
    detail: dict[str, object] | None = None,
    screenshot_png: bytes | None = None,
) -> dict[str, object]:
    """Parse STATE and correct FE7 Link Arena's stale battle-flag report.

    The FE7 title screen and Link Arena map can leave the byte read by the
    legacy ``isInBattle`` helper set. Chapter/phase/lock are separate live
    signals, so use them together to distinguish a playable map from battle
    animation. Keep the raw label for diagnosis.
    """
    if raw.startswith("menu:"):
        _, menu_type, selection_raw = (raw.split(":", 2) + [""])[:3]
        try:
            selection: object = int(selection_raw)
        except ValueError:
            selection = selection_raw
        known_menu_types = {
            "unit", "item", "trade", "support", "battle", "repair", "supply",
            "arena", "vendor", "secret", "gameover", "none",
        }
        if (
            menu_type not in known_menu_types
            and screenshot_png is not None
            and detail is not None
        ):
            if (
                _is_unlocked_fe7_link_map(game_state, detail)
                and _link_arena_phase_banner(screenshot_png)
            ):
                return {"name": "phase_transition", "source": "fe7_ch65_player_phase_banner"}
            overlay = _link_arena_overlay_menu(screenshot_png, game_state, detail)
            if overlay is not None:
                return overlay
        if _is_unlocked_fe7_link_map(game_state, detail) and menu_type not in known_menu_types:
            # On the live chapter-65 map, FE7's old menu flag can retain an
            # impossible menu type (observed 0xE1) with selection 48. The
            # five-unit rosters, unlocked battle map, and valid map cursor are
            # stronger evidence. Real, named battle menus still take priority.
            return {"name": "link_arena_map", "raw_name": raw, "source": "fe7_ch65_map"}
        return {"name": "menu", "menu_type": menu_type, "selection": selection}
    if raw == "battle" and game_state and detail:
        phase = game_state.get("phase")
        if (
            game_state.get("chapter") == 65
            and phase in {"player_phase", "npc_phase"}
            and detail.get("locked") is False
        ):
            return {"name": phase, "raw_name": raw, "source": "fe7_ch65_phase"}
    return {"name": raw}


def _is_unlocked_fe7_link_map(
    game_state: dict[str, object] | None,
    detail: dict[str, object] | None,
) -> bool:
    if not game_state or not detail or game_state.get("chapter") != 65 or detail.get("locked") is not False:
        return False
    cursor = detail.get("bm_cursor")
    if not isinstance(cursor, list) or len(cursor) != 2:
        return False
    try:
        x, y = (int(value) for value in cursor)
    except (TypeError, ValueError):
        return False
    if not (0 <= x < 15 and 0 <= y < 10):
        return False
    for key in ("players", "npcs"):
        value = game_state.get(key)
        if not isinstance(value, str) or "/" not in value:
            return False
        try:
            total = int(value.rsplit("/", 1)[1])
        except ValueError:
            return False
        if total != 5:
            return False
    return True


def _link_arena_overlay_menu(
    png: bytes,
    game_state: dict[str, object] | None,
    detail: dict[str, object] | None,
) -> dict[str, object] | None:
    """Recognize FE7 Link Arena's blue weapon panel and selected row.

    The bridge's legacy menu pointer reports ``0xE1:48`` while FE7 displays
    this panel, and marks the map input-locked. The fixed blue-panel geometry
    plus a unique white cursor wedge in the gutter is sufficient evidence to
    report the actual item-menu row; the right-side forecast panel is a
    separate confirm-only screen, and ambiguous panels remain unclassified.
    """
    if not _has_fe7_link_arena_roster(game_state):
        return None
    pixels = _decode_native_png(png)
    if pixels is None:
        return None
    components = _blue_components(pixels)
    # Confirming a weapon returns to the arena map with the selected fighter's
    # FE7 status card open. The panel can be anchored on either edge depending
    # on the linked client's camera layout; a live Zephyrus capture placed it
    # on the left at x=6, y=27. The attack starts only after a second A press
    # from this screen. It is taller than the forecast card (68x80 to 68x93).
    status_panels = [
        box for size, box in components
        if size >= 1500
        and 60 <= box[2] - box[0] + 1 <= 90
        # The card is normally near the top edge. FE7 can place it lower on
        # the second linked client's map camera, where live captures measured
        # a 68x93 panel beginning at y=27.
        and 79 <= box[3] - box[1] + 1 <= 105
        and (box[0] <= 12 or box[0] >= 150)
        and box[1] <= 35
    ]
    if len(status_panels) == 1:
        return {"name": "unit_status", "source": "fe7_ch65_selected_unit_status"}
    if detail is None or detail.get("locked") is not True:
        return None
    forecasts = [
        box for size, box in components
        if size >= 1200
        and 60 <= box[2] - box[0] + 1 <= 90
        and 60 <= box[3] - box[1] + 1 <= 78
        and box[0] >= 144
        and box[1] <= 12
    ]
    if len(forecasts) == 1:
        return {"name": "battle_forecast", "source": "fe7_ch65_forecast"}

    panels = [
        box for size, box in components
        if size >= 500
        and 80 <= box[2] - box[0] + 1 <= 130
        and 55 <= box[3] - box[1] + 1 <= 100
        and box[0] < 144
    ]
    if len(panels) != 1:
        return None
    left, top, right, bottom = panels[0]
    panel_height = bottom - top + 1
    # FE7's Link Arena weapon list uses 16px row spacing. Scan the complete
    # panel before inferring its row count: a 75px crop made the five-row
    # weapon panel look 61px tall, which shifted later selections by one row.
    row_count = round(panel_height / 16.0)
    if not 1 <= row_count <= 5:
        return None
    row = _white_gutter_cursor_row(pixels, left, top, bottom, row_count)
    if row is None:
        return {"name": "menu", "menu_type": "item", "selection": -1,
                "source": "fe7_ch65_weapon_panel"}
    return {"name": "menu", "menu_type": "item", "selection": row,
            "source": "fe7_ch65_weapon_panel"}


def _link_arena_phase_banner(png: bytes) -> bool:
    """Recognize FE7's green 1P/2P phase ribbon over the arena map.

    During this banner, chapter-65 memory already looks like an unlocked map,
    so cursor inputs are ignored even though the legacy bridge reports the
    usual stale ``menu:0xE1:48`` value. The localized bright-green text band
    distinguishes this transition from the combat effects and idle map.
    """
    pixels = _decode_native_png(png)
    if pixels is None:
        return False
    green_pixels = 0
    for y in range(65, 100):
        for x in range(20, 220):
            red, green, blue = _pixel(pixels, x, y)
            if green >= 145 and green > red * 1.28 and green > blue * 1.12:
                green_pixels += 1
    return green_pixels >= 1500


def _has_fe7_link_arena_roster(game_state: dict[str, object] | None) -> bool:
    if not game_state or game_state.get("chapter") != 65:
        return False
    for key in ("players", "npcs"):
        value = game_state.get(key)
        if not isinstance(value, str) or "/" not in value:
            return False
        try:
            total = int(value.rsplit("/", 1)[1])
        except ValueError:
            return False
        if total != 5:
            return False
    return True


def _decode_native_png(png: bytes) -> bytes | None:
    """Decode the bridge's 240x160 RGBA/filter-0 PNG into packed pixels."""
    try:
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            return None
        offset = 8
        compressed = bytearray()
        width = height = depth = color_type = None
        while offset + 12 <= len(png):
            length = struct.unpack_from(">I", png, offset)[0]
            kind = png[offset + 4 : offset + 8]
            data = png[offset + 8 : offset + 8 + length]
            offset += length + 12
            if kind == b"IHDR":
                width, height, depth, color_type = struct.unpack_from(">IIBB", data)
            elif kind == b"IDAT":
                compressed.extend(data)
            elif kind == b"IEND":
                break
        if (width, height, depth, color_type) != (240, 160, 8, 6):
            return None
        rows = zlib.decompress(bytes(compressed))
        stride = width * 4
        if len(rows) != height * (stride + 1):
            return None
        packed = bytearray(width * height * 4)
        for y in range(height):
            row = y * (stride + 1)
            if rows[row] != 0:
                return None
            packed[y * stride : (y + 1) * stride] = rows[row + 1 : row + 1 + stride]
        return bytes(packed)
    except (ValueError, zlib.error, struct.error):
        return None


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * 240 + x) * 4
    return pixels[offset], pixels[offset + 1], pixels[offset + 2]


def _blue_components(pixels: bytes) -> list[tuple[int, tuple[int, int, int, int]]]:
    blue = {
        (x, y)
        for y in range(120)
        for x in range(240)
        for red, green, value in [_pixel(pixels, x, y)]
        if value > red + 20 and value > green + 10 and red < 140 and green < 160
    }
    result = []
    while blue:
        start = blue.pop()
        stack = [start]
        count = 1
        left = right = start[0]
        top = bottom = start[1]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor not in blue:
                    continue
                blue.remove(neighbor)
                stack.append(neighbor)
                count += 1
                left, right = min(left, neighbor[0]), max(right, neighbor[0])
                top, bottom = min(top, neighbor[1]), max(bottom, neighbor[1])
        result.append((count, (left, top, right, bottom)))
    return result


def _white_gutter_cursor_row(
    pixels: bytes, left: int, top: int, bottom: int, row_count: int
) -> int | None:
    bright = {
        (x, y)
        for y in range(max(0, top + 1), min(120, bottom))
        for x in range(max(0, left - 16), left)
        for red, green, blue in [_pixel(pixels, x, y)]
        if min(red, green, blue) >= 190 and max(red, green, blue) - min(red, green, blue) <= 55
    }
    candidates = []
    while bright:
        start = bright.pop()
        stack = [start]
        points = [start]
        while stack:
            x, y = stack.pop()
            for neighbor in (
                (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                (x + 1, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1),
            ):
                if neighbor in bright:
                    bright.remove(neighbor)
                    stack.append(neighbor)
                    points.append(neighbor)
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        width, height = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        gap = left - max(xs)
        if len(points) >= 14 and 4 <= width <= 12 and 4 <= height <= 12 and 1 <= gap <= 9:
            candidates.append(sum(ys) / len(ys))
    if len(candidates) != 1:
        return None
    row = int((candidates[0] - top) * row_count / (bottom - top + 1))
    return row if 0 <= row < row_count else None


def parse_detail(raw: str) -> dict[str, object]:
    """Parse FE7_DETAIL key/value fields, including the battle-map cursor."""
    fields: dict[str, object] = {}
    for item in raw.split("|")[1:]:
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key in {"cursor", "bm_cursor", "bm_camera"}:
            try:
                fields[key] = [int(part) for part in value.split(",", 1)]
            except ValueError:
                fields[key] = value
        elif key in {"phase_raw", "bm_state"}:
            try:
                fields[key] = int(value, 16)
            except ValueError:
                fields[key] = value
        elif key in {"chapter", "turn", "taken_action", "players_alive", "enemies_alive"}:
            try:
                fields[key] = int(value)
            except ValueError:
                fields[key] = value
        elif key == "locked":
            fields[key] = value not in {"0", "N", "false", "False"}
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
