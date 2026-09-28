"""Fail-closed reader for FE7 Link Arena's final result screen."""

from __future__ import annotations

import hashlib
from typing import Any

from .bridge import _decode_native_png


# Calibrated from the two archived FE7 result screens. Each digit is the
# 6x8 cyan-ink mask rendered by the score font after the screen palette has
# been applied. Unknown glyphs are rejected rather than guessed.
_DIGIT_MASKS: dict[str, tuple[str, ...]] = {
    "0": (
        "..###.", ".#..##", "##..##", "##..##", "##..##", "##..##", "##..#.", ".###..",
    ),
    "2": (
        ".####.", "##..##", "#...##", "....#.", "...#..", "..#...", ".#...#", "######",
    ),
    "3": (
        ".#####", "#...#.", "...#..", "..###.", "....##", ".#..##", "##..#.", ".###..",
    ),
    "4": (
        "....#.", "...##.", "..###.", ".#.##.", "#..###", "#####.", "...##.", "..####",
    ),
    "5": (
        ".#...#", ".####.", ".#....", ".####.", "....##", ".#..##", "##..#.", ".###..",
    ),
    "6": (
        "..###.", ".#....", ".#....", "#####.", "##..##", "##..##", "##..#.", ".###..",
    ),
    "7": (
        ".#####", "#...#.", "....#.", "...#..", "...#..", "..##..", "..##..", "..#...",
    ),
    "8": (
        ".###..", "#...#.", "#...#.", ".###..", ".####.", "#...##", "#...#.", ".###..",
    ),
}
_DIGIT_BITS = {
    digit: tuple(character == "#" for row in rows for character in row)
    for digit, rows in _DIGIT_MASKS.items()
}
_POINTS_BONUS_PANEL_SHA256 = "be917b7a048211a9278f7986d39f0368e9afd8ed13b2e62537eabe0d2474b3d4"


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * 240 + x) * 4
    return pixels[offset], pixels[offset + 1], pixels[offset + 2]


def is_points_bonus_transition(png: bytes) -> bool:
    """Recognize the exact FE7 30-point award panel seen at match end."""
    pixels = _decode_native_png(png)
    if pixels is None:
        return False
    panel = b"".join(
        pixels[(y * 240 + 64) * 4:(y * 240 + 239) * 4]
        for y in range(90, 119)
    )
    return hashlib.sha256(panel).hexdigest() == _POINTS_BONUS_PANEL_SHA256


def _cyan_components(
    pixels: bytes, *, y_start: int, y_stop: int,
) -> list[tuple[int, int, int, int, tuple[bool, ...]]]:
    points = {
        (x, y)
        for y in range(y_start, y_stop)
        for x in range(73, 95)
        for red, green, blue in (_pixel(pixels, x, y),)
        if red > 150 and green > 220 and blue > 220
    }
    components = []
    while points:
        start = points.pop()
        stack = [start]
        members = [start]
        while stack:
            x, y = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    neighbor = (x + dx, y + dy)
                    if neighbor in points:
                        points.remove(neighbor)
                        stack.append(neighbor)
                        members.append(neighbor)
        left = min(x for x, _ in members)
        right = max(x for x, _ in members)
        top = min(y for _, y in members)
        bottom = max(y for _, y in members)
        if right - left != 5 or bottom - top != 7:
            continue
        member_set = set(members)
        mask = tuple(
            (left + column, top + row) in member_set
            for row in range(8)
            for column in range(6)
        )
        components.append((left, top, right, bottom, mask))
    return sorted(components, key=lambda value: value[0])


def _read_score_row(pixels: bytes, *, y_start: int, y_stop: int) -> int | None:
    components = _cyan_components(pixels, y_start=y_start, y_stop=y_stop)
    if len(components) != 3:
        return None
    digits: list[str] = []
    for _, _, _, _, mask in components:
        distances = sorted(
            (sum(actual != expected for actual, expected in zip(mask, _DIGIT_BITS[digit])), digit)
            for digit in _DIGIT_BITS
        )
        # Exact templates are required. This intentionally declines scores
        # containing an uncalibrated glyph rather than risking a false total.
        if distances[0][0] != 0 or distances[0][0] == distances[1][0]:
            return None
        digits.append(distances[0][1])
    score = int("".join(digits))
    return score if score >= 0 else None


def _seat_badge(pixels: bytes, *, y_start: int, y_stop: int) -> str | None:
    blue = green = 0
    for y in range(y_start, y_stop):
        for x in range(72, 109):
            red, channel_green, channel_blue = _pixel(pixels, x, y)
            if channel_blue > red + 25 and channel_blue > channel_green + 10:
                blue += 1
            if channel_green > red + 20 and channel_green > channel_blue + 10:
                green += 1
    if blue > 100 and green < 20:
        return "1P"
    if green > 80 and blue < 100:
        return "2P"
    return None


def read_final_result_screen(png: bytes) -> dict[str, Any] | None:
    """Parse the FE7 first/second-place screen; return ``None`` if uncertain.

    Only the visible final result screen is accepted. Intermediate points
    panels, including the terminal 30-point award transition, are not results.
    """
    pixels = _decode_native_png(png)
    if pixels is None:
        return None

    first_seat = _seat_badge(pixels, y_start=53, y_stop=68)
    second_seat = _seat_badge(pixels, y_start=101, y_stop=116)
    first_points = _read_score_row(pixels, y_start=69, y_stop=79)
    second_points = _read_score_row(pixels, y_start=117, y_stop=127)
    if (
        first_seat is None
        or second_seat is None
        or first_seat == second_seat
        or first_points is None
        or second_points is None
        or first_points <= second_points
    ):
        return None
    return {
        "source": "fe7_final_result_screen",
        "screen_sha256": hashlib.sha256(png).hexdigest(),
        "first_place": {"seat": first_seat, "points": first_points},
        "second_place": {"seat": second_seat, "points": second_points},
        "points_by_seat": {first_seat: first_points, second_seat: second_points},
    }
