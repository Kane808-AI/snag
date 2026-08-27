#!/usr/bin/env python3
"""Snag web viewer server (Increment 2 + 3 + write-back).

Serves a JSON API over the same SQLite vault the bot writes, plus a write-back
endpoint (PATCH /api/items/<id>) for the UI's Done / stage / impact / effort
controls. stdlib only, bound to localhost, no external services.

CORS is restricted to localhost origins (not ``*``), so a page on the public
web can neither read the vault nor mutate it. Writes additionally require an
explicit localhost Origin header (CSRF defense).

Run:
    python3 webview/server.py          # http://localhost:8476

Endpoints:
    GET  /                 -> the viewer
    GET  /api/items        -> list, ?q= &stage= &tag= &impact= &status=
    GET  /api/items/<id>   -> one item
    GET  /api/stats        -> counts by stage/status
    GET  /api/tags         -> tag list with counts
    PATCH /api/items/<id>  -> write-back {status|stage|impact|effort}
    POST /api/capture      -> analyze a {url} into a note preview (unsaved)
    POST /api/items        -> save a previewed capture into the vault
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

_THIS = Path(__file__).resolve().parent            # webview/
sys.path.insert(0, str(_THIS))                     # for `import api`
sys.path.insert(0, str(_THIS.parent))              # for `import db`

import api  # noqa: E402
import db   # noqa: E402
import service  # noqa: E402

ROOT = _THIS
PORT = 8476

# The viewer is single-user (localhost dogfood). Captures and saves made from
# the web app are attributed to this fixed user id; the Telegram bot uses the
# real Telegram user id instead.
WEB_USER_ID = 1

# DNS-rebinding guard: only these Host names may reach the viewer. The browser
# always sends "Host: localhost:8476" (or 127.0.0.1:8476) for this server, so
# any other Host header — including a rebinding attack that points a remote
# domain at 127.0.0.1 — is refused.
_ALLOWED_HOSTS = ("localhost", "127.0.0.1")


def _host_ok(host_header):
    """Accept only localhost / 127.0.0.1, optionally with the right port."""
    if not host_header:
        return False
    host = host_header.strip().lower()
    if host.startswith("["):  # IPv6 literal — never allowed here
        return False
    name = host
    if ":" in host:
        name, _, port = host.rpartition(":")
        if not port.isdigit() or int(port) != PORT:
            return False
    return name in _ALLOWED_HOSTS


class Handler(BaseHTTPRequestHandler):
    def _origin(self):
        """Return the request Origin only when it is a localhost/loopback origin.

        Cross-site requests from remote origins get no CORS headers at all, so a
        page on the public web can neither read the vault nor (with the PATCH
        origin check) mutate it. Reflecting the allowed origin keeps the
        localhost:8080 frontend working whether it reaches us as localhost or
        127.0.0.1.
        """
        origin = (self.headers.get("Origin") or "").strip()
        if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
            return origin
        return None

    def _send(self, code, data, content_type="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, body):
        self._send(code, json.dumps(body, ensure_ascii=False).encode())

    def do_OPTIONS(self):
        # CORS preflight for the PATCH write endpoint. Only a localhost origin
        # gets the allow headers, so a remote site's preflight fails and the
        # browser never sends the actual write.
        self.send_response(204)
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if not _host_ok(self.headers.get("Host", "")):
            return self._json(403, {"error": "bad host"})

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

    def do_POST(self):
        # Capture (analyze a URL into a note preview) and save (persist a
        # previewed capture). Both are actions, so they require a valid Host
        # and an explicit localhost Origin, matching the PATCH write-back.
        if not _host_ok(self.headers.get("Host", "")):
            return self._json(403, {"error": "bad host"})
        if not self._origin():
            return self._json(403, {"error": "forbidden origin"})

        try:
            length = min(int(self.headers.get("Content-Length") or 0), 1024 * 1024)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "bad json"})
        if not isinstance(body, dict):
            return self._json(400, {"error": "expected object"})

        path = urlparse(self.path).path

        if path == "/api/capture":
            url = (body.get("url") or "").strip()
            if not url:
                return self._json(400, {"error": "url required"})
            try:
                res = service.capture_url(url, WEB_USER_ID)
            except Exception as e:  # unexpected pipeline failure, not a user error
                return self._json(500, {"ok": False, "kind": "error", "error": repr(e)})
            if not res.ok:
                return self._json(422, {
                    "ok": False, "kind": res.kind, "error": res.error,
                    "duration": res.duration,
                })
            # Strip the raw model output before it reaches the frontend; the
            # preview only needs the structured fields.
            note = {k: v for k, v in res.note.items() if k != "raw"}
            return self._json(200, {
                "ok": True,
                "preview": {
                    "note": note,
                    "triage": res.triage,
                    "transcript": res.transcript,
                    "content_type": res.content_type,
                    "url": res.url,
                },
            })

        if path == "/api/items":
            note = body.get("note")
            triage = body.get("triage")
            if not isinstance(note, dict) or not isinstance(triage, dict):
                return self._json(400, {"error": "note and triage must be objects"})
            try:
                item_id = db.save_note(
                    WEB_USER_ID,
                    body.get("url") or "",
                    note,
                    body.get("transcript") or "",
                    triage,
                    body.get("content_type") or "video",
                )
            except Exception as e:
                return self._json(500, {"error": repr(e)})
            return self._json(200, {"ok": True, "id": item_id})

        self._json(404, {"error": "not found"})

    def do_PATCH(self):
        # Write-back endpoint (single-user localhost viewer). State-changing, so
        # it requires both a valid Host and an explicit localhost Origin to block
        # cross-site request forgery from a page on the public web.
        if not _host_ok(self.headers.get("Host", "")):
            return self._json(403, {"error": "bad host"})
        if not self._origin():
            return self._json(403, {"error": "forbidden origin"})

        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/items/"):
            return self._json(404, {"error": "not found"})
        try:
            item_id = int(parsed.path.rsplit("/", 1)[1])
        except ValueError:
            return self._json(404, {"error": "bad id"})

        try:
            length = min(int(self.headers.get("Content-Length") or 0), 1024 * 1024)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "bad json"})
        if not isinstance(body, dict):
            return self._json(400, {"error": "expected object"})

        try:
            updated = db.update_item_fields(item_id, body)
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        if not updated:
            return self._json(404, {"error": "not found"})
        return self._json(200, {"ok": True})

    def log_message(self, *args):
        pass


def main():
    # Ensure the schema exists even if the bot has never run on this machine.
    # Idempotent: CREATE TABLE IF NOT EXISTS — never clobbers an existing vault.
    db.init()
    print(f"Snag web viewer at http://localhost:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
