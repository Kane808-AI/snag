"""
Stripe subscription via Checkout, keyed to the Telegram user ID.

Flow:
  create_checkout_link(telegram_id) -> hosted Checkout URL (subscription mode)
  ...user pays...
  Stripe fires checkout.session.completed / customer.subscription.* webhooks
  handle_webhook() flips the user's plan in our DB by telegram_id (client_reference_id)

Net ~95% of revenue vs ~55-70% on Telegram Stars (Apple tax + Fragment spread),
plus automatic renewals + dunning. Stdlib only (Stripe REST via urllib).
"""
import hmac
import hashlib
import json
import time
import urllib.parse
import urllib.request

import config
import db

_API = "https://api.stripe.com/v1"


def _stripe_post(path, fields):
    data = urllib.parse.urlencode(fields, doseq=True).encode()
    req = urllib.request.Request(
        f"{_API}/{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {config.STRIPE_SECRET_KEY}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def create_checkout_link(telegram_id):
    if not (config.STRIPE_SECRET_KEY and config.STRIPE_PRICE_ID):
        return None
    base = config.PUBLIC_BASE_URL.rstrip("/")
    fields = {
        "mode": "subscription",
        "line_items[0][price]": config.STRIPE_PRICE_ID,
        "line_items[0][quantity]": 1,
        "client_reference_id": str(telegram_id),
        "success_url": f"{base}/upgrade/success",
        "cancel_url": f"{base}/upgrade/cancel",
        "allow_promotion_codes": "true",
    }
    session = _stripe_post("checkout/sessions", fields)
    return session.get("url")


def _verify_signature(payload, sig_header):
    """Stripe signed-payload check (no stripe lib needed)."""
    if not config.STRIPE_WEBHOOK_SECRET:
        return False
    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    timestamp = parts.get("t", "")
    signed = f"{timestamp}.{payload}".encode()
    expected = hmac.new(config.STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    given = parts.get("v1", "")
    # tolerate 5 min clock skew
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
        return False
    return hmac.compare_digest(expected, given)


def handle_webhook(payload, sig_header):
    """Returns (status_code, message). Wire this to a tiny HTTP route."""
    if not _verify_signature(payload, sig_header):
        return 400, "bad signature"
    event = json.loads(payload)
    etype = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        tid = obj.get("client_reference_id")
        customer = obj.get("customer")
        if tid:
            db.set_plan(int(tid), "pro", stripe_customer_id=customer)
            return 200, f"user {tid} -> pro"

    elif etype in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer = obj.get("customer")
        if customer:
            db.set_plan_by_customer(customer, "free")
            return 200, f"customer {customer} -> free"

    return 200, "ignored"
