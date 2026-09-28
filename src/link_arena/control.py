"""Fail-closed, one-input-at-a-time controls for FE7 Link Arena."""

from __future__ import annotations

import time
from typing import Any, Callable

from .coordinator import StaleObservation


class UnsafeScreen(RuntimeError):
    """Raised before or after an input when the observed screen is unexpected."""


_DIRECTION_DELTA = {
    "UP": (0, -1),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
    "RIGHT": (1, 0),
}
_MAP_STATES = {"player_phase", "npc_phase", "link_arena_map"}
_KNOWN_MENUS = {"arena", "unit", "item", "battle"}


def _ui(observation: dict[str, Any]) -> dict[str, Any]:
    value = observation.get("ui_state")
    return value if isinstance(value, dict) else {}


def _cursor(observation: dict[str, Any]) -> tuple[int, int]:
    detail = observation.get("detail")
    value = detail.get("bm_cursor") if isinstance(detail, dict) else None
    if not isinstance(value, list) or len(value) != 2:
        raise UnsafeScreen("DETAIL does not contain a usable battle-map cursor")
    try:
        x, y = int(value[0]), int(value[1])
    except (TypeError, ValueError) as exc:
        raise UnsafeScreen("DETAIL battle-map cursor is not numeric") from exc
    if not (0 <= x < 15 and 0 <= y < 10):
        raise UnsafeScreen(f"battle-map cursor is outside the FE7 board: {(x, y)}")
    return x, y


