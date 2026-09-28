"""Minimax policies for FE7 Link Arena decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    score: float | None
    worst_reply_item: int | None
    rationale: str | None = None

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

    def benchmark_metadata(self) -> dict[str, Any]:
        return {
            "kind": "hand_coded_policy",
            "name": "fe7-link-arena-minimax-depth-two",
            "version": 1,
            "provider": "local",
            "model": None,
            "own_team": self.own_team,
        }

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


class OpenAICompatibleAgent(MinimaxAgent):
    """Structured-state Link Arena policy using Chutes or MiniMax chat APIs.

    This adapter asks only for a legal matchup tuple. The existing verified
    controller remains responsible for every cursor/menu input and refuses any
    choice that does not match the observed FE7 roster and inventory.
    """

    _PROVIDERS = {
        "chutes": {
            "base_url": "https://llm.chutes.ai/v1",
            "api_key_env": "CHUTES_API_KEY",
        },
        "minimax-api": {
            "base_url": "https://api.minimax.io/v1",
            "api_key_env": "MINIMAX_API_KEY",
        },
    }
    _SYSTEM_TEMPLATE = (
        "Choose one FE7 Link Arena attack from the supplied structured state. "
        "Return exactly one JSON object with integer fields attacker_id, "
        "defender_id, and weapon_id, and a rationale string of at most two "
        "sentences. Select a living unit from own_units, a living unit from "
        "opposing_units, and a usable weapon in the attacker's inventory. Give "
        "only a concise user-visible explanation based on the supplied state; "
        "do not provide hidden chain-of-thought. Do not return movement, buttons, "
        "or any other fields."
    )

    def __init__(
        self,
        side: str,
        *,
        provider: str,
        model: str,
        base_url: str | None = None,
        api_key_env: str | None = None,
        timeout_seconds: float = 120.0,
        temperature: float = 0.0,
        max_completion_tokens: int = 2048,
        minimax_thinking: str | None = None,
        minimax_reasoning_effort: str | None = None,
    ):
        super().__init__(side)
        normalized_provider = provider.strip().lower()
        if normalized_provider not in self._PROVIDERS:
            raise ValueError(f"unsupported Link Arena model provider: {provider!r}")
        if not model.strip():
            raise ValueError(f"a concrete model ID is required for provider {normalized_provider}")
        if timeout_seconds <= 0 or max_completion_tokens < 1:
            raise ValueError("model timeout and maximum completion tokens must be positive")
        defaults = self._PROVIDERS[normalized_provider]
        self.provider = normalized_provider
        self.model = model.strip()
        self.base_url = (base_url or defaults["base_url"]).rstrip("/")
        self.api_key_env = api_key_env or defaults["api_key_env"]
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        if minimax_thinking not in {None, "adaptive", "disabled"}:
            raise ValueError("MiniMax thinking mode must be 'adaptive' or 'disabled'")
        if minimax_reasoning_effort not in {None, "low", "medium", "high", "xhigh", "max"}:
            raise ValueError("unsupported MiniMax reasoning effort")
        if self.provider != "minimax-api" and (
            minimax_thinking is not None or minimax_reasoning_effort is not None
        ):
            raise ValueError("MiniMax reasoning options require --agent-a/b minimax-api")
        self.minimax_thinking: str | None = None
        self.minimax_reasoning_effort: str | None = None
        self.reasoning_split: bool | None = None
        if self.provider == "minimax-api":
            model_id = self.model.lower()
            is_m31 = "m3.1" in model_id
            is_m2 = "m2." in model_id or model_id.endswith("-m2")
            self.minimax_thinking = minimax_thinking or "adaptive"
            self.reasoning_split = True
            if is_m31 and self.minimax_thinking == "disabled":
                raise ValueError("MiniMax M3.1 always reasons; choose an explicit reasoning effort instead")
            if is_m2 and self.minimax_thinking == "disabled":
                raise ValueError("MiniMax M2 models ignore disabled thinking; use adaptive")
            if is_m31 and minimax_reasoning_effort is None:
                raise ValueError(
                    "MiniMax M3.1 requires an explicit --minimax-reasoning-effort-a/b setting"
                )
            if not is_m31 and minimax_reasoning_effort is not None:
                raise ValueError(
                    "MiniMax reasoning effort is only supported by MiniMax M3.1 models"
                )
            self.minimax_reasoning_effort = minimax_reasoning_effort
        self.last_call_metadata: dict[str, Any] = {}
        self._system_prompt_sha256 = hashlib.sha256(
            self._SYSTEM_TEMPLATE.encode("utf-8")
        ).hexdigest()

    def benchmark_metadata(self) -> dict[str, Any]:
        reasoning_settings: dict[str, Any] = {}
        if self.provider == "minimax-api":
            reasoning_settings = {
                "thinking": {"type": self.minimax_thinking},
                "reasoning_split": self.reasoning_split,
            }
            if self.minimax_reasoning_effort is not None:
                reasoning_settings["reasoning_effort"] = self.minimax_reasoning_effort
        return {
            "kind": "hosted_language_model",
            "name": f"{self.provider}:{self.model}",
            "provider": self.provider,
            "model_requested": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "prompt_template": "fe7-link-arena-choice-v1",
            "prompt_template_sha256": self._system_prompt_sha256,
            "system_prompt": self._SYSTEM_TEMPLATE,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning_settings": reasoning_settings,
            "reasoning_capture": {
                "mode": "brief_user_visible_rationale_only",
                "provider_private_reasoning_content": "not_read_or_persisted",
                "reasoning_token_counts": "provider_usage_only_when_reported",
            },
            "own_team": self.own_team,
        }

    def _provider_request_parameters(self) -> dict[str, Any]:
        if self.provider != "minimax-api":
            return {}
        parameters: dict[str, Any] = {
            "thinking": {"type": self.minimax_thinking},
            "reasoning_split": self.reasoning_split,
        }
        if self.minimax_reasoning_effort is not None:
            parameters["reasoning_effort"] = self.minimax_reasoning_effort
        return parameters

    @staticmethod
    def _int_field(value: Any, key: str) -> int:
        result = value.get(key) if isinstance(value, dict) else None
        if isinstance(result, bool) or not isinstance(result, int):
            raise ValueError(f"model action field {key!r} must be an integer")
        return result

    def _request_decision(self, observation: dict[str, Any]) -> dict[str, Any]:
        key = os.environ.get(self.api_key_env)
        if not key:
            self.last_call_metadata = {
                "provider": self.provider,
                "model_requested": self.model,
                "error": f"required credential environment variable {self.api_key_env} is unset",
            }
            raise RuntimeError(self.last_call_metadata["error"])

        own, opponents = self._teams(observation)
        user_state = {
            "schema_version": 1,
            "seat": "1P" if self.side == "A" else "2P",
            "own_team": self.own_team,
            "own_units": own,
            "opposing_units": opponents,
            "game_state": observation.get("game_state", {}),
        }
        messages = [
            {"role": "system", "content": self._SYSTEM_TEMPLATE},
            {"role": "user", "content": json.dumps(
                user_state, sort_keys=True, separators=(",", ":"),
            )},
        ]
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            ("max_completion_tokens" if self.provider == "minimax-api" else "max_tokens"):
                self.max_completion_tokens,
            "stream": False,
        }
        body.update(self._provider_request_parameters())
        encoded_body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        prompt_text = json.dumps(messages, sort_keys=True, separators=(",", ":"))
        self.last_call_metadata = {
            "provider": self.provider,
            "model_requested": self.model,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "prompt_template": "fe7-link-arena-choice-v1",
            "system_prompt": self._SYSTEM_TEMPLATE,
            "policy_input": user_state,
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "request_sha256": hashlib.sha256(encoded_body).hexdigest(),
            "request_parameters": {
                "temperature": self.temperature,
                "max_completion_tokens": self.max_completion_tokens,
                "stream": False,
                "output_contract": "strict_json_object_validated_client_side",
                **self._provider_request_parameters(),
            },
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=encoded_body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.last_call_metadata["call_started_at"] = time.time()
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = response.status
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            self.last_call_metadata.update({
                "http_status": exc.code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": f"HTTP {exc.code}",
            })
            raise RuntimeError(f"{self.provider} completion failed with HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            self.last_call_metadata.update({
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": type(exc).__name__,
            })
            raise RuntimeError(f"{self.provider} completion failed: {type(exc).__name__}") from None

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if not isinstance(response_data, dict):
            self.last_call_metadata.update({"http_status": status_code, "latency_ms": elapsed_ms,
                                            "error": "non-object API response"})
            raise RuntimeError(f"{self.provider} returned a non-object response")
        choices = response_data.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            self.last_call_metadata.update({"http_status": status_code, "latency_ms": elapsed_ms,
                                            "error": "response is missing assistant JSON content"})
            raise RuntimeError(f"{self.provider} returned no assistant JSON content")

        self.last_call_metadata.update({
            "http_status": status_code,
            "latency_ms": elapsed_ms,
            "request_id": response_data.get("id"),
            "model_resolved": response_data.get("model"),
            "usage": response_data.get("usage"),
            "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
        try:
            action = json.loads(content)
        except json.JSONDecodeError:
            self.last_call_metadata["error"] = "assistant content was not valid JSON"
            raise RuntimeError(f"{self.provider} action was not valid JSON") from None
        if not isinstance(action, dict):
            self.last_call_metadata["error"] = "assistant JSON was not an object"
            raise RuntimeError(f"{self.provider} action was not a JSON object")
        expected_fields = {"attacker_id", "defender_id", "weapon_id", "rationale"}
        if set(action) != expected_fields:
            self.last_call_metadata["error"] = "assistant JSON did not match the action schema"
            raise RuntimeError(f"{self.provider} action did not match the required JSON schema")
        try:
            for field in ("attacker_id", "defender_id", "weapon_id"):
                self._int_field(action, field)
        except ValueError as exc:
            self.last_call_metadata["error"] = str(exc)
            raise
        rationale = action.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 400:
            self.last_call_metadata["error"] = "rationale must be a non-empty string of at most 400 characters"
            raise RuntimeError(f"{self.provider} rationale did not match the required schema")
        self.last_call_metadata["action"] = {
            key: action.get(key) for key in ("attacker_id", "defender_id", "weapon_id")
        }
        self.last_call_metadata["rationale"] = rationale.strip()
        # Store the model-visible structured completion exactly as returned;
        # provider-only reasoning fields are intentionally never read or saved.
        self.last_call_metadata["response_text"] = content
        return action

    def choose_matchup(self, observation: dict[str, Any]) -> AgentDecision:
        action = self._request_decision(observation)
        attacker_id = self._int_field(action, "attacker_id")
        defender_id = self._int_field(action, "defender_id")
        weapon_id = self._int_field(action, "weapon_id")
        own_units, opposing_units = self._teams(observation)
        attacker = next((u for u in own_units if int(u.get("character_id", -1)) == attacker_id), None)
        defender = next((u for u in opposing_units if int(u.get("character_id", -1)) == defender_id), None)
        if attacker is None or defender is None:
            raise ValueError("model action selected a unit outside the current legal rosters")
        if self._hp_current(attacker) <= 0 or self._hp_current(defender) <= 0:
            raise ValueError("model action selected a fallen Link Arena unit")
        if weapon_id not in FE7_COMBAT_WEAPON_IDS:
            raise ValueError(f"model action selected an unclassified FE7 combat weapon ID: {weapon_id}")
        inventory = attacker.get("inventory", [])
        item = next((value for value in inventory if isinstance(value, dict)
                     and int(value.get("id", -1)) == weapon_id
                     and int(value.get("uses", 0)) > 0), None) if isinstance(inventory, list) else None
        if item is None:
            raise ValueError("model action selected a weapon not usable by the chosen attacker")
        slot_value = item.get("slot")
        if isinstance(slot_value, bool) or not isinstance(slot_value, int):
            raise ValueError("selected inventory item has no integer FE7 slot")
        weapon = WEAPONS.get(weapon_id)
        weapon_name = item.get("name")
        if not isinstance(weapon_name, str) or not weapon_name:
            weapon_name = weapon.name if weapon is not None else f"FE7 item 0x{weapon_id:02X}"
        return AgentDecision(
            side=self.side,
            attacker_id=attacker_id,
            defender_id=defender_id,
            weapon_id=weapon_id,
            weapon_name=weapon_name,
            inventory_slot=slot_value,
            score=None,
            worst_reply_item=None,
            rationale=self.last_call_metadata["rationale"],
        )

    @staticmethod
    def _hp_current(unit: dict[str, Any]) -> int:
        hp = unit.get("hp")
        current = hp.get("current") if isinstance(hp, dict) else None
        return current if isinstance(current, int) and not isinstance(current, bool) else 0
