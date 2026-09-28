"""Minimax policies for FE7 Link Arena decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .minimax import (
    FE7_COMBAT_WEAPON_IDS,
    FE7_NONCOMBAT_ITEM_IDS,
    DuelChoice,
    WEAPONS,
    minimax_matchup,
    minimax_weapon,
)


@dataclass(frozen=True)
class AgentDecision:
    side: str
    attacker_id: int
    defender_id: int
    weapon_id: int
    weapon_name: str
    inventory_slot: int
    score: float
    worst_reply_item: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MinimaxAgent:
    """Chooses a Link Arena matchup and weapon by a depth-two minimax search."""

    def __init__(self, side: str, *, defender_auto_weapon: bool = False):
        normalized = side.upper()
        if normalized not in {"A", "B"}:
            raise ValueError("side must be A or B")
        self.side = normalized
        self.defender_auto_weapon = defender_auto_weapon
        # The bridge perspective can be rotated between mGBA clients. The
        # autoplay runner replaces this default after inspecting each live
        # map; standalone agents keep the historical A/player, B/NPC mapping.
        self.own_team = "player" if normalized == "A" else "npc"

    def set_own_team(self, team: str) -> None:
        normalized = team.lower()
        if normalized not in {"player", "npc"}:
            raise ValueError("own team must be player or npc")
        self.own_team = normalized

    def _teams(self, observation: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        units = observation.get("units", [])
        if not isinstance(units, list):
            return [], []
        own_team = self.own_team
        opponent_teams = {"npc", "enemy"} if own_team == "player" else {"player", "enemy"}
        own = [unit for unit in units if isinstance(unit, dict) and unit.get("team") == own_team]
        opponents = [unit for unit in units if isinstance(unit, dict) and unit.get("team") in opponent_teams]
        return own, opponents

    def _input_position(self, position: list[Any]) -> tuple[int, int]:
        x, y = int(position[0]), int(position[1])
        # Each bridge reports positions in that emulator's local map frame:
        # the local roster sits on the bottom edge for both Link Arena clients.
        return x, y

    @staticmethod
    def observed_cursor(observation: dict[str, Any]) -> tuple[int, int]:
        detail = observation.get("detail")
        cursor = detail.get("bm_cursor") if isinstance(detail, dict) else None
        if not isinstance(cursor, list) or len(cursor) != 2:
            raise ValueError("observation has no FE7 battle-map cursor in detail.bm_cursor")
        x, y = int(cursor[0]), int(cursor[1])
        if not (0 <= x < 15 and 0 <= y < 10):
            raise ValueError(f"observed battle-map cursor is outside the board: {(x, y)}")
        return x, y

    def choose_matchup(self, observation: dict[str, Any]) -> AgentDecision:
        own, opponents = self._teams(observation)
        choice: DuelChoice = minimax_matchup(
            own, opponents, defender_auto_weapon=self.defender_auto_weapon
        )
        return AgentDecision(
            side=self.side,
            attacker_id=choice.attacker_id,
            defender_id=choice.defender_id,
            weapon_id=choice.item_id,
            weapon_name=WEAPONS[choice.item_id].name,
            inventory_slot=choice.slot,
            score=choice.score,
            worst_reply_item=choice.worst_reply_item,
        )

    def choose_weapon(
        self,
        observation: dict[str, Any],
        *,
        attacker_id: int,
        defender_id: int,
    ) -> AgentDecision:
        own, opponents = self._teams(observation)
        attacker = next((unit for unit in own if int(unit.get("character_id", -1)) == attacker_id), None)
        defender = next((unit for unit in opponents if int(unit.get("character_id", -1)) == defender_id), None)
        if attacker is None or defender is None:
            raise ValueError(f"selected Link Arena matchup is absent from side {self.side}'s observation")
        slot, weapon, score, reply = minimax_weapon(
            attacker, defender, defender_auto_weapon=self.defender_auto_weapon
        )
        return AgentDecision(
            side=self.side,
            attacker_id=attacker_id,
            defender_id=defender_id,
            weapon_id=weapon.item_id,
            weapon_name=weapon.name,
            inventory_slot=slot,
            score=score,
            worst_reply_item=reply,
        )

    @staticmethod
    def cursor_path(start: tuple[int, int], target: tuple[int, int]) -> list[str]:
        """Shortest unobstructed cursor path on the 15x10 Link Arena board."""
        x, y = start
        tx, ty = target
        path: list[str] = []
        while x < tx:
            path.append("RIGHT")
            x += 1
        while x > tx:
            path.append("LEFT")
            x -= 1
        while y < ty:
            path.append("DOWN")
            y += 1
        while y > ty:
            path.append("UP")
            y -= 1
        return path

    def select_actor_buttons(
        self,
        observation: dict[str, Any],
        decision: AgentDecision,
        *,
        cursor: tuple[int, int] | None = None,
    ) -> list[str]:
        own, _ = self._teams(observation)
        actor = next((unit for unit in own if int(unit.get("character_id", -1)) == decision.attacker_id), None)
        if actor is None:
            raise ValueError(f"attacker {decision.attacker_id} is absent from side {self.side}'s roster")
        position = actor.get("position", [])
        if not isinstance(position, list) or len(position) != 2:
            raise ValueError("selected attacker has no map position")
        start = self.observed_cursor(observation) if cursor is None else cursor
        return self.cursor_path(start, self._input_position(position)) + ["A"]

    def select_target_buttons(
        self,
        observation: dict[str, Any],
        decision: AgentDecision,
        *,
        cursor: tuple[int, int] | None = None,
    ) -> list[str]:
        _, opponents = self._teams(observation)
        defender = next((unit for unit in opponents if int(unit.get("character_id", -1)) == decision.defender_id), None)
        if defender is None:
            raise ValueError(f"defender {decision.defender_id} is absent from side {self.side}'s observation")
        position = defender.get("position", [])
        if not isinstance(position, list) or len(position) != 2:
            raise ValueError("selected defender has no map position")
        start = self.observed_cursor(observation) if cursor is None else cursor
        return self.cursor_path(start, self._input_position(position)) + ["A"]

    @staticmethod
    def confirm_forecast() -> list[str]:
        """Confirm the in-game FE7 forecast after the minimax weapon choice."""
        return ["A"]

    @staticmethod
    def buttons_for_weapon(decision: AgentDecision, *, selected_row: int = 0) -> list[str]:
        # Link Arena's list omits non-weapons, so inventory slot is not always
        # the row index. The current roster's active unit lists only weapons in
        # its selectable slots; callers may provide a UI row if they decoded it.
        delta = decision.inventory_slot - selected_row
        direction = "DOWN" if delta > 0 else "UP"
        return [direction] * abs(delta) + ["A"]

    def weapon_menu_row(
        self,
        observation: dict[str, Any],
        decision: AgentDecision,
    ) -> int:
        """Return the menu row for the chosen inventory slot, or fail closed.

        FE7's Link Arena weapon list omits non-weapons. Count every known FE7
        combat weapon, including weapons not yet modeled by the minimax scorer,
        and skip known FE7 gear. Unknown inventory IDs still fail closed.
        """
        own, _ = self._teams(observation)
        actor = next((unit for unit in own if int(unit.get("character_id", -1)) == decision.attacker_id), None)
        if actor is None:
            raise ValueError(f"attacker {decision.attacker_id} is absent from side {self.side}'s roster")
        inventory = actor.get("inventory", [])
        if not isinstance(inventory, list):
            raise ValueError("selected attacker has no parsed inventory")
        rows: list[dict[str, Any]] = []
        for item in inventory:
            if not isinstance(item, dict):
                continue
            item_id = int(item.get("id", -1))
            if item_id in FE7_COMBAT_WEAPON_IDS:
                rows.append(item)
            elif item_id in FE7_NONCOMBAT_ITEM_IDS:
                # Equipment, staves, and consumables are omitted from the
                # target's attack-weapon menu.
                continue
            else:
                raise ValueError(
                    f"cannot map Link Arena weapon-menu rows: inventory item {item_id} is not classified"
                )
        for row, item in enumerate(rows):
            if int(item.get("slot", -1)) == decision.inventory_slot and int(item.get("id", -1)) == decision.weapon_id:
                return row
        raise ValueError(
            f"chosen weapon {decision.weapon_id} in slot {decision.inventory_slot} is absent from the menu inventory"
        )
