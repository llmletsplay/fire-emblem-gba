import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.versus.agents import ModelAgent, HumanAgent
from src.versus.tournament import (
    Tournament,
    load_config,
    schedule,
    standings,
    output_lock,
)
from src.versus.stream import server

CONFIG = {
    "entrants": [
        {"id": "A", "provider": "local"},
        {"id": "B", "provider": "local"},
        {"id": "C", "provider": "local"},
    ],
    "scenarios": [
        {
            "map": "forest-forts",
            "parties": ["balanced", "mobile"],
            "objective": "either",
        }
    ],
}


class TournamentTests(unittest.TestCase):
    def test_human_rejects_invalid_and_requires_confirmation(self):
        observation = {"active_seat": 1, "round": 2, "sequence": 3,
                       "units": [], "legal_actions": [
                           {"id": "end-3", "type": "end"},
                           {"id": "attack-3", "type": "attack"}]}
        with patch("builtins.input", side_effect=["999", "/attack", "1", "n", "units", "next", "all", "attack-3", "y"]), patch("builtins.print"):
            decision = HumanAgent({"id": "Player"}).choose(observation)
        self.assertEqual(decision["action_id"], "attack-3")
        with patch("builtins.input", side_effect=EOFError), patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "interactive terminal"):
                HumanAgent({"id": "Player"}).choose(observation)

    def test_single_match_and_human_examples(self):
        for name in ["human-agent", "human-human"]:
            config = load_config(Path(__file__).parents[1] / f"examples/versus-{name}.json")
            games = schedule(config)
            self.assertEqual(len(games), 1)
            self.assertEqual(games[0]["opener"], 0)
            self.assertEqual(games[0]["entrants"][0], config["entrants"][0]["id"])
        with tempfile.TemporaryDirectory() as d:
            c = copy.deepcopy(CONFIG)
            c["format"] = "single"
            p = Path(d) / "config.json"
            p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError, "two entrants"):
                load_config(p)

    def test_seats_openers_and_parties_are_balanced(self):
        games = schedule(CONFIG)
        self.assertEqual(len(games), 12)
        for a, b in [("A", "B"), ("A", "C"), ("B", "C")]:
            pair = [g for g in games if set(g["entrants"]) == {a, b}]
            for entrant in [a, b]:
                self.assertEqual(
                    {(g["entrants"].index(entrant), g["opener"]) for g in pair},
                    {(0, 0), (0, 1), (1, 0), (1, 1)},
                )
            for g in pair:
                self.assertEqual(g["parties"][g["entrants"].index(a)], "balanced")

    def test_only_one_runner_can_own_output(self):
        with tempfile.TemporaryDirectory() as d:
            with output_lock(d):
                with self.assertRaises(RuntimeError):
                    with output_lock(d):
                        pass
            with output_lock(d):
                pass

    def test_points_follow_native_outcomes(self):
        r = standings(
            CONFIG,
            [
                {"entrants": ["A", "B"], "outcome": 2},
                {"entrants": ["C", "B"], "outcome": 3},
            ],
        )
        self.assertEqual(r[0]["id"], "B")
        self.assertEqual(r[0]["points"], 4)
        self.assertEqual(r[0]["played"], 2)

    def test_credential_values_cannot_be_in_config(self):
        with tempfile.TemporaryDirectory() as d:
            c = copy.deepcopy(CONFIG)
            c["entrants"][0]["api_key"] = "secret"
            p = Path(d) / "config.json"
            p.write_text(json.dumps(c))
            with self.assertRaises(ValueError):
                load_config(p)

    def test_provider_request_and_illegal_output(self):
        seen = []
        answer = {"action_id": "legal", "rationale": "Move toward objective"}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                seen.append(
                    (
                        self.path,
                        self.headers.get("Authorization"),
                        json.loads(
                            self.rfile.read(int(self.headers["Content-Length"]))
                        ),
                    )
                )
                payload = json.dumps(
                    {
                        "model": "resolved",
                        "usage": {"total_tokens": 10},
                        "choices": [{"message": {"content": json.dumps(answer)}}],
                    }
                ).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)

        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict("os.environ", {"TEST_VERSUS_KEY": "test-only-key"}):
                for provider, model in [
                    ("chutes", "test-model"),
                    ("minimax-api", "MiniMax-M2.5"),
                ]:
                    agent = ModelAgent(
                        {
                            "id": "test",
                            "provider": provider,
                            "model": model,
                            "base_url": f"http://127.0.0.1:{http.server_port}/v1",
                            "api_key_env": "TEST_VERSUS_KEY",
                        }
                    )
                    o = {"legal_actions": [{"id": "legal"}]}
                    self.assertEqual(agent.choose(o)["action_id"], "legal")
                    self.assertNotIn(
                        "test-only-key", json.dumps(agent.last_call_metadata)
                    )
                    payload = seen[-1][2]
                    self.assertEqual(seen[-1][0], "/v1/chat/completions")
                    self.assertEqual(seen[-1][1], "Bearer test-only-key")
                    self.assertIn(
                        (
                            "max_completion_tokens"
                            if provider == "minimax-api"
                            else "max_tokens"
                        ),
                        payload,
                    )
                    if provider == "minimax-api":
                        self.assertTrue(payload["reasoning_split"])
                answer["action_id"] = "illegal"
                with self.assertRaises(RuntimeError):
                    agent.choose(o)
        finally:
            http.shutdown()
            http.server_close()

    def make_tournament(self, directory):
        engine = Path(directory) / "engine"
        output = Path(directory) / "output"
        (engine / "build/versus").mkdir(parents=True)
        (engine / "build/versus/catalog.json").write_text(
            json.dumps(
                {
                    "maps": [{"id": "forest-forts"}],
                    "parties": [{"id": "balanced"}, {"id": "mobile"}],
                    "objectives": ["either"],
                }
            )
        )
        (engine / "build/versus/manifest.json").write_text(
            json.dumps({"rom_sha256": "test"})
        )
        return Tournament(CONFIG, output, engine, session_factory=lambda **kwargs: None)

    def test_failed_match_is_not_a_loss_and_resume_skips_completed(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            first = t.games[0]

            def play(g):
                if g["id"] == 0:
                    return {**g, "outcome": 1}
                raise RuntimeError("Provider unavailable")

            t.play = play
            t.run()
            self.assertEqual(t.snapshot()["status"], "error")
            self.assertEqual(len(t.results), 1)
            self.assertEqual(sum(r["played"] for r in t.snapshot()["standings"]), 2)
            resumed = Tournament(
                CONFIG, t.output, t.engine, session_factory=lambda **k: None
            )
            called = []
            resumed.play = lambda g: (called.append(g["id"]) or {**g, "outcome": 3})
            resumed.run()
            self.assertNotIn(first["id"], called)
            self.assertEqual(resumed.snapshot()["status"], "complete")

    def test_decisions_keep_both_sides_and_reset_between_games(self):
        class Session:
            id = "test-match"
            sequence = 0

            def __init__(self, **kwargs):
                kwargs["evidence"].mkdir(parents=True)

            def stable(self):
                return [{"active": self.sequence % 2}]

            def observe(self, seat):
                return {
                    "active_seat": seat,
                    "sequence": self.sequence,
                    "round": 1,
                    "state_hash": "test",
                    "units": [],
                    "legal_actions": [{"id": "end", "type": "end"}],
                    "outcome": 1 if self.sequence == 2 else 0,
                    "victory_reason": "elimination",
                }

            def act(self, seat, request):
                self.sequence += 1
                return {"accepted": True, "sequence": self.sequence}

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            t.config["action_delay_seconds"] = 0
            t.session_factory = Session
            t.play(t.games[0])
            decisions = t.snapshot()["decisions"]
            self.assertEqual([v["seat"] for v in decisions], [0, 1])
            self.assertEqual([v["sequence"] for v in decisions], [0, 1])
            snapshots = []
            publish = t.publish

            def capture(**updates):
                publish(**updates)
                snapshots.append(t.snapshot())

            t.publish = capture
            t.play(t.games[1])
            self.assertEqual(snapshots[0]["decisions"], [None, None])

    def test_native_human_uses_ui_and_keeps_result_window(self):
        instances = []
        class NativeSession:
            id = 'native-ui-test'
            sequence = 0
            closed = False
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                kwargs['evidence'].mkdir(parents=True)
                instances.append(self)
            def stable(self):
                return [{'active': self.sequence % 2}]
            def observe(self, seat):
                return {'active_seat': seat, 'sequence': self.sequence, 'round': 1,
                        'outcome': 1 if self.sequence == 2 else 0, 'victory_reason': 'surrender'}
            def human_action(self, seat, sequence, stop):
                self.assertion = (seat, sequence)
                self.sequence += 1
                return {'accepted': True, 'sequence': self.sequence}
            def act(self, *args):
                raise AssertionError('Human input must not use the agent mailbox')
            def close(self):
                self.closed = True
        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            t.desktop, t.browser_video = True, False
            for e in t.entrants.values():
                e['provider'] = 'human'
            t.session_factory = NativeSession
            with patch('src.versus.agents.HumanAgent.choose', side_effect=AssertionError('No terminal input')):
                result = t.play(t.games[0])
            self.assertEqual(result['outcome'], 1)
            self.assertEqual(instances[0].kwargs['human_seats'], 3)
            self.assertFalse(instances[0].kwargs['video'])
            self.assertIsNone(t.video_directory)
            self.assertFalse(instances[0].closed)
            t.close()
            self.assertTrue(instances[0].closed)
            self.assertEqual(t.snapshot()['decisions'][1]['action_id'], 'native-ui')

    def test_native_window_is_reused_for_next_game(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            previous = Mock()
            t.live_session, t.desktop, t.browser_video = previous, True, False
            # Constructor failure must leave the previous owner available for cleanup.
            t.session_factory = Mock(side_effect=RuntimeError('setup failed'))
            with self.assertRaisesRegex(RuntimeError, 'setup failed'):
                t.play(t.games[0])
            self.assertIs(t.session_factory.call_args.kwargs['reuse'], previous)
            previous.close.assert_not_called()
            t.close()
            previous.close.assert_called_once()

    def test_cli_starts_no_server_by_default(self):
        from tools import versus_tournament as cli
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config.json'
            p.write_text(json.dumps(CONFIG))
            runner = Mock()
            runner.snapshot.return_value = {'status': 'complete'}
            runner.results = []
            with patch('sys.argv', ['versus_tournament.py', str(p), '--output', str(Path(d) / 'run'), '--exit-on-complete']), patch.object(cli, 'Tournament', return_value=runner) as constructor, patch.object(cli, 'server') as http, patch('builtins.print'):
                self.assertEqual(cli.main(), 0)
            http.assert_not_called()
            self.assertTrue(constructor.call_args.kwargs['desktop'])
            self.assertFalse(constructor.call_args.kwargs['browser_video'])
            runner.close.assert_called_once()

    def test_resume_rejects_changed_config(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            t.play = lambda g: {**g, "outcome": 3}
            t.run()
            c = copy.deepcopy(CONFIG)
            c["repetitions"] = 2
            with self.assertRaises(ValueError):
                Tournament(c, t.output, t.engine, session_factory=lambda **k: None)

    def test_native_video_route_uses_emulator_pixels(self):
        from PIL import Image
        import io

        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            t.video_directory = Path(d) / "frames"
            t.video_directory.mkdir()
            Image.new("RGB", (240, 160), (17, 34, 51)).save(
                t.video_directory / "seat-0.ppm"
            )
            http = server(t, 0)
            threading.Thread(target=http.serve_forever, daemon=True).start()
            try:
                with urlopen(f"http://127.0.0.1:{http.server_port}/video/0.png") as r:
                    self.assertEqual(r.headers["Content-Type"], "image/png")
                    image = Image.open(io.BytesIO(r.read()))
                self.assertEqual(image.size, (240, 160))
                self.assertEqual(image.getpixel((0, 0)), (17, 34, 51))
            finally:
                http.shutdown()
                http.server_close()

    def test_stream_is_read_only_and_has_no_session_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            t = self.make_tournament(d)
            http = server(t, 0)
            threading.Thread(target=http.serve_forever, daemon=True).start()
            try:
                with urlopen(f"http://127.0.0.1:{http.server_port}/state") as r:
                    data = json.load(r)
                self.assertNotIn("keys", data)
                with urlopen(f"http://127.0.0.1:{http.server_port}/") as r:
                    self.assertIn(b"Live native Fire Emblem emulator video", r.read())
            finally:
                http.shutdown()
                http.server_close()


if __name__ == "__main__":
    unittest.main()