def _menu_selection(observation: dict[str, Any]) -> tuple[str, int]:
    ui = _ui(observation)
    if ui.get("name") != "menu" or ui.get("menu_type") not in _KNOWN_MENUS:
        raise UnsafeScreen(f"not on a supported Link Arena menu: {ui!r}")
    try:
        selection = int(ui["selection"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnsafeScreen(f"menu has no numeric selected row: {ui!r}") from exc
    return str(ui["menu_type"]), selection


def _directional_cursor_target(
    screen_name: str, cursor: tuple[int, int], button: str,
) -> tuple[int, int]:
    """Return FE7's verified cursor destination for one directional press.

    Link Arena's narrow battlefield connects the two deployed rows directly:
    UP from row 9 reaches row 1, and DOWN from row 1 reaches row 9. The map
    cursor follows that arena topology rather than traversing the empty tiles
    between the teams.
    """
    x, y = cursor
    if screen_name == "link_arena_map" and button == "UP" and y == 9:
        return x, 1
    if screen_name == "link_arena_map" and button == "DOWN" and y == 1:
        return x, 9
    dx, dy = _DIRECTION_DELTA[button]
    return x + dx, y + dy


class VerifiedInputController:
    """Issue one button at a time and verify the corresponding FE7 state delta.

    The coordinator is intentionally duck-typed to keep this controller usable
    with both the live bridge and deterministic fakes in unit tests.
    """

    def __init__(
        self,
        coordinator: Any,
        *,
        poll_interval: float = 0.05,
        settle_timeout: float = 60.0,
    ):
        self.coordinator = coordinator
        self.poll_interval = poll_interval
        self.settle_timeout = settle_timeout
        self.decision_id: str | None = None
        self.agent_side: str | None = None

    def set_decision_context(self, decision_id: str | None, agent_side: str | None = None) -> None:
        """Tag every verified button pulse with the policy choice that caused it."""
        self.decision_id = decision_id
        self.agent_side = agent_side if decision_id is not None else None

    def observe_settled(self, side: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.settle_timeout
        last: dict[str, Any] | None = None
        locked_menu_key: tuple[Any, ...] | None = None
        locked_menu_reads = 0
        while time.monotonic() < deadline:
            last = self.coordinator.observe(side)
            if last.get("coherent") is True and last.get("settled") is True:
                return last
            ui = _ui(last)
            detail = last.get("detail")
            game_state = last.get("game_state")
            stable_menu = (
                ui.get("name") == "menu"
                and ui.get("menu_type") in {"item", "arena", "battle"}
                and isinstance(ui.get("selection"), int)
                and int(ui["selection"]) >= 0
            )
            if (
                last.get("coherent") is True
                and (stable_menu or ui.get("name") == "battle_forecast")
                and isinstance(detail, dict)
                and detail.get("locked") is True
            ):
                key = (
                    ui.get("name"), ui.get("menu_type"), ui.get("selection"),
                    detail.get("bm_cursor"),
                    game_state.get("chapter") if isinstance(game_state, dict) else None,
                    game_state.get("players") if isinstance(game_state, dict) else None,
                    game_state.get("npcs") if isinstance(game_state, dict) else None,
                )
                locked_menu_reads = locked_menu_reads + 1 if key == locked_menu_key else 1
                locked_menu_key = key
                if locked_menu_reads >= 2:
                    # Some FE7 Link Arena menus keep BmSt locked while they
                    # await a menu input. Accept only a visually classified,
                    # uniquely selected menu that is stable across captures.
                    return last
            else:
                locked_menu_key = None
                locked_menu_reads = 0
            time.sleep(self.poll_interval)
        detail = last.get("detail") if isinstance(last, dict) else None
        ui = last.get("ui_state") if isinstance(last, dict) else None
        raise UnsafeScreen(f"screen did not settle for side {side}: state={ui!r} detail={detail!r}")

    @staticmethod
    def _same_control_context(
        before: dict[str, Any],
        after: dict[str, Any],
        *,
        require_generation: bool = True,
    ) -> bool:
        """Allow a stale-ID retry only when the game is exactly where we saw it."""
        def generation(observation: dict[str, Any]) -> str | None:
            observation_id = observation.get("observation_id")
            return observation_id.split("-", 1)[0] if isinstance(observation_id, str) else None

        def roster(observation: dict[str, Any]) -> tuple[Any, ...]:
            return tuple(sorted(
                (
                    str(unit.get("team")), str(unit.get("character_id")),
                    tuple(unit.get("position", []))
                    if isinstance(unit.get("position"), (list, tuple)) else (),
                    str((unit.get("hp") or {}).get("current")
                        if isinstance(unit.get("hp"), dict) else None),
                    tuple(sorted(
                        (str(item.get("id")), str(item.get("uses")), str(item.get("slot")))
                        for item in unit.get("inventory", [])
                        if isinstance(item, dict)
                    )) if isinstance(unit.get("inventory"), list) else (),
                )
                for unit in observation.get("units", [])
                if isinstance(unit, dict)
            ))

        before_detail = before.get("detail")
        after_detail = after.get("detail")
        before_state = before.get("game_state")
        after_state = after.get("game_state")
        state_keys = ("chapter", "turn", "phase", "players", "npcs")
        return (
            generation(before) is not None
            and generation(after) is not None
            and (not require_generation or generation(before) == generation(after))
            and _ui(before) == _ui(after)
            and isinstance(before_detail, dict)
            and isinstance(after_detail, dict)
            and before_detail.get("bm_cursor") == after_detail.get("bm_cursor")
            and before_detail.get("phase_raw") == after_detail.get("phase_raw")
            and isinstance(before_state, dict)
            and isinstance(after_state, dict)
            and all(before_state.get(key) == after_state.get(key) for key in state_keys)
            and roster(before) == roster(after)
        )

    def _send_and_observe(
        self,
        side: str,
        before: dict[str, Any],
        button: str,
        *,
        hold_frames: int | None = None,
    ) -> dict[str, Any]:
        action = {
            "observation_id": before["observation_id"],
            "buttons": [button],
        }
        if self.decision_id is not None:
            action["decision_id"] = self.decision_id
            action["agent_side"] = self.agent_side
        if hold_frames is not None:
            action["hold_frames"] = hold_frames
        try:
            self.coordinator.act(side, action)
        except StaleObservation as exc:
            refreshed = self.observe_settled(side)
            if not self._same_control_context(before, refreshed):
                raise UnsafeScreen(
                    "action observation went stale and the game state changed; refusing to retry"
                ) from exc
            action["observation_id"] = refreshed["observation_id"]
            try:
                self.coordinator.act(side, action)
            except StaleObservation as retry_exc:
                raise UnsafeScreen("refreshed action observation also went stale") from retry_exc
        return self.observe_settled(side)

    @staticmethod
    def _map_target(observation: dict[str, Any], button: str) -> tuple[int, int]:
        cursor = _cursor(observation)
        expected = _directional_cursor_target(
            str(_ui(observation).get("name")), cursor, button,
        )
        if (
            str(_ui(observation).get("name")) != "link_arena_map"
            or button not in {"LEFT", "RIGHT"}
            or cursor[1] not in {1, 9}
        ):
            return expected
        x, y = cursor
        candidates: list[int] = []
        for unit in observation.get("units", []):
            if not isinstance(unit, dict):
                continue
            position = unit.get("position")
            if not isinstance(position, list) or len(position) != 2 or position[1] != y:
                continue
            hp = unit.get("hp")
            if isinstance(hp, dict) and isinstance(hp.get("current"), int) and hp["current"] <= 0:
                continue
            unit_x = position[0]
            if isinstance(unit_x, int) and (
                (button == "LEFT" and unit_x < x)
                or (button == "RIGHT" and unit_x > x)
            ):
                candidates.append(unit_x)
        if not candidates:
            return expected
        # FE7 skips a row coordinate after a unit on that tile has fallen. Its
        # cursor moves to the next live unit, so validate that observed jump
        # against the board instead of insisting on an empty square.
        next_x = max(candidates) if button == "LEFT" else min(candidates)
        return next_x, y

    def tap_direction(self, side: str, direction: str) -> dict[str, Any]:
        """Move one map tile or menu row, requiring an exact one-step result."""
        button = direction.upper()
        if button not in _DIRECTION_DELTA:
            raise ValueError(f"unsupported direction: {direction}")
        before = self.observe_settled(side)
        ui_before = _ui(before)
        dx, dy = _DIRECTION_DELTA[button]

        if ui_before.get("name") in _MAP_STATES:
            x, y = _cursor(before)
            expected_cursor = self._map_target(before, button)
            if not (0 <= expected_cursor[0] < 15 and 0 <= expected_cursor[1] < 10):
                raise UnsafeScreen(f"{button} would move the cursor off the map from {(x, y)}")
            after = self._send_and_observe(side, before, button)
            if _ui(after).get("name") != ui_before.get("name"):
                raise UnsafeScreen(f"map state changed during {button}: {_ui(before)!r} -> {_ui(after)!r}")
            actual_cursor = _cursor(after)
            if actual_cursor != expected_cursor:
                raise UnsafeScreen(f"{button} expected cursor {expected_cursor}, observed {actual_cursor}")
            return after

        menu_type, selected_row = _menu_selection(before)
        expected_row = selected_row + dy if dx == 0 else selected_row
        if dx != 0:
            raise UnsafeScreen("left/right inputs are not allowed while a menu is open")
        if expected_row < 0:
            raise UnsafeScreen(f"{button} would move above menu row zero")
        after = self._send_and_observe(side, before, button)
        after_type, actual_row = _menu_selection(after)
        if after_type != menu_type or actual_row != expected_row:
            raise UnsafeScreen(
                f"{button} expected {menu_type} row {expected_row}, observed {after_type} row {actual_row}"
            )
        return after

    def move_cursor_to(self, side: str, target: tuple[int, int]) -> dict[str, Any]:
        """Walk an unobstructed Manhattan path, checking every individual tile."""
        tx, ty = target
        if not (0 <= tx < 15 and 0 <= ty < 10):
            raise ValueError(f"target is outside the FE7 board: {target}")
        current = self.observe_settled(side)
        if _ui(current).get("name") not in _MAP_STATES:
            raise UnsafeScreen(f"cannot route a board cursor from {_ui(current)!r}")
        x, y = _cursor(current)
        while x != tx:
            current = self.tap_direction(side, "RIGHT" if x < tx else "LEFT")
            x, y = _cursor(current)
        while y != ty:
            current = self.tap_direction(side, "DOWN" if y < ty else "UP")
            x, y = _cursor(current)
        return current

    def move_menu_to(self, side: str, *, menu_type: str, row: int) -> dict[str, Any]:
        """Move to an exact row while verifying every selection-index change."""
        if row < 0:
            raise ValueError("menu row must be non-negative")
        current = self.observe_settled(side)
        current_type, selected = _menu_selection(current)
        if current_type != menu_type:
            raise UnsafeScreen(f"expected {menu_type} menu, observed {current_type}")
        while selected != row:
            current = self.tap_direction(side, "DOWN" if selected < row else "UP")
            current_type, selected = _menu_selection(current)
            if current_type != menu_type:
                raise UnsafeScreen(f"menu changed while navigating: expected {menu_type}, observed {current_type}")
        return current

    def confirm_unit_at_cursor(
        self,
        side: str,
        *,
        team: str,
        character_id: int,
        expected_after: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        """Confirm only when a live named unit occupies the verified cursor tile."""
        before = self.observe_settled(side)
        if _ui(before).get("name") not in _MAP_STATES:
            raise UnsafeScreen(f"unit confirmation requires a stable board, saw {_ui(before)!r}")
        cursor = _cursor(before)
        unit = next((
            candidate for candidate in before.get("units", [])
            if isinstance(candidate, dict)
            and candidate.get("team") == team
            and candidate.get("character_id") == character_id
            and candidate.get("position") == list(cursor)
        ), None)
        if unit is None:
            raise UnsafeScreen(f"no live {team} unit {character_id} is under cursor {cursor}")
        # A short pulse selects the unit and releases before FE7's next menu
        # can consume the same held A as a weapon or battle confirmation.
        after = self._send_and_observe(side, before, "A", hold_frames=3)
        if not expected_after(after):
            raise UnsafeScreen(
                f"A on {team} unit {character_id} produced an unapproved screen: {_ui(after)!r}"
            )
        return after

    def confirm_menu_row(
        self,
        side: str,
        *,
        menu_type: str,
        row: int,
        expected_after: Callable[[dict[str, Any]], bool],
    ) -> dict[str, Any]:
        """Confirm a caller-identified row, then require its declared screen result."""
        before = self.observe_settled(side)
        actual_type, actual_row = _menu_selection(before)
        if (actual_type, actual_row) != (menu_type, row):
            raise UnsafeScreen(
                f"refusing A: expected {menu_type} row {row}, saw {actual_type} row {actual_row}"
            )
        after = self._send_and_observe(side, before, "A", hold_frames=3)
        if not expected_after(after):
            raise UnsafeScreen(
                f"A on {menu_type} row {row} produced an unapproved screen: {_ui(after)!r}"
            )
        return after

    def confirm_screen(
        self,
        side: str,
        *,
        screen_name: str,
        expected_after: Callable[[dict[str, Any]], bool],
        button: str = "A",
    ) -> dict[str, Any]:
        """Send one button only from a recognized, visually stable screen."""
        before = self.observe_settled(side)
        if _ui(before).get("name") != screen_name:
            raise UnsafeScreen(f"refusing {button}: expected {screen_name}, saw {_ui(before)!r}")
        after = self._send_and_observe(side, before, button, hold_frames=3)
        if not expected_after(after):
            raise UnsafeScreen(
                f"{button} on {screen_name} produced an unapproved screen: {_ui(after)!r}"
            )
        return after
