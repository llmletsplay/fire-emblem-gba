"""Legal-action agents for FE8 Versus. The ROM is the rules authority."""

from __future__ import annotations

import hashlib
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from types import SimpleNamespace
from src.link_arena.agents import OpenAICompatibleAgent

SYSTEM = (
    "You are playing Fire Emblem Versus, a turn-based tactical battle. "
    "Choose exactly one action from legal_actions in the supplied observation. "
    "Return only JSON with action_id (the exact supplied string) and rationale "
    "(a short public explanation, at most 240 characters). No hidden reasoning. "
    "Use observed units, terrain, objective and enemy castles. Seize explicitly "
    "when enabled; Wait on a castle does not capture it. End ends your whole phase. "
    "Avoid surrender. Every unit is level 20 with fixed preset stats."
)


class LocalAgent:
    """Deterministic tactical baseline; not a hosted model or exact FE8 simulator."""

    def __init__(self, config):
        self.config = config
        self.last_call_metadata = {}

    def choose(self, observation):
        units = {u["id"]: u for u in observation["units"]}
        enemies = [
            u
            for u in units.values()
            if u["seat"] != observation["seat"] and not u["dead"]
        ]
        actions = observation["legal_actions"]
        seize = [a for a in actions if a["type"] == "seize"]
        attacks = [a for a in actions if a["type"] == "attack"]
        heals = [a for a in actions if a["type"] == "heal"]
        pots = [
            a
            for a in actions
            if a["type"] == "vulnerary"
            and units[a["actor"]]["hp"] < units[a["actor"]]["max_hp"] / 2
        ]
        moves = [
            a
            for a in actions
            if a["type"] == "wait" and units[a["actor"]]["role"] != "healer"
        ]
        if seize:
            action = seize[0]
        elif attacks:
            action = min(attacks, key=lambda a: units[a["target"]]["hp"])
        elif heals:
            action = min(
                heals,
                key=lambda a: units[a["target"]]["hp"] / units[a["target"]]["max_hp"],
            )
        elif pots:
            action = pots[0]
        elif moves and enemies:
            action = min(
                moves,
                key=lambda a: min(
                    abs(a["x"] - e["x"]) + abs(a["y"] - e["y"]) for e in enemies
                ),
            )
        else:
            action = next(a for a in actions if a["type"] == "end")
        return {
            "action_id": action["id"],
            "rationale": "Local tactical baseline: " + action["type"],
        }


class HumanAgent:
    """Terminal hotseat controller selecting only native legal actions."""

    def __init__(self, config):
        self.config = config
        self.last_call_metadata = {"provider": "human"}

    def choose(self, observation):
        actions = observation["legal_actions"]
        print(f"\n{self.config['id']} · {'Red' if observation['active_seat'] else 'Blue'} "
              f"· round {observation['round']} · action {observation['sequence']}", flush=True)
        print("Coordinates are zero-based: x right, y down. 'units' shows the roster.\n"
              "Search with /text (e.g. /attack), 'next' pages, 'all' resets.\n"
              "Enter a displayed number or exact action ID; Ctrl-C stops the match.")
        filtered, offset = list(enumerate(actions)), 0
        while True:
            for index, action in filtered[offset:offset + 20]:
                print(f"[{index}] {json.dumps(action, separators=(',', ':'))}")
            print(f"Showing {offset + 1 if filtered else 0}–{min(offset + 20, len(filtered))} "
                  f"of {len(filtered)} matches", flush=True)
            try:
                value = input("Action > ").strip()
            except EOFError:
                raise RuntimeError("Human input closed; run in an interactive terminal") from None
            if value == "units":
                print(json.dumps(observation['units'], indent=2))
            elif value == "next":
                offset = offset + 20 if offset + 20 < len(filtered) else 0
            elif value == "all":
                filtered, offset = list(enumerate(actions)), 0
            elif value.startswith("/"):
                query = value[1:].lower()
                filtered = [(i, a) for i, a in enumerate(actions)
                            if query in json.dumps(a).lower()]
                offset = 0
            else:
                selected = next((a for a in actions if a['id'] == value), None)
                if selected is None and value.isdecimal():
                    index = int(value)
                    selected = actions[index] if index < len(actions) else None
                if selected is not None:
                    print("Selected: " + json.dumps(selected), flush=True)
                    confirm = input("Submit this action? [y/N] > ").strip().lower()
                    if confirm in {"y", "yes"}:
                        return {"action_id": selected['id'],
                                "rationale": "Human selected " + selected['type']}
                else:
                    print("Invalid action. Choose a current legal action.")


