from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.link_arena.series import DecisionLedger
from tools.audit_link_arena_ledger import audit_ledger
from tools.prune_legacy_link_arena_ledger import prune_legacy_ledger


def _decision(side: str, decision_id: str) -> dict:
    return {
        "type": "decision",
        "timestamp": 1.0,
        "decision_id": decision_id,
        "side": side,
        "seat": "1P" if side == "A" else "2P",
        "bridge_side": side,
        "decision": {"action": "end_turn"},
        "observation_id": f"observation-{decision_id}",
        "generation": 1,
        "observation": {},
        "policy": {"name": "local-fixture"},
        "policy_input_sha256": "a" * 64,
        "inference": {"provider": "local"},
    }


class PruneLegacyLinkArenaLedgerTests(unittest.TestCase):
    def test_dry_run_does_not_modify_source_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            ledger = DecisionLedger(data_dir, backfill=False)
            ledger.record("old-match", _decision("A", "old"), trace_origin="legacy_backfill")
            before = ledger.path.read_bytes()
            result = prune_legacy_ledger(ledger.path, apply=False)
            self.assertFalse(result["applied"])
            self.assertEqual(ledger.path.read_bytes(), before)

    def test_prune_archives_source_quarantines_known_corruption_and_prevents_reimport(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            ledger = DecisionLedger(data_dir, backfill=False)
            ledger.record("old-match", _decision("A", "old"), trace_origin="legacy_backfill")
            ledger.record("live-match", _decision("B", "live"), trace_origin="live")
            malformed = b'81319,"trace_origin":"legacy_backfill"}\n'
            with ledger.path.open("ab") as stream:
                stream.write(malformed)
            original = ledger.path.read_bytes()

            result = prune_legacy_ledger(ledger.path, apply=True)

            self.assertTrue(result["applied"])
            self.assertEqual(result["legacy_backfill_rows_removed"], 1)
            self.assertEqual(result["malformed_lines_quarantined"][0]["line"], 3)
            archive = ledger.path.parent / result["archive"]
            self.assertEqual(archive.read_bytes(), original)
            summary, rows = audit_ledger(ledger.path)
            self.assertEqual(summary["malformed_lines"], [])
            self.assertEqual(summary["trace_origins"], {"live": 1})
            self.assertEqual([row["event_id"] for row in rows], [
                json.loads(original.splitlines()[1])["event_id"],
            ])

            old_match = data_dir / "old-match"
            old_match.mkdir()
            (old_match / "session.json").write_text(
                json.dumps({"match_id": "old-match"}), encoding="utf-8",
            )
            (old_match / "minimax-autoplay.jsonl").write_text(json.dumps({
                "type": "decision",
                "side": "A",
                "timestamp": 2.0,
                "decision": {"action": "end_turn"},
            }) + "\n", encoding="utf-8")

            restarted = DecisionLedger(data_dir)
            self.assertEqual(restarted.path.read_bytes(), ledger.path.read_bytes())

    def test_rejects_unexpected_malformed_content_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            ledger = DecisionLedger(data_dir, backfill=False)
            ledger.record("live-match", _decision("A", "live"), trace_origin="live")
            with ledger.path.open("ab") as stream:
                stream.write(b"unexpected corruption\n")
            before = ledger.path.read_bytes()
            with self.assertRaisesRegex(ValueError, "unexpected malformed line"):
                prune_legacy_ledger(ledger.path, apply=True)
            self.assertEqual(ledger.path.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
