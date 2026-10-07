"""Loopback, read-only OBS browser source for a tournament."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from PIL import Image
from pathlib import Path

ASSETS = Path(__file__).with_name("overlay")


def server(tournament, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ["/video/0.png", "/video/1.png"]:
                directory = tournament.video_directory
                if directory is None:
                    self.send_error(503)
                    return
                try:
                    with Image.open(directory / ("seat-" + path[-5] + ".ppm")) as frame:
                        output = io.BytesIO()
                        frame.save(output, format="PNG")
                    payload = output.getvalue()
                    kind = "image/png"
                except (OSError, ValueError):
                    self.send_error(503)
                    return
            elif path in ["/fonts/title.ttf", "/fonts/body.ttf", "/fonts/mono.ttf"]:
                payload = (ASSETS / path[1:]).read_bytes()
                kind = "font/ttf"
            elif path == "/artwork.png":
                payload = (ASSETS / "artwork.png").read_bytes()
                kind = "image/png"
            elif path == "/state":
                payload = json.dumps(tournament.snapshot()).encode()
                kind = "application/json"
            elif path in ["/", "/overlay.js", "/overlay.css"]:
                name = "index.html" if path == "/" else path[1:]
                payload = (ASSETS / name).read_bytes()
                kind = {
                    "index.html": "text/html",
                    "overlay.js": "text/javascript",
                    "overlay.css": "text/css",
                }[name]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
