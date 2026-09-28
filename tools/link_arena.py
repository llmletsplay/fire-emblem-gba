#!/usr/bin/env python3
"""Start a local, two-agent FE7 Link Arena match and its side-scoped API."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.link_arena.coordinator import InvalidAction, LinkArenaCoordinator, StaleObservation
from src.link_arena.bridge import BridgeError
from src.link_arena.autoplay import MinimaxAutoplay
from src.link_arena.stream import LinkArenaStreamState


DEFAULT_ROM = ROOT / "roms" / "fe7.gba"
DEFAULT_SAVE = ROOT / "roms" / "fe7-link-arena-maxed.sav"


def _twitch_channel(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,25}", value):
        raise argparse.ArgumentTypeError("Twitch channel must be a channel handle (letters, digits, underscore)")
    return value.lower()


def _default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "FE7-Link-Arena"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "fe7-link-arena"


DEFAULT_DATA_DIR = _default_data_dir()
DEFAULT_MGBA_CANDIDATES = (
    Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "mGBA" / "mGBA.exe",
    Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "mGBA" / "mGBA.exe",
    Path("/Applications/mGBA.app/Contents/MacOS/mGBA"),
)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _available_port(port: int) -> bool:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_mgba(requested: str | None) -> str:
    if requested:
        return requested
    env_path = os.environ.get("MGBA_PATH")
    if env_path:
        return env_path
    portable = ROOT / "mgba-portable" / "mGBA.exe"
    if portable.is_file():
        # Keep the isolated runner on the tested portable build. On Windows,
        # the installed Qt build can close the Lua bridge during FE7's serial
        # team handshake; fall back to the system install only when the runner
        # does not carry its portable emulator.
        return str(portable)
    for candidate in DEFAULT_MGBA_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    for name in ("mgba-qt", "mgba", "mGBA"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("mGBA was not found; pass --mgba or set MGBA_PATH")


def _new_match(args: argparse.Namespace) -> tuple[Path, dict[str, Any], dict[str, str]]:
    rom = Path(args.rom).expanduser().resolve()
    save = Path(args.save).expanduser().resolve()
    source_script = ROOT / "lua" / "socketserver.lua"
    if not rom.is_file():
        raise FileNotFoundError(f"FE7 ROM not found: {rom}")
    if not save.is_file():
        raise FileNotFoundError(
            f"converted FE7 battery save not found: {save}\n"
            "Import roms/fe7-link-arena-maxed.xps into an isolated FE7 copy in mGBA, "
            "save the prepared RAGNAROK roster to an isolated .sav, then pass that "
            "copy with --save. The runner handles title and Link Arena setup."
        )
    if not source_script.is_file():
        raise FileNotFoundError(f"mGBA Lua bridge not found: {source_script}")
    if not 1024 <= args.base_port <= 65532:
        raise ValueError("--base-port must be between 1024 and 65532")
    if not 1 <= args.api_port <= 65535:
        raise ValueError("--api-port must be between 1 and 65535")
    ports = (args.base_port, args.base_port + 1, args.api_port)
    if len(set(ports)) != len(ports):
        raise ValueError("the API port must differ from both bridge ports")
    busy_ports = [port for port in ports if not _available_port(port)]
    if busy_ports:
        raise OSError(f"port(s) already in use: {', '.join(map(str, busy_ports))}")

    match_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    match_dir = Path(args.data_dir).expanduser().resolve() / match_id
    (match_dir / "side-a").mkdir(parents=True)
    (match_dir / "side-b").mkdir()
    for side_dir in (match_dir / "side-a", match_dir / "side-b"):
        shutil.copy2(rom, side_dir / "FE7.gba")
        shutil.copy2(save, side_dir / "FE7.sav")

    bridge_source = source_script.read_text(encoding="utf-8")
    bridge_text, substitutions = re.subn(
        r"(local LISTEN_PORT\s*=\s*)\d+",
        rf"\g<1>{args.base_port}",
        bridge_source,
        count=1,
    )
    if substitutions != 1:
        raise RuntimeError("could not set the side bridge's starting port")
    bridge_text, bind_substitutions = re.subn(
        r"socket\.bind\(nil,\s*port\)",
        'socket.bind("127.0.0.1", port)',
        bridge_text,
        count=1,
    )
    if bind_substitutions != 1:
        raise RuntimeError("could not restrict the side bridge to loopback")

    trace_path = match_dir / "mgba-lua-trace.log"
    trace_prelude = "\n".join((
        f"local LINK_ARENA_TRACE_FILE = {json.dumps(str(trace_path))}",
        "local function link_arena_trace(message)",
        "    if not io or not io.open then return end",
        "    pcall(function()",
        "        local trace = io.open(LINK_ARENA_TRACE_FILE, 'a')",
        "        if trace then",
        "            trace:write(tostring(os and os.time and os.time() or 0), '|', tostring(message), '\\n')",
        "            trace:close()",
        "        end",
        "    end)",
        "end",
        "link_arena_trace('script_start')",
        "",
    ))
    bridge_text = trace_prelude + bridge_text

    claim_side_a = json.dumps(str(match_dir / "side-a.bridge-claim"))
    claim_side_b = json.dumps(str(match_dir / "side-b.bridge-claim"))
    allocation_block = "\n".join((
        f"local BRIDGE_CLAIM_A = {claim_side_a}",
        f"local BRIDGE_CLAIM_B = {claim_side_b}",
        "local function try_claim(path)",
        "    local command = 'mkdir \"' .. path .. '\"'",
        "    if path:match('^%a:[/\\\\]') then",
        "        command = command .. ' >NUL 2>&1'",
        "    else",
        "        command = command .. ' >/dev/null 2>&1'",
        "    end",
        "    local ok, reason, code = os.execute(command)",
        "    return ok == true or ok == 0 or code == 0, tostring(reason) .. ':' .. tostring(code)",
        "end",
        "local function claim_bridge_side()",
        "    local ok, claimed, result = pcall(try_claim, BRIDGE_CLAIM_A)",
        "    link_arena_trace('claim_a|ok=' .. tostring(ok) .. '|claimed=' .. tostring(claimed) .. '|result=' .. tostring(result))",
        "    if ok and claimed then",
        "        return 'A', LISTEN_PORT",
        "    end",
        "    if not ok then",
        "        error('cannot claim side A bridge identity: ' .. tostring(claimed))",
        "    end",
        "    ok, claimed, result = pcall(try_claim, BRIDGE_CLAIM_B)",
        "    link_arena_trace('claim_b|ok=' .. tostring(ok) .. '|claimed=' .. tostring(claimed) .. '|result=' .. tostring(result))",
        "    if ok and claimed then",
        "        return 'B', LISTEN_PORT + 1",
        "    end",
        "    if ok and not claimed then",
        "        error('both Link Arena bridge identities are already claimed')",
        "    end",
        "    error('cannot claim side B bridge identity: ' .. tostring(claimed))",
        "end",
        "local BRIDGE_SIDE, BRIDGE_PORT = claim_bridge_side()",
        "LISTEN_PORT = BRIDGE_PORT",
        "link_arena_trace('bridge_side=' .. BRIDGE_SIDE .. '|port=' .. tostring(BRIDGE_PORT))",
        "",
    ))
    constants_anchor = "local QUEUE_SPACING = 24"
    if bridge_text.count(constants_anchor) != 1:
        raise RuntimeError("could not add atomic side-specific bridge allocation")
    bridge_text = bridge_text.replace(constants_anchor, allocation_block + constants_anchor, 1)

    bind_line = '      server, bind_err = socket.bind("127.0.0.1", port)\n'
    if bridge_text.count(bind_line) != 1:
        raise RuntimeError("could not instrument the side bridge bind call")
    bridge_text = bridge_text.replace(
        bind_line,
        '      link_arena_trace("bind_attempt|port=" .. tostring(port))\n'
        + bind_line
        + '      link_arena_trace("bind_result|port=" .. tostring(port) .. "|server=" .. tostring(server) .. "|error=" .. tostring(bind_err))\n',
        1,
    )
    listen_retry_block = (
        "      if not server then\n"
        "         if bind_err == socket.ERRORS.ADDRESS_IN_USE then\n"
        "            console:log(\"[INFO ] listen: Port \" .. port .. \" in use, trying next...\")\n"
        "            port = port + 1\n"
        "         else\n"
        "            err(\"bind\", \"Failed to bind to any port: \" .. tostring(bind_err))\n"
        "            return\n"
        "         end\n"
        "      else\n"
    )
    if bridge_text.count(listen_retry_block) != 1:
        raise RuntimeError("could not make assigned bridge ports fail closed")
    bridge_text = bridge_text.replace(
        listen_retry_block,
        "      if not server then\n"
        "         err(\"bind\", \"Failed to bind on assigned port \" .. port .. \": \" .. tostring(bind_err))\n"
        "         return\n"
        "      else\n",
        1,
    )
    listen_line = "listen(LISTEN_PORT)\n"
    if bridge_text.count(listen_line) != 1:
        raise RuntimeError("could not instrument the side bridge startup")
    bridge_text = bridge_text.replace(
        listen_line,
        listen_line + 'link_arena_trace("listener_init_returned")\n',
        1,
    )

    input_function = """local function applyHeldKeys()
   local m = heldMask()
   if m ~= 0 then
      emu:setKeys(m)
   end
