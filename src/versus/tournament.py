"""Balanced round-robin scheduling, durable results, and native Versus matches."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid

from .agents import make_agent

ROOT = Path(__file__).resolve().parents[2]
SUBMODULE = ROOT / "vendor/fire-emblem-versus"


@contextmanager
def output_lock(output):
    """One writer per tournament directory, including across processes."""
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "runner.lock").open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Another runner owns this output directory") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)


def load_config(path):
    config = json.loads(Path(path).read_text())
    entrants = config.get("entrants", [])
    if len(entrants) < 2 or len({e.get("id") for e in entrants}) != len(entrants):
        raise ValueError("At least two entrants with unique IDs are required")
    for e in entrants:
        if not isinstance(e.get("id"), str) or not e["id"].strip():
            raise ValueError("Entrant IDs must be nonempty strings")
        if e.get("provider") not in {"local", "chutes", "minimax-api"}:
            raise ValueError("Provider must be local, chutes or minimax-api")
        if e["provider"] != "local" and not e.get("model"):
            raise ValueError("Hosted entrants require an exact model ID")
        if any(k in e for k in ("api_key", "token", "password")):
            raise ValueError(
                "Store keys in environment variables, not tournament config"
            )
        make_agent(
            e
        )  # Validate provider/model reasoning options without making API calls.
    if not config.get("scenarios"):
        raise ValueError("At least one scenario is required")
    if (
        type(config.get("repetitions", 1)) is not int
        or config.get("repetitions", 1) < 1
    ):
        raise ValueError("repetitions must be a positive integer")
    for field, minimum in [("max_actions", 1), ("action_delay_seconds", 0)]:
        value = config.get(field, 1000 if field == "max_actions" else 0.5)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < minimum
        ):
            raise ValueError(f"{field} must be at least {minimum}")
    return config


def schedule(config):
    games = []
    for pair in itertools.combinations(config["entrants"], 2):
        for si, scenario in enumerate(config["scenarios"]):
            for rep in range(config.get("repetitions", 1)):
                # Cross seat assignment with opening army: each entrant opens once on each seat.
                for swap in range(2):
                    for opener in range(2):
                        seats = pair[::-1] if swap else pair
                        parties = scenario.get("parties", ["balanced", "balanced"])
                        if len(parties) != 2:
                            raise ValueError(
                                "Scenario parties must contain two preset IDs"
                            )
                        games.append(
                            {
                                "id": len(games),
                                "entrants": [e["id"] for e in seats],
                                "map": scenario["map"],
                                "parties": parties[::-1] if swap else parties,
                                "objective": scenario.get("objective", "either"),
                                "opener": opener,
                                "scenario": si,
                                "repetition": rep,
                            }
                        )
    return games


def standings(config, results):
    table = {
        e["id"]: dict(id=e["id"], wins=0, losses=0, draws=0, played=0, points=0)
        for e in config["entrants"]
    }
    for r in results:
        for seat, entrant in enumerate(r["entrants"]):
            row = table[entrant]
            row["played"] += 1
            if r["outcome"] == 3:
                row["draws"] += 1
                row["points"] += 1
            elif r["outcome"] == seat + 1:
                row["wins"] += 1
                row["points"] += 3
            else:
                row["losses"] += 1
    return sorted(table.values(), key=lambda r: (-r["points"], -r["wins"], r["id"]))


def engine_session(engine):
    source = engine / "tools/versus/agents/session.py"
    if not source.exists() or not (engine / "build/versus/agent-bridge").exists():
        raise RuntimeError(
            "Build and test the submodule first; see docs/VERSUS_TOURNAMENT.md"
        )
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("_fe8_versus_session", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Session


class Tournament:
    def __init__(self, config, output, engine, session_factory=None):
        self.config = config
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.engine = Path(engine)
        self.catalog = json.loads(
            (self.engine / "build/versus/catalog.json").read_text()
        )
        self.manifest = json.loads(
            (self.engine / "build/versus/manifest.json").read_text()
        )
        self.games = schedule(config)
        self.entrants = {e["id"]: e for e in config["entrants"]}
        self._validate_scenarios()
        self.session_factory = session_factory or engine_session(self.engine)
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.identity = hashlib.sha256(
            json.dumps(
                {"config": config, "rom_sha256": self.manifest["rom_sha256"]},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.video_directory = None
        self.results = []
        ledger = self.output / "results.json"
        if ledger.exists():
            saved = json.loads(ledger.read_text())
            if saved["identity"] != self.identity:
                raise ValueError(
                    "Output belongs to a different config or ROM; use another output directory"
                )
            self.results = saved["results"]
        self.state = {
            "status": "ready",
            "completed": len(self.results),
            "total": len(self.games),
            "standings": standings(config, self.results),
            "match": None,
            "observation": None,
            "decisions": [None, None],
        }
        snapshot_path = self.output / "stream-state.json"
        if ledger.exists() and snapshot_path.exists():
            previous = json.loads(snapshot_path.read_text())
            for key in ["match", "observation", "decision", "decisions", "last_result"]:
                if key in previous:
                    self.state[key] = previous[key]
        if self.results and not self.state.get("observation"):
            last = self.results[-1]
            events = self.output / last.get("evidence", "") / "events.jsonl"
            if events.is_file():
                for line in events.read_text().splitlines():
                    row = json.loads(line)
                    if row["kind"] == "observation":
                        self.state["observation"] = row["data"]
                self.state["match"] = {
                    **last,
                    "models": [self.entrants[e] for e in last["entrants"]],
                }
                self.state["last_result"] = last
                self.video_directory = self.output / last["evidence"] / "frames"
        if self.results and self.video_directory is None:
            self.video_directory = (
                self.output / self.results[-1].get("evidence", "") / "frames"
            )
        self.publish()

    def _validate_scenarios(self):
        for g in self.games:
            for key, values in [
                ("map", self.catalog["maps"]),
                ("objective", self.catalog["objectives"]),
            ]:
                ids = [v["id"] if isinstance(v, dict) else v for v in values]
                if g[key] not in ids:
                    raise ValueError(f"Unknown {key}: {g[key]}")
            if any(
                p not in [p["id"] for p in self.catalog["parties"]]
                for p in g["parties"]
            ):
                raise ValueError("Unknown party preset")

    def publish(self, **updates):
        with self.lock:
            self.state.update(updates)
            atomic_json(self.output / "stream-state.json", self.state)

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    def run(self):
        finished = {r["id"] for r in self.results}
        for game in self.games:
            if game["id"] in finished:
                continue
            if self.stop.is_set():
                self.publish(status="stopped")
                return
            try:
                result = self.play(game)
            except Exception as exc:
                # Fail closed: neither provider/transport failure nor illegal output is a game loss.
                self.publish(status="error", error=str(exc))
                return
            self.results.append(result)
            atomic_json(
                self.output / "results.json",
                {"identity": self.identity, "results": self.results},
            )
            self.publish(
                completed=len(self.results),
                standings=standings(self.config, self.results),
                last_result=result,
            )
        self.publish(status="complete")

    def play(self, game):
        maps = [m["id"] for m in self.catalog["maps"]]
        parties = [p["id"] for p in self.catalog["parties"]]
        evidence = self.output / f"game-{game['id']:04}-{uuid.uuid4().hex[:8]}"
        s = self.session_factory(
            red=bool(game["opener"]),
            map_id=maps.index(game["map"]),
            blue_party=parties.index(game["parties"][0]),
            red_party=parties.index(game["parties"][1]),
            objective=self.catalog["objectives"].index(game["objective"]),
            evidence=evidence,
            video=True,
        )
        self.video_directory = evidence / "frames"
        agents = [make_agent(self.entrants[e]) for e in game["entrants"]]
        count = 0
        public_match = {
            **game,
            "models": [self.entrants[e] for e in game["entrants"]],
            "rom_sha256": self.manifest["rom_sha256"],
        }
        self.publish(
            status="playing",
            match=public_match,
            observation=None,
            decision=None,
            decisions=[None, None],
            error=None,
        )
        try:
            with (evidence / "decisions.jsonl").open("w") as log:
                while not self.stop.is_set():
                    stable = s.stable()[0]
                    o = s.observe(stable["active"])
                    self.publish(observation=o)
                    if o["outcome"]:
                        if o["outcome"] not in [1, 2, 3]:
                            raise RuntimeError("Native ROM match aborted")
                        return {
                            **game,
                            "outcome": o["outcome"],
                            "victory_reason": o["victory_reason"],
                            "actions": count,
                            "round": o["round"],
                            "match_id": s.id,
                            "rom_sha256": self.manifest["rom_sha256"],
                            "evidence": evidence.name,
                        }
                    if count >= self.config.get("max_actions", 1000):
                        raise RuntimeError(
                            "Action limit reached without native outcome"
                        )
                    seat = o["active_seat"]
                    self.publish(status="thinking", thinking_seat=seat)
                    decision = agents[seat].choose(o)
                    if decision["action_id"] not in {
                        a["id"] for a in o["legal_actions"]
                    }:
                        raise RuntimeError("Agent selected an illegal action")
                    public_decision = {
                        "seat": seat,
                        "sequence": o["sequence"],
                        "round": o["round"],
                        **decision,
                    }
                    decisions = self.snapshot()["decisions"]
                    decisions[seat] = public_decision
                    self.publish(
                        status="playing", decision=public_decision, decisions=decisions
                    )
                    if self.stop.wait(self.config.get("action_delay_seconds", 0.5)):
                        break
                    request = dict(
                        match_id=s.id,
                        sequence=o["sequence"],
                        state_hash=o["state_hash"],
                        action_id=decision["action_id"],
                        request_id=uuid.uuid4().hex,
                    )
                    response = s.act(seat, request)
                    if not response.get("accepted"):
                        raise RuntimeError("Native command was not accepted")
                    count += 1
                    log.write(
                        json.dumps(
                            {
                                "sequence": response["sequence"],
                                "entrant": game["entrants"][seat],
                                "decision": decision,
                                "metadata": agents[seat].last_call_metadata,
                            }
                        )
                        + "\n"
                    )
                    log.flush()
            raise RuntimeError("Tournament stopped before native outcome")
        finally:
            s.close()
