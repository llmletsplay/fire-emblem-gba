from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.link_arena import _STOP_AFTER_MATCH_REQUEST, _consume_stop_after_current_match


class SafeHandoffRequestTests(unittest.TestCase):
    def test_missing_request_does_not_stop_the_series(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertFalse(_consume_stop_after_current_match(Path(temporary)))

    def test_request_is_consumed_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            request = data_dir / "series" / _STOP_AFTER_MATCH_REQUEST
            request.parent.mkdir(parents=True)
            request.write_text("stop after verified result", encoding="ascii")

            self.assertTrue(_consume_stop_after_current_match(data_dir))
            self.assertFalse(request.exists())
            self.assertFalse(_consume_stop_after_current_match(data_dir))


if __name__ == "__main__":
    unittest.main()
