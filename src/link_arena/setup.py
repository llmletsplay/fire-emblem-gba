"""Fail-closed FE7 title-to-Link-Arena setup for unattended matches.

The setup path is deliberately specific to the prepared FE7 (US) save. Each
direction press is checked against the rendered menu selection; transitions
are recognized from the UI caption region and live chapter/roster state. Any
unrecognized screen stops for supervision before the next input.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import time
import zlib
from typing import Any, Callable

from .control import UnsafeScreen, _MAP_STATES, _ui
from .coordinator import StaleObservation


_HUB_CAPTIONS = {
    "91efe201edc0901ba65876359a66f7b668ba9f73ef3be742f573e627638f2630": 0,
    "bdce63d6e9f9083f74f26e692d12eb7f101b72fe27161ca716674f8a02807ecd": 1,
    "af085bb00cff0e99b47e7b96b811e7e9dfdfd24eac2d2ee234fe82a95aece7bc": 2,
}
_LINK_MODE_CAPTIONS = {
    "f61f7be58f9b156602bd0b7e2aaf4bdd0bb136e433b065f85c910e8dee593af5",
    "5d31e0cc3b580dbe435ec781f95f88b6d4dc0ae2076a7b53704a7eb163ea62d4",
}
_TEAM_SELECT_CAPTIONS = {
    "A": "dcc36f3972bbe94e35ada6df4dcf8c380a00110544dbe6543527c19c577ad198",
    "B": "dcc36f3972bbe94e35ada6df4dcf8c380a00110544dbe6543527c19c577ad198",
}
_LINK_READY_CAPTIONS = {
    "A": "c26f069382a05f0c15a81d6fd3c6e547b3c90c7f64d5e2a49f54aabbca521c82",
    "B": "3ad7fd9c6a9579d295a1c3ed02166993db7c440445c25d17dce137b373ebb875",
}
_FIRST_PLAYER_CAPTIONS = {
    "A": "3ad7fd9c6a9579d295a1c3ed02166993db7c440445c25d17dce137b373ebb875",
    "B": "d1880fd0ddf5ba949f82284d6bc4b37606c78ffafc7d6fec34d05f7a22c71f41",
}


def _png_pixels(observation: dict[str, Any]) -> tuple[int, int, bytes]:
    """Decode screenshots produced by ``argb_to_png`` without image packages."""
    encoded = observation.get("screenshot")
    if not isinstance(encoded, str) or not encoded.startswith("data:image/png;base64,"):
        raise UnsafeScreen("observation has no FE7 PNG screenshot")
    try:
        payload = base64.b64decode(encoded.partition(",")[2], validate=True)
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("invalid PNG signature")
        offset = 8
        compressed = bytearray()
        width = height = bit_depth = color_type = None
        while offset + 12 <= len(payload):
            length = struct.unpack_from(">I", payload, offset)[0]
            kind = payload[offset + 4 : offset + 8]
            data = payload[offset + 8 : offset + 8 + length]
            offset += length + 12
            if kind == b"IHDR":
                width, height, bit_depth, color_type = struct.unpack_from(">IIBB", data)
            elif kind == b"IDAT":
                compressed.extend(data)
            elif kind == b"IEND":
                break
        if (width, height, bit_depth, color_type) != (240, 160, 8, 6):
            raise ValueError("unsupported FE7 screenshot format")
        rows = zlib.decompress(bytes(compressed))
        stride = width * 4
        if len(rows) != height * (stride + 1):
            raise ValueError("truncated FE7 screenshot")
        pixels = bytearray(width * height * 4)
        for y in range(height):
            row_start = y * (stride + 1)
            if rows[row_start] != 0:
                raise ValueError("unexpected PNG row filter")
            pixels[y * stride : (y + 1) * stride] = rows[row_start + 1 : row_start + 1 + stride]
        return width, height, bytes(pixels)
    except (ValueError, zlib.error, struct.error) as exc:
        raise UnsafeScreen(f"could not decode FE7 screenshot: {exc}") from exc


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * 240 + x) * 4
    return pixels[offset], pixels[offset + 1], pixels[offset + 2]


def _blue_menu_bands(pixels: bytes) -> list[tuple[int, int]]:
    """Find FE7's fixed four/five-row title menu geometry.

    Arbitrary blue-run detection mistakes the FE7 title logo and battle UI for
    menu rows. The FE7-US main and Extras menus use fixed 24px row spacing; a
    strong blue fill must be present in every expected row.
    """
    for top, count in ((15, 5), (27, 4)):
        bands = [(top + row * 24, top + row * 24 + 17) for row in range(count)]
        strengths = []
        for row_top, row_bottom in bands:
            blue_pixels = 0
            for y in range(row_top, row_bottom + 1):
                for x in range(55, 185):
                    red, green, blue = _pixel(pixels, x, y)
                    if blue > 55 and blue > red * 1.2 and blue > green * 1.04:
                        blue_pixels += 1
            strengths.append(blue_pixels)
        if min(strengths, default=0) >= 1000:
            return bands
    return []


def _gold_marker_scores(pixels: bytes, bands: list[tuple[int, int]]) -> list[int]:
    scores: list[int] = []
    for top, bottom in bands:
        score = 0
        for y in range(max(0, top - 4), min(160, bottom + 5)):
            for x in (*range(32, 59), *range(180, 208)):
                red, green, blue = _pixel(pixels, x, y)
                if red > 145 and green > 95 and red > green * 1.12 and blue < 170:
                    score += 1
        scores.append(score)
    return scores


def title_menu_state(observation: dict[str, Any]) -> tuple[str, int] | None:
    """Return (main|extras, selected row) only for a recognized FE7 menu."""
    _, _, pixels = _png_pixels(observation)
    bands = _blue_menu_bands(pixels)
    if len(bands) == 4:
        kind = "main"
    elif len(bands) == 5:
        kind = "extras"
    else:
        return None
    scores = _gold_marker_scores(pixels, bands)
    if not scores:
        return None
    selected = max(range(len(scores)), key=scores.__getitem__)
    if scores[selected] < 30 or sum(score == scores[selected] for score in scores) != 1:
        return None
    return kind, selected


def title_menu_band_count(observation: dict[str, Any]) -> int:
    """Count visible title-style menu rows even when their marker is mid-blink."""
    _, _, pixels = _png_pixels(observation)
    return len(_blue_menu_bands(pixels))


def _caption_fingerprint_window(observation: dict[str, Any], y0: int, y1: int) -> str:
    _, _, pixels = _png_pixels(observation)
    mask = bytearray()
    for y in range(y0, y1):
        for x in range(3, 178):
            red, green, blue = _pixel(pixels, x, y)
            mask.append(
                int(min(red, green, blue) > 135 and max(red, green, blue) - min(red, green, blue) < 110)
            )
    return hashlib.sha256(mask).hexdigest()


def caption_fingerprint(observation: dict[str, Any]) -> str:
    """Hash FE7's static bottom prompt, excluding animated screen regions."""
    # Rows 130–143 contain animated art on VS Mode screens. The true footer
    # prompt begins at row 144 and remains stable across animation frames.
    return _caption_fingerprint_window(observation, 144, 158)


