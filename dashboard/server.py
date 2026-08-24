#!/usr/bin/env python3
"""Local server for the Hermes Snag dashboard.

Serves dashboard/ statically and handles status updates against the Hermes SQLite
vault. Run:

    python3 dashboard/server.py          # http://localhost:8475

No Netlify, no OpenClaw, no external services. Status edits write back to the
same app.db the bot uses, so the dashboard and the Telegram bot share one vault.
"""
import json
import sys
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

ROOT = Path(__file__).resolve().parent
PORT = 8475


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html")
        if path in ("/data.json", "/last_built.json"):
            f = ROOT / path.lstrip("/")
            if f.exists():
                return self._send(200, f.read_bytes(), "application/json")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if path == "/status-update":
            idea_id = body.get("id", "")
            status = body.get("status", "")
            m = re.match(r"live:(\d+)", idea_id)
            if not m:
                return self._send(400, {"error": "bad id"})
            db.set_status(None, int(m.group(1)), status)
            return self._send(200, {"ok": True})

        self._send(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def main():
    db.init()
    print(f"Serving Snag dashboard at http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
