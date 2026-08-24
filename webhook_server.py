#!/usr/bin/env python3
"""Stripe webhook receiver for the Snag Telegram bot. Stdlib only.

Receives signed Stripe webhook POSTs and hands each one to
billing.handle_webhook(payload, sig_header), which verifies the signature and
flips the user's plan in the shared SQLite DB by Telegram ID.

Run from the snag directory so the sibling modules (config/billing/db) import:

    python3 webhook_server.py            # listen on 0.0.0.0:8480
    python3 webhook_server.py --check    # import + .env key-presence check, then exit
    python3 webhook_server.py --help

Stripe posts events to:  https://<PUBLIC_BASE_URL>/webhook
Put this behind a TLS reverse proxy / tunnel (nginx, Caddy, Cloudflare) that
forwards POST /webhook to the port this listens on. No third-party deps.
"""

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Make sibling modules importable no matter where this file is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config   # noqa: E402  (loads .env, declares the Stripe env vars)
import billing  # noqa: E402  (handle_webhook / create_checkout_link)
import db       # noqa: E402  (SQLite store; also imported by billing)

WEBHOOK_PATH = "/webhook"
MAX_BODY_BYTES = 1_000_000  # 1 MB cap; real Stripe events are a few KB


class Handler(BaseHTTPRequestHandler):
    server_version = "SnagWebhook/1.0"

    def _reply(self, code, message):
        body = json.dumps({"status": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/health"):
            return self._reply(200, "ok")
        self._reply(404, "not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != WEBHOOK_PATH:
            return self._reply(404, "not found")

        sig = self.headers.get("Stripe-Signature", "")
        if not sig:
            return self._reply(400, "missing Stripe-Signature header")

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._reply(400, "bad Content-Length")
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._reply(413, "payload too large")

        # Raw body as TEXT: billing verifies the signature over the exact
        # string, and Stripe signs the raw UTF-8 JSON body (lossless round-trip).
        try:
            payload = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            return self._reply(400, "payload not valid utf-8")

        try:
            code, message = billing.handle_webhook(payload, sig)
        except json.JSONDecodeError:
            return self._reply(400, "payload is not valid JSON")
        except Exception as exc:  # db/network errors -> 500 so Stripe retries
            self.log_error("handler raised: %r", exc)
            return self._reply(500, "internal error")

        if code < 200 or code >= 300:
            self.log_error("billing rejected event: %s", message)
        return self._reply(code, message)

    def log_message(self, fmt, *args):
        sys.stderr.write("[webhook] %s - %s\n" % (self.address_string(), fmt % args))


def _check():
    """Import + key-presence check. Prints booleans only, never secret values."""
    keys = ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PRICE_ID", "PUBLIC_BASE_URL")
    missing = [k for k in keys if not getattr(config, k)]
    print("imports ok: config, billing, db")
    if missing:
        print("missing (add to .env): " + ", ".join(missing))
        print("STATUS: NOT READY")
        return 1
    print("all four Stripe keys present in .env")
    print("STATUS: READY")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Snag Stripe webhook receiver (stdlib only). "
                    "Stripe posts to /webhook; see STRIPE_SETUP.md."
    )
    ap.add_argument("--host", default=os.environ.get("WEBHOOK_HOST", "0.0.0.0"),
                    help="bind address (default 0.0.0.0 or $WEBHOOK_HOST)")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("WEBHOOK_PORT", "8480")),
                    help="listen port (default 8480 or $WEBHOOK_PORT)")
    ap.add_argument("--check", action="store_true",
                    help="verify imports + required .env keys, then exit (presence only)")
    args = ap.parse_args()

    if args.check:
        sys.exit(_check())

    db.init()  # ensure tables exist before accepting events
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Snag webhook receiver: http://{args.host}:{args.port}{WEBHOOK_PATH}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
