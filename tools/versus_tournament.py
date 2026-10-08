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
    p.add_argument("--headless", action="store_true", help="Run without the native emulator window (agent matches)")
    p.add_argument("--terminal-human", action="store_true", help="Use the legacy terminal action selector")
    p.add_argument("--overlay", action="store_true", help="Enable optional loopback OBS information overlay")
    p.add_argument("--browser-video", action="store_true", help="Enable legacy screenshot browser video (implies --overlay)")
    args = p.parse_args()
    config = load_config(args.config)
    if args.plan:
        print(json.dumps(schedule(config), indent=2))
        return 0
    if args.headless and not args.terminal_human and any(e['provider'] == 'human' for e in config['entrants']):
        p.error("Human play needs the native window; omit --headless or add --terminal-human")
    with output_lock(args.output):
        t = Tournament(config, args.output, args.engine_root.resolve(), desktop=not args.headless,
                       terminal_human=args.terminal_human, browser_video=args.browser_video)
        http = server(t, args.port) if args.overlay or args.browser_video else None
        web = threading.Thread(target=http.serve_forever, daemon=True) if http else None
        if web:
            web.start()
        print(
            json.dumps(
                {
                    "overlay": (f"http://127.0.0.1:{http.server_port}/" + ("" if args.browser_video else "?overlay=1")) if http else None,
                    "native_window": not args.headless,
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
            if not args.exit_on_complete and t.snapshot()["status"] != "error":
                # Keep the native results window and optional overlay alive until Ctrl-C.
                while not t.stop.wait(0.25):
                    if t.live_session is None and not http:
                        break
                    if t.live_session is not None and t.live_session.p.poll() is not None:
                        break
        except KeyboardInterrupt:
            t.stop.set()
        finally:
            t.close()
            if http:
                http.shutdown()
                http.server_close()
        return 1 if t.snapshot()["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