end"""
    traced_input_function = """local linkArenaLastInputTrace = "none"
local function applyHeldKeys(source)
   local m = heldMask()
   if m ~= 0 then
      emu:setKeys(m)
      linkArenaLastInputTrace = tostring(source or "frame")
         .. "|frame=" .. tostring(emu:currentFrame())
         .. "|mask=" .. tostring(m)
         .. "|active=" .. tostring(emu:getKeys())
      link_arena_trace("held_keys|side=" .. tostring(BRIDGE_SIDE) .. "|" .. linkArenaLastInputTrace)
   end
end"""
    if bridge_text.count(input_function) != 1:
        raise RuntimeError("could not instrument the Link Arena key state")
    bridge_text = bridge_text.replace(input_function, traced_input_function, 1)
    callback_anchor = 'callbacks:add("keysRead", applyHeldKeys)'
    if bridge_text.count(callback_anchor) != 1:
        raise RuntimeError("could not instrument the Link Arena key-read callback")
    bridge_text = bridge_text.replace(
        callback_anchor,
        'callbacks:add("keysRead", function() applyHeldKeys("keysRead") end)',
        1,
    )
    state_command_anchor = '   if line_upper == "STATE" then\n'
    keytrace_command = (
        '   if line_upper == "KEYTRACE" then\n'
        '      sock:send("KEYTRACE|side=" .. tostring(BRIDGE_SIDE) .. "|" .. linkArenaLastInputTrace .. "\\n")\n'
        '      return\n'
        '   end\n\n'
    )
    if bridge_text.count(state_command_anchor) != 1:
        raise RuntimeError("could not expose the Link Arena key trace")
    bridge_text = bridge_text.replace(state_command_anchor, keytrace_command + state_command_anchor, 1)
    bridge_path = match_dir / "link_arena_socketserver.lua"
    bridge_path.write_text(bridge_text, encoding="utf-8")

    tokens = {"A": secrets.token_urlsafe(32), "B": secrets.token_urlsafe(32)}
    for side, token in tokens.items():
        token_path = match_dir / f"side-{side.lower()}.token"
        token_path.write_text(token + "\n", encoding="utf-8")
        if os.name != "nt":
            token_path.chmod(0o600)

    session = {
        "schema_version": 1,
        "match_id": match_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rom_sha256": _sha256(rom),
        "seed_save_sha256": _sha256(save),
        "mgba_lua_trace": "mgba-lua-trace.log",
        "bridge_ports": {"A": args.base_port, "B": args.base_port + 1},
        "api": {"host": "127.0.0.1", "port": args.api_port},
        "agent_tokens": {side: f"side-{side.lower()}.token" for side in ("A", "B")},
    }
    (match_dir / "session.json").write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    return match_dir, session, tokens


class _ApiServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], coordinator: LinkArenaCoordinator):
        self.coordinator = coordinator
        self.autoplay: MinimaxAutoplay | None = None
        self.stream_state: LinkArenaStreamState | None = None
        super().__init__(address, _ApiHandler)


class _ApiHandler(http.server.BaseHTTPRequestHandler):
    server: _ApiServer

    def log_message(self, fmt: str, *args: object) -> None:
        print("[link-arena-api] " + fmt % args)

    def _json(self, status: int, value: dict[str, Any]) -> None:
        data = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _static_file(self, path: str) -> None:
        filename = {"/stream": "index.html", "/stream.css": "overlay.css", "/stream.js": "overlay.js"}.get(path)
        if filename is None:
            self._json(404, {"error": "unknown stream asset"})
            return
        source = ROOT / "src" / "link_arena" / "stream_overlay" / filename
        try:
            data = source.read_bytes()
        except OSError:
            self._json(503, {"error": "stream overlay assets are missing from this deployment"})
            return
        content_type = "text/html; charset=utf-8" if filename.endswith(".html") else (
            "text/css; charset=utf-8" if filename.endswith(".css") else "text/javascript; charset=utf-8"
        )
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src https://www.twitch.tv https://*.twitch.tv; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _authorized_side(self) -> str | None:
        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        return self.server.coordinator.side_for_token(token)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/stream", "/stream.css", "/stream.js"}:
            self._static_file(path)
            return
        if path in {"/v1/stream", "/v1/stream/frames"}:
            if self.server.stream_state is None:
                self._json(503, {"error": "stream telemetry is not available"})
                return
            try:
                if path == "/v1/stream/frames":
                    self._json(200, self.server.stream_state.frames())
                    return
                query = parse_qs(urlsplit(self.path).query)
                include_frame = query.get("frame", ["1"])[0] != "0"
                self._json(200, self.server.stream_state.snapshot(include_frame=include_frame))
            except (BridgeError, OSError, ValueError) as exc:
                self._json(503, {"error": str(exc)})
            return
        side = self._authorized_side()
        if side is None:
            self._json(401, {"error": "use this agent side's bearer token"})
            return
        try:
            if self.path == "/v1/observe":
                autoplay = self.server.autoplay
                if autoplay is not None and autoplay.status.get("state") not in {"ready", "playing", "complete"}:
                    self._json(503, {"error": "Link Arena setup is not ready for agent observations",
                                     "autoplay": autoplay.status})
                    return
                self._json(200, self.server.coordinator.observe(side))
            elif self.path == "/v1/status":
                autoplay = self.server.autoplay
                if autoplay is not None and autoplay.status.get("state") not in {"ready", "playing", "complete"}:
                    self._json(200, {"side": side, "autoplay": autoplay.status})
                    return
                status = self.server.coordinator.status()
                response = {"generation": status["generation"], "side": side,
                            **status["sides"][side]}
                if autoplay is not None:
                    response["autoplay"] = autoplay.status
                self._json(200, response)
            else:
                self._json(404, {"error": "unknown endpoint"})
        except (BridgeError, OSError) as exc:
            self._json(502, {"error": str(exc)})

    def do_POST(self) -> None:
        side = self._authorized_side()
        if side is None:
            self._json(401, {"error": "use this agent side's bearer token"})
            return
        if self.path != "/v1/action":
            self._json(404, {"error": "unknown endpoint"})
            return
        try:
            autoplay = self.server.autoplay
            if autoplay is not None and autoplay.status.get("state") not in {"ready", "playing", "complete"}:
                self._json(503, {"error": "Link Arena setup is not ready for agent actions",
                                 "autoplay": autoplay.status})
                return
            if autoplay is not None and autoplay.play_minimax:
                self._json(409, {"error": "the built-in minimax runner currently owns both sides"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise InvalidAction("request body must be between 1 and 8192 bytes")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise InvalidAction("action body must be a JSON object")
            result = self.server.coordinator.act(side, payload)
            self._json(200, result)
        except StaleObservation as exc:
            self._json(409, {"error": str(exc)})
        except (InvalidAction, json.JSONDecodeError, ValueError) as exc:
            self._json(400, {"error": str(exc)})
        except (BridgeError, OSError) as exc:
            self._json(502, {"error": str(exc)})


def start(args: argparse.Namespace) -> int:
    if args.auto_minimax and args.manual_setup:
        raise ValueError("--auto-minimax requires the default automatic title and Link Arena setup")
    mgba = _find_mgba(args.mgba)
    match_dir, session, tokens = _new_match(args)
    side_a = match_dir / "side-a" / "FE7.gba"
    side_b = match_dir / "side-b" / "FE7.gba"
    bridge_path = match_dir / "link_arena_socketserver.lua"
    command = [mgba]
    if args.mgba_log_level is not None:
        command.extend(("--log-level", str(args.mgba_log_level)))
    command.extend(("--script", str(bridge_path), str(side_a), str(side_b)))
    print(f"Match: {session['match_id']}\nData: {match_dir}\nStarting mGBA's linked two-ROM session...")
    process_env = os.environ.copy()
    if os.name == "nt":
        mgba_profile = match_dir / "mgba-profile"
        mgba_profile.mkdir()
        process_env["APPDATA"] = str(mgba_profile)
    mgba_log_path = match_dir / "mgba.log"
    with mgba_log_path.open("wb") as mgba_log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=process_env,
            stdout=mgba_log,
            stderr=subprocess.STDOUT,
        )

    from src.link_arena.bridge import SideBridge

    bridges = {side: SideBridge(session["bridge_ports"][side]) for side in ("A", "B")}
    coordinator: LinkArenaCoordinator | None = None
    try:
        for side, bridge in bridges.items():
            bridge.wait_until_ready(timeout=args.startup_timeout)
            print(f"Side {side} bridge ready on 127.0.0.1:{bridge.port}")
        coordinator = LinkArenaCoordinator(
            session["bridge_ports"], tokens, match_dir, bridges=bridges
        )
        server = _ApiServer(("127.0.0.1", args.api_port), coordinator)
        autoplay = None
        if not args.manual_setup:
            autoplay = MinimaxAutoplay(
                coordinator,
                match_dir,
                play_minimax=args.auto_minimax,
                poll_interval=args.auto_poll_interval,
                settle_timeout=args.auto_settle_timeout,
            )
            server.autoplay = autoplay
            autoplay.start()
            if args.auto_minimax:
                print("Automatic title/setup and minimax armed; the runner will take both clients to the arena map and play.")
            else:
                print("Automatic title/setup armed; agent observations and actions unlock when both clients reach the arena map.")
        else:
            print("Manual setup enabled; the agent API will expose the current screen.")
        server.stream_state = LinkArenaStreamState(
            coordinator,
            match_id=session["match_id"],
            started_at=session["created_at"],
            autoplay=autoplay,
        )
        print(f"Agent API: http://127.0.0.1:{args.api_port}/v1/observe")
        overlay_url = f"http://127.0.0.1:{args.api_port}/stream"
        if args.twitch_channel:
            overlay_url += "?" + urlencode({"channel": args.twitch_channel})
        print(f"OBS Link Arena overlay: {overlay_url}")
        print(f"Side A token file: {match_dir / 'side-a.token'}")
        print(f"Side B token file: {match_dir / 'side-b.token'}")
        print("Press Ctrl-C here to stop the API and close this mGBA session.")
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
            if autoplay is not None:
                autoplay.stop()
    except KeyboardInterrupt:
        pass
    finally:
        if coordinator is not None:
            coordinator.close()
        else:
            for bridge in bridges.values():
                bridge.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    print("Link Arena session stopped.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", default=str(DEFAULT_ROM), help="local FE7 ROM; default: roms/fe7.gba")
    parser.add_argument("--save", default=str(DEFAULT_SAVE), help="converted raw .sav seed file")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="local match data directory")
    parser.add_argument("--mgba", help="mGBA executable; defaults to MGBA_PATH or the installed app")
    parser.add_argument("--mgba-log-level", type=int, help="optional mGBA log bitmask forwarded to its CLI")
    parser.add_argument("--base-port", type=int, default=18888, help="first side bridge port (next port is side B)")
    parser.add_argument("--api-port", type=int, default=18700, help="loopback agent API port")
    parser.add_argument("--startup-timeout", type=float, default=20.0)
    parser.add_argument("--auto-minimax", action="store_true",
                        help="automate title/link setup and play both sides with minimax")
    parser.add_argument("--manual-setup", action="store_true",
                        help="leave title and Link Arena menus under operator control")
    parser.add_argument("--auto-poll-interval", type=float, default=0.5,
                        help="seconds between stable-screen checks while minimax autoplay waits")
    parser.add_argument("--auto-settle-timeout", type=float, default=60.0,
                        help="seconds allowed for each one-button transition and FE7 combat animation to settle")
    parser.add_argument("--twitch-channel", type=_twitch_channel,
                        help="Twitch channel handle shown in the stream overlay")
    parser.set_defaults(func=start)
    return parser


if __name__ == "__main__":
    try:
        arguments = build_parser().parse_args()
        raise SystemExit(arguments.func(arguments))
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
        print(f"link-arena: {exc}", file=sys.stderr)
        raise SystemExit(2)
