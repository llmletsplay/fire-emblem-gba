import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.versus.agents import ModelAgent
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