class ModelAgent:
    def __init__(self, config):
        self.config = config
        # Reuse the existing project's provider defaults and MiniMax reasoning settings.
        defaults = OpenAICompatibleAgent._PROVIDERS[config["provider"]]
        p = SimpleNamespace(
            provider=config["provider"],
            model=config["model"],
            base_url=config.get("base_url", defaults["base_url"]).rstrip("/"),
            api_key_env=config.get("api_key_env", defaults["api_key_env"]),
            timeout_seconds=config.get("timeout_seconds", 120),
            temperature=config.get("temperature", 0),
            max_completion_tokens=config.get("max_completion_tokens", 4096),
        )
        if p.timeout_seconds <= 0 or p.max_completion_tokens < 1:
            raise ValueError("Provider timeout and token limit must be positive")
        thinking = config.get("minimax_thinking", "adaptive")
        effort = config.get("minimax_reasoning_effort")
        if thinking not in ["adaptive", "disabled"] or effort not in [
            None,
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ]:
            raise ValueError("Unsupported MiniMax reasoning setting")
        if p.provider == "chutes" and any(
            k in config for k in ["minimax_thinking", "minimax_reasoning_effort"]
        ):
            raise ValueError("MiniMax settings require minimax-api provider")
        m31 = "m3.1" in p.model.lower()
        m2 = "m2." in p.model.lower() or p.model.lower().endswith("-m2")
        if p.provider == "minimax-api" and ((m31 or m2) and thinking == "disabled"):
            raise ValueError("This MiniMax model requires adaptive thinking")
        if p.provider == "minimax-api" and (
            (m31 and effort is None) or (not m31 and effort is not None)
        ):
            raise ValueError("Set an explicit reasoning effort only for MiniMax M3.1")
        self.parameters = (
            {"thinking": {"type": thinking}, "reasoning_split": True}
            if p.provider == "minimax-api"
            else {}
        )
        if effort is not None:
            self.parameters["reasoning_effort"] = effort
        self.settings = p
        self.last_call_metadata = {}

    def choose(self, observation):
        p = self.settings
        key = os.environ.get(p.api_key_env)
        if not key:
            raise RuntimeError(
                f"Missing credential environment variable: {p.api_key_env}"
            )
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(observation, separators=(",", ":"))},
        ]
        payload = {
            "model": p.model,
            "messages": messages,
            "temperature": p.temperature,
            "stream": False,
            (
                "max_completion_tokens" if p.provider == "minimax-api" else "max_tokens"
            ): p.max_completion_tokens,
            **self.parameters,
        }
        encoded = json.dumps(payload).encode()
        self.last_call_metadata = {
            "provider": p.provider,
            "model_requested": p.model,
            "prompt_sha256": hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
        }
        started = time.monotonic()
        request = Request(
            p.base_url + "/chat/completions",
            data=encoded,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=p.timeout_seconds) as response:
                data = json.load(response)
            choice = data["choices"][0]["message"]["content"]
            decision = json.loads(choice)
        except HTTPError as exc:
            raise RuntimeError(f"{p.provider} HTTP {exc.code}") from None
        except (URLError, OSError, ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError(
                f"{p.provider} failed or returned invalid JSON content"
            ) from None
        self.last_call_metadata.update(
            latency_ms=round((time.monotonic() - started) * 1000),
            model_resolved=data.get("model"),
            usage=data.get("usage"),
        )
        if (
            not isinstance(decision, dict)
            or set(decision) != {"action_id", "rationale"}
            or not isinstance(decision["rationale"], str)
            or len(decision["rationale"]) > 240
            or decision["action_id"]
            not in {a["id"] for a in observation["legal_actions"]}
        ):
            raise RuntimeError(
                "Model returned a decision outside the legal-action schema"
            )
        return decision


def make_agent(config):
    return {"local": LocalAgent, "human": HumanAgent}.get(config["provider"], ModelAgent)(config)
