#!/usr/bin/env python3
"""Run native FE8 two-model tournaments and an OBS browser-source dashboard."""

import argparse
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.versus.tournament import (
    SUBMODULE,
    Tournament,
    load_config,
    schedule,
    output_lock,
)
from src.versus.stream import server


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--output", type=Path, default=ROOT / "runtime/versus-tournament")
    p.add_argument("--engine-root", type=Path, default=SUBMODULE / "decomp")
    p.add_argument("--port", type=int, default=8770)
    p.add_argument(
        "--plan",
        action="store_true",
        help="Validate config and print balanced schedule without API calls or ROM",
    )
    p.add_argument("--exit-on-complete", action="store_true")
    args = p.parse_args()
    config = load_config(args.config)
    if args.plan:
        print(json.dumps(schedule(config), indent=2))
        return 0
    with output_lock(args.output):
        t = Tournament(config, args.output, args.engine_root.resolve())
        http = server(t, args.port)
        web = threading.Thread(target=http.serve_forever, daemon=True)
        web.start()
        print(
            json.dumps(
                {
                    "overlay": f"http://127.0.0.1:{http.server_port}/",
                    "output": str(args.output),
                }
            ),
            flush=True,
        )
        try:
            t.run()
            print(
                json.dumps(
                    {"status": t.snapshot()["status"], "completed": len(t.results)}
                ),
                flush=True,
            )
            if not args.exit_on_complete:
                web.join()  # Keep the final standings visible to OBS.
        except KeyboardInterrupt:
            t.stop.set()
        finally:
            http.shutdown()
            http.server_close()
        return 1 if t.snapshot()["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
