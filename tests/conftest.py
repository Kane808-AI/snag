"""Shared test setup.

- Puts the engine dir on sys.path so `import config, db, bot` resolve.
- Points DB_PATH and WORK_DIR at a temp location BEFORE config loads, so the
  live data/app.db is never touched. The migration test makes its own copy.
"""
import os
import sys
import tempfile
import pathlib

SN = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SN))

_TMP = tempfile.mkdtemp(prefix="snag-tests-")
os.environ["DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["WORK_DIR"] = os.path.join(_TMP, "work")
os.environ.setdefault("BRAND_NAME", "Snag")

import pytest  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402
import bot  # noqa: E402


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    """A brand-new vault database per test."""
    p = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", str(p))
    db.init()
    return p


@pytest.fixture(autouse=True)
def clean_bot_state():
    bot._PENDING.clear()
    bot._RECENT_CB.clear()
    yield
    bot._PENDING.clear()
    bot._RECENT_CB.clear()


@pytest.fixture
def pump():
    """Run queued jobs synchronously, like the worker thread does in prod.

    The link/file flows are async now: handle_message only acks and enqueues,
    so tests that want the finished card call pump() first.
    """
    def _pump(max_jobs=None):
        return bot.WORKER.pump(max_jobs=max_jobs)
    return _pump


@pytest.fixture
def fake_api(monkeypatch):
    """Recording stub for the Telegram API. Never touches the live service."""

    class Fake:
        def __init__(self):
            self.calls = []  # list of (method, params, result)

        def __call__(self, method, **params):
            result = {"ok": True, "result": {
                "message_id": len(self.calls) + 1001,
                "chat": {"id": params.get("chat_id", 1)},
            }}
            self.calls.append((method, params, result))
            return result

    f = Fake()
    monkeypatch.setattr(bot, "_api", f)
    monkeypatch.setattr(bot, "_post_upload", lambda *a, **k: {"ok": True})
    return f


@pytest.fixture
def no_billing(monkeypatch):
    monkeypatch.setattr(bot.billing, "create_checkout_link", lambda uid: None)


def make_item(uid, summary, stage="Reference", at="Just reference",
              impact=2, effort=3, status="inbox", tags="a,b",
              transcript="some transcript", content_type=None, source_url="https://tiktok.com/x"):
    note = {
        "summary": summary,
        "key_ideas": "key idea one",
        "why_it_matters": "why it matters",
        "recommendations": "rec one",
        "tags": tags.split(","),
    }
    triage = {"stage": stage, "action_type": at, "impact": impact, "effort": effort}
    vid = db.save_note(uid, source_url, note, transcript, triage)
    if content_type:
        with db._conn() as c:
            c.execute("UPDATE vault SET content_type=? WHERE id=?", (content_type, vid))
    if status != "inbox":
        db.set_status(uid, vid, status)
    return vid


def msg(text, chat=1, uid=1):
    return {"chat": {"id": chat}, "from": {"id": uid, "username": "tester"},
            "text": text}


def cb(data, msg_id, chat=1, uid=1, qid="q1"):
    return {"id": qid, "from": {"id": uid},
            "message": {"chat": {"id": chat}, "message_id": msg_id}, "data": data}