def link_mode_fingerprint(observation: dict[str, Any]) -> str:
    """Hash the full Link Battle page, whose help footer matches hub row 2."""
    return _caption_fingerprint_window(observation, 130, 158)


def arena_hub_row(observation: dict[str, Any]) -> int | None:
    # The Link Arena hub's description occupies two lines above the footer.
    # Retain its wider mask, which includes the row-specific help text.
    return _HUB_CAPTIONS.get(_caption_fingerprint_window(observation, 130, 158))


class ArenaSetup:
    """Navigate two prepared FE7 cores into the opening Link Arena map."""

    def __init__(
        self,
        coordinator: Any,
        controller: Any,
        *,
        log: Callable[[dict[str, Any]], None],
        status: Callable[[dict[str, Any]], None],
        transition_timeout: float = 15.0,
        poll_interval: float = 0.1,
    ):
        self.coordinator = coordinator
        self.controller = controller
        self.log = log
        self.set_status = status
        self.transition_timeout = transition_timeout
        self.poll_interval = poll_interval
        self._steps = 0

    @staticmethod
    def _chapter(observation: dict[str, Any]) -> int | None:
        value = observation.get("game_state", {}).get("chapter")
        return value if isinstance(value, int) else None

    @staticmethod
    def _roster(observation: dict[str, Any], key: str) -> tuple[int, int] | None:
        value = observation.get("game_state", {}).get(key)
        if not isinstance(value, str) or "/" not in value:
            return None
        try:
            return tuple(int(part) for part in value.split("/", 1))  # type: ignore[return-value]
        except ValueError:
            return None

    @classmethod
    def is_arena_map(cls, observation: dict[str, Any]) -> bool:
        if cls._chapter(observation) != 65 or _ui(observation).get("name") not in _MAP_STATES:
            return False
        players = cls._roster(observation, "players")
        npcs = cls._roster(observation, "npcs")
        return bool(players and npcs and players[1] == 5 and npcs[1] == 5 and players[0] > 0 and npcs[0] > 0)

    def _log_step(self, side: str, stage: str, button: str, observation: dict[str, Any]) -> None:
        self._steps += 1
        if self._steps > 80:
            raise UnsafeScreen("Link Arena setup exceeded 80 verified input steps")
        self.log({"type": "setup_input", "side": side, "stage": stage, "button": button,
                  "observation_id": observation.get("observation_id"),
                  "game_state": observation.get("game_state"), "ui_state": _ui(observation)})
        self.set_status({"state": "setting_up", "side": side, "stage": stage,
                         "inputs_sent": self._steps})

    def _fresh(self, side: str) -> dict[str, Any]:
        observation = self.controller.observe_settled(side)
        if observation.get("coherent") is not True or observation.get("settled") is not True:
            raise UnsafeScreen(f"side {side} setup observation is not settled")
        return observation

    def _press(self, side: str, button: str, stage: str) -> dict[str, Any]:
        before = self._fresh(side)
        last_stale: StaleObservation | None = None
        for attempt in range(3):
            try:
                self.coordinator.act(side, {
                    "observation_id": before["observation_id"],
                    "buttons": [button],
                })
            except StaleObservation as exc:
                last_stale = exc
                refreshed = self._fresh(side)
                # Another linked core can advance the coordinator's shared
                # generation while this local menu remains byte-for-byte at
                # the same control state. The refreshed observation still
                # must match cursor, menu, phase, roster, HP, and inventory.
                same_context = self.controller._same_control_context(
                    before, refreshed, require_generation=False,
                )
                self.log({
                    "type": "setup_stale_observation",
                    "side": side,
                    "stage": stage,
                    "attempt": attempt + 1,
                    "before_observation_id": before.get("observation_id"),
                    "refreshed_observation_id": refreshed.get("observation_id"),
                    "same_control_context": same_context,
                    "reason": str(exc),
                })
                if not same_context:
                    raise UnsafeScreen(
                        f"setup state changed before {stage}; refusing to retry"
                    ) from exc
                if attempt == 2:
                    break
                before = refreshed
                time.sleep(self.poll_interval)
                continue
            self._log_step(side, stage, button, before)
            return before
        raise UnsafeScreen(
            f"setup observation stayed stale at {stage} after bounded safe retries: {last_stale}"
        )

    def _press_startup(self, side: str) -> None:
        """Retry only stale START observations while the safe boot gate holds."""
        last_stale: StaleObservation | None = None
        for _attempt in range(4):
            before = self._fresh(side)
            startup = before.get("game_state", {})
            if (
                self._chapter(before) != 0
                or startup.get("phase") != "start_screen"
                or self._roster(before, "players") != (0, 0)
                or self._roster(before, "npcs") != (0, 0)
                or title_menu_band_count(before) in {4, 5}
            ):
                raise UnsafeScreen("startup changed before the guarded START tap")
            try:
                self.coordinator.act(side, {
                    "observation_id": before["observation_id"], "buttons": ["START"],
                })
            except StaleObservation as exc:
                last_stale = exc
                time.sleep(self.poll_interval)
                continue
            self._log_step(side, "skip_title_or_attract", "START", before)
            return
        raise UnsafeScreen(f"FE7 startup would not hold a fresh START observation: {last_stale}")

    def _wait(self, side: str, predicate: Callable[[dict[str, Any]], bool], description: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.transition_timeout
        last: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            snapshot = self.coordinator.status()["sides"][side]
            if snapshot.get("coherent") is True and snapshot.get("settled") is True:
                observation = self._fresh(side)
                if predicate(observation):
                    return observation
                last = observation
            time.sleep(self.poll_interval)
        state = {
            "ui_state": _ui(last) if last else None,
            "game_state": last.get("game_state") if last else None,
            "caption": caption_fingerprint(last) if last and last.get("screenshot") else None,
        }
        raise UnsafeScreen(f"side {side} did not reach {description}: {state!r}")

    def _menu_row(
        self, side: str, *, kind: str | None = None, selected: int | None = None
    ) -> tuple[dict[str, Any], int]:
        deadline = time.monotonic() + self.transition_timeout
        last_layout: tuple[str, int] | None = None
        last_observation: dict[str, Any] | None = None
        stable_count = 0
        saw_menu_rows = False
        while time.monotonic() < deadline:
            observation = self._fresh(side)
            layout = title_menu_state(observation)
            saw_menu_rows = saw_menu_rows or title_menu_band_count(observation) in {4, 5}
            if layout is not None and (kind is None or layout[0] == kind):
                if selected is None or layout[1] == selected:
                    stable_count = stable_count + 1 if layout == last_layout else 1
                    last_layout = layout
                    last_observation = observation
                    if stable_count >= 2:
                        return observation, layout[1]
                else:
                    last_layout = layout
                    last_observation = observation
                    stable_count = 0
            else:
                last_layout = None
                last_observation = observation
                stable_count = 0
            time.sleep(self.poll_interval)
        observed = title_menu_state(last_observation) if last_observation else None
        if saw_menu_rows:
            raise UnsafeScreen(f"FE7 title menu rows were visible but selection was unstable: {observed!r}")
        raise UnsafeScreen(f"expected FE7 {kind or 'title'} menu, observed {observed!r}")

    def _move_title_menu(self, side: str, kind: str, target: int) -> dict[str, Any]:
        observation, row = self._menu_row(side, kind=kind)
        count = 4 if kind == "main" else 5
        if not 0 <= target < count:
            raise ValueError("title menu target is outside its row range")
        while row != target:
            expected = (row + 1) % count
            self.coordinator.act(side, {
                "observation_id": observation["observation_id"], "buttons": ["DOWN"],
            })
            self._log_step(side, f"{kind}_menu_row_{row}_to_{expected}", "DOWN", observation)
            observation = self._wait(
                side,
                lambda candidate, k=kind, e=expected: title_menu_state(candidate) == (k, e),
                f"{kind} menu row {expected}",
            )
            # _menu_row takes fresh screenshots while waiting for the cursor
            # highlight to stabilize; keep its newest observation ID for the
            # next direction press.
            observation, row = self._menu_row(side, kind=kind, selected=expected)
        return observation

    def _navigate_side_to_hub(self, side: str) -> None:
        start_presses = 0
        while True:
            observation = self._fresh(side)
            if self.is_arena_map(observation):
                return
            chapter = self._chapter(observation)
            ui_name = _ui(observation).get("name")

            if chapter == 0:
                layout = title_menu_state(observation)
                if layout is None:
                    phase = observation.get("game_state", {}).get("phase")
                    if title_menu_band_count(observation) in {4, 5}:
                        # The menu is visibly present but its gold selection
                        # marker is blinking. Wait for two matching reads;
                        # never let START activate a menu with unknown focus.
                        stable, _ = self._menu_row(side)
                        layout = title_menu_state(stable)
                        if layout is None:
                            raise UnsafeScreen("FE7 title menu selection did not stabilize")
                    else:
                        layout = None
                    if layout is None and (
                        phase == "start_screen"
                        and self._roster(observation, "players") == (0, 0)
                        and self._roster(observation, "npcs") == (0, 0)
                    ):
                        if start_presses >= 8:
                            raise UnsafeScreen(f"side {side} stayed on title/demo after eight START presses")
                        # STATE can falsely call the FE7 attract demo a menu
                        # (and report impossible rows such as 48). Chapter 0,
                        # start_screen, empty rosters, and no visible menu rows
                        # are the safe bounded boot case.
                        self._press_startup(side)
                        start_presses += 1
                        continue
                    if layout is None:
                        raise UnsafeScreen(f"unrecognized FE7 startup screen; refusing to press a menu button on side {side}")
                else:
                    stable, _ = self._menu_row(side, kind=layout[0], selected=layout[1])
                    layout = title_menu_state(stable)
                    if layout is None:
                        raise UnsafeScreen("FE7 title menu selection did not stabilize")
                kind, row = layout
                if kind == "main":
                    self._move_title_menu(side, "main", 3)
                    self._press(side, "A", "open_extras")
                    self._wait(
                        side,
                        lambda candidate: self._chapter(candidate) == 0
                        and _ui(candidate).get("name") == "not_in_game"
                        and title_menu_state(candidate) == ("extras", 0),
                        "Extras with Link Arena selected",
                    )
                    continue
                if kind == "extras":
                    if row != 0:
                        raise UnsafeScreen(f"Extras opened on row {row}; refusing to choose a different mode")
                    self._press(side, "A", "open_link_arena")
                    self._wait(
                        side,
                        lambda candidate: self._chapter(candidate) == 65
                        and self._roster(candidate, "players") == (0, 0)
                        and self._roster(candidate, "npcs") == (0, 0)
                        and arena_hub_row(candidate) == 0,
                        "Link Arena hub with Edit Teams selected",
                    )
                    return
                raise UnsafeScreen(f"unexpected FE7 title menu kind {kind!r}")

            raise UnsafeScreen(
                f"side {side} reached an unsupported setup state: chapter={chapter!r}, ui={_ui(observation)!r}"
            )

    def _select_linked_battle_team(self, side: str) -> None:
        """Navigate one core through boot and stop at the saved-team picker."""
        self._navigate_side_to_hub(side)
        observation = self._fresh(side)
        row = arena_hub_row(observation)
        if row is None:
            raise UnsafeScreen(f"side {side} Link Arena hub caption is unrecognized")
        while row < 2:
            expected = row + 1
            self.coordinator.act(side, {
                "observation_id": observation["observation_id"], "buttons": ["DOWN"],
            })
            self._log_step(side, f"link_arena_hub_row_{row}_to_{expected}", "DOWN", observation)
            observation = self._wait(
                side,
                lambda candidate, e=expected: self._chapter(candidate) == 65
                and self._roster(candidate, "players") == (0, 0)
                and self._roster(candidate, "npcs") == (0, 0)
                and arena_hub_row(candidate) == e,
                f"Link Arena hub row {expected}",
            )
            row = arena_hub_row(observation)
            if row is None:
                raise UnsafeScreen("Link Arena hub menu lost its selection caption")

        # The row-specific help line is the cursor witness: row 2 is Linked
        # Battle. Some mGBA input timings pass through the one-option page;
        # others carry the confirm through to team selection in one tap.
        self._press(side, "A", "open_linked_battle")
        def is_team_select(candidate: dict[str, Any]) -> bool:
            return (
                self._chapter(candidate) == 65
                and self._roster(candidate, "players") == (50, 50)
                and caption_fingerprint(candidate) == _TEAM_SELECT_CAPTIONS[side]
            )

        def is_link_mode(candidate: dict[str, Any]) -> bool:
            return (
                self._chapter(candidate) == 65
                and self._roster(candidate, "players") == (0, 0)
                and self._roster(candidate, "npcs") == (0, 0)
                and link_mode_fingerprint(candidate) in _LINK_MODE_CAPTIONS
            )

        selection_screen = self._wait(
            side,
            lambda candidate: is_link_mode(candidate) or is_team_select(candidate),
            "Linked Battle confirmation or RAGNAROK team selection",
        )
        if is_link_mode(selection_screen):
            self._press(side, "A", "confirm_linked_battle")
            self._wait(side, is_team_select, "RAGNAROK team selection")

    def _confirm_default_team(self, side: str) -> None:
        """Confirm the saved RAGNAROK roster after both cores are at the picker."""
        def is_team_select(candidate: dict[str, Any]) -> bool:
            return (
                self._chapter(candidate) == 65
                and self._roster(candidate, "players") == (50, 50)
                and caption_fingerprint(candidate) == _TEAM_SELECT_CAPTIONS[side]
            )

        before = self._fresh(side)
        if not is_team_select(before):
            raise UnsafeScreen(f"side {side} is not at the verified RAGNAROK team picker")

        # Both emulators must reach the team picker before either one starts
        # FE7's serial-link setup. Advancing side A while side B is still on
        # the title screen caused mGBA 0.11 to abort on the saved-team confirm.
        self._press(side, "A", "confirm_default_ragnarok_team")
        time.sleep(min(2.0, self.transition_timeout))
        after_team_confirm = self._fresh(side)
        if is_team_select(after_team_confirm):
            # FE7's VS Mode team picker can consume the first A as focus on the
            # saved-team list and remain on the same screen. Both cores are now
            # staged at this exact picker, so one guarded retry is safe.
            self._press(side, "A", "confirm_default_ragnarok_team_again")
        time.sleep(min(1.0, self.transition_timeout))
        connected = self._fresh(side)
        if (
            self._chapter(connected) != 65
            or self._roster(connected, "players") != (50, 50)
            or caption_fingerprint(connected) == _TEAM_SELECT_CAPTIONS[side]
        ):
            raise UnsafeScreen(f"side {side} did not leave the verified team picker after confirmation")

    def _connect_and_start(self) -> None:
        def ready_prompt(side: str, expected_hash: str) -> dict[str, Any]:
            return self._wait(
                side,
                lambda candidate: self._chapter(candidate) == 65
                and self._roster(candidate, "players") == (50, 50)
                and caption_fingerprint(candidate) == expected_hash,
                "connected Link Arena lobby",
            )

        ready_prompt("A", _LINK_READY_CAPTIONS["A"])
        ready_prompt("B", _LINK_READY_CAPTIONS["B"])
        self._press("A", "START", "start_link_battle")
        self._wait(
            "A",
            lambda candidate: self._chapter(candidate) == 65
            and self._roster(candidate, "players") == (50, 50)
            and caption_fingerprint(candidate) == _FIRST_PLAYER_CAPTIONS["A"],
            "player-order prompt on side A",
        )
        self._wait(
            "B",
            lambda candidate: self._chapter(candidate) == 65
            and self._roster(candidate, "players") == (50, 50)
            and caption_fingerprint(candidate) == _FIRST_PLAYER_CAPTIONS["B"],
            "1P-first selection on side B",
        )
        # FE7 defaults to 1P first. This matches MinimaxAutoplay's A then B
        # scheduling and keeps the opening order deterministic.
        self._press("B", "A", "select_player_one_to_move_first")
        self._wait(
            "A", self.is_arena_map, "stable opening Link Arena map on side A"
        )
        self._wait(
            "B", self.is_arena_map, "stable opening Link Arena map on side B"
        )

    def prepare_pair(self) -> None:
        self.set_status({"state": "setting_up", "stage": "booting_side_a", "side": "A"})
        self._select_linked_battle_team("A")
        self.set_status({"state": "setting_up", "stage": "booting_side_b", "side": "B",
                         "side_a": "at_team_picker"})
        self._select_linked_battle_team("B")
        self.set_status({"state": "setting_up", "stage": "confirming_saved_teams",
                         "side_a": "at_team_picker", "side_b": "at_team_picker"})
        self._confirm_default_team("A")
        self._confirm_default_team("B")
        self.set_status({"state": "setting_up", "stage": "link_handshake",
                         "side_a": "team_confirmed", "side_b": "team_confirmed"})
        self._connect_and_start()
        self.set_status({"state": "ready", "stage": "opening_map"})
        self.log({"type": "setup_complete", "opening_map": "FE7 chapter 65",
                  "teams": {"A": "RAGNAROK", "B": "RAGNAROK"}, "first_player": "A/1P"})
