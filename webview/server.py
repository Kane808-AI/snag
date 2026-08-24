#!/usr/bin/env python3
"""Read-only Snag web viewer server (Increment 2 + 3).

Serves webview/index.html and a live JSON API over the same SQLite vault the
bot writes. stdlib only, bound to localhost, no external services.

Run:
    python3 webview/server.py          # http://localhost:8476

Endpoints:
    GET /                -> the viewer
    GET /api/items       -> list, ?q= &stage= &tag= &impact= &status=
    GET /api/items/<id>  -> one item
    GET /api/stats       -> counts by stage/status
    GET /api/tags        -> tag list with counts
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_THIS = Path(__file__).resolve().parent            # webview/
sys.path.insert(0, str(_THIS))                     # for `import api`

import api  # noqa: E402

ROOT = _THIS
PORT = 8476


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, body):
        self._send(code, json.dumps(body, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        one = lambda k: qs.get(k, [None])[0]  # noqa: E731

        if path in ("/", "/index.html"):
            return self._send(200, (ROOT / "index.html").read_bytes(), "text/html")

        if path == "/api/items":
            items = api.list_items(
                q=one("q"), stage=one("stage"), tag=one("tag"),
                impact=one("impact"), status=one("status"),
            )
            return self._json(200, {"items": items})

        if path.startswith("/api/items/"):
            try:
                item_id = int(path.rsplit("/", 1)[1])
            except ValueError:
                return self._json(404, {"error": "bad id"})
            item = api.get_item(item_id)
            if item is None:
                return self._json(404, {"error": "not found"})
            return self._json(200, item)

        if path == "/api/stats":
            return self._json(200, api.stats())

        if path == "/api/tags":
            return self._json(200, {"tags": api.all_tags()})

        self._json(404, {"error": "not found"})

    def log_message(self, *args):
        pass


def main():
    print(f"Snag web viewer at http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
