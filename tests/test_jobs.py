"""Job queue tests: schema, enqueue/claim/complete lifecycle, stale requeue,
and the bot-level async seam (instant ack + worker pump produces the card).

The Telegram API, analysis, and transcription are stubbed so nothing touches
the live service or the live data/app.db.
"""
import time

import pytest

import config
import db
import bot
from conftest import msg

TIKTOK = "https://www.tiktok.com/t/ZTD5K5MKb"


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Deterministic note + triage + transcription, no network."""
    note = {"summary": "AI tools for marketers", "key_ideas": "build in public",
            "why_it_matters": "matters for Brand75", "recommendations": "ship one tool",
            "tags": ["ai-tools", "marketing"], "raw": "raw"}
    triage = {"stage": "Worth Acting On", "action_type": "Make content",
              "impact": 4, "effort": 2}
    monkeypatch.setattr(bot.analyze, "analyze_note", lambda t: dict(note))
    monkeypatch.setattr(bot.analyze, "analyze_triage", lambda n: dict(triage))
    monkeypatch.setattr(bot.ingest, "ingest",
                        lambda url: bot.ingest.IngestResult(
                            ok=True, file_path="/tmp/fake.mp4", duration=30, source="yt-dlp"))
    monkeypatch.setattr(bot.analyze, "transcribe_local",
                        lambda path: "transcript of the video")
    monkeypatch.setattr(bot.ingest, "probe_duration", lambda url: None)
    return note, triage


# --- schema ------------------------------------------------------------------

def test_init_creates_jobs_table(fresh_db):
    db.init()
    with db._conn() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
    assert {"id", "chat_id", "telegram_id", "source_url", "kind", "file_id",
            "ack_message_id", "status", "worker", "error",
            "created_at", "started_at", "finished_at"} <= cols


def test_jobs_table_created_on_live_db_copy(tmp_path, monkeypatch):
    """init() against a copy of the live app.db must add jobs without touching rows."""
    import shutil
    from conftest import SN
    src = SN / "data" / "app.db"
    if not src.exists():
        pytest.skip("live app.db not present in workspace")
    dest = tmp_path / "app-copy.db"
    shutil.copy(src, dest)
    monkeypatch.setattr(config, "DB_PATH", str(dest))
    before = db.all_vault()
    db.init()
    assert len(db.all_vault()) == len(before), "init must not lose rows"
    with db._conn() as c:
        assert c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        ).fetchone()


# --- enqueue / claim / complete ----------------------------------------------

def test_enqueue_and_status(fresh_db):
    jid = db.enqueue_job(chat_id=1, telegram_id=7, source_url=TIKTOK,
                         kind="link", ack_message_id=42)
    row = db.job_status(jid)
    assert row["status"] == "pending"
    assert row["chat_id"] == 1 and row["telegram_id"] == 7
    assert row["ack_message_id"] == 42 and row["kind"] == "link"
    assert row["source_url"] == TIKTOK
    assert row["created_at"] is not None


def test_claim_fifo_and_marks_processing(fresh_db):
    j1 = db.enqueue_job(1, 7, "https://tiktok.com/1")
    j2 = db.enqueue_job(1, 7, "https://tiktok.com/2")
    got = db.claim_next_job("test-worker")
    assert got["id"] == j1  # oldest first
    assert got["status"] == "processing" and got["worker"] == "test-worker"
    assert got["started_at"] is not None
    # a claimed job is not claimed again
    assert db.claim_next_job("test-worker")["id"] == j2


def test_claim_returns_none_when_empty(fresh_db):
    assert db.claim_next_job("test-worker") is None


def test_complete_and_fail(fresh_db):
    jid = db.enqueue_job(1, 7, "https://tiktok.com/1")
    db.claim_next_job("test-worker")
    db.complete_job(jid)
    row = db.job_status(jid)
    assert row["status"] == "done" and row["finished_at"] is not None
    assert row["error"] is None

    jid2 = db.enqueue_job(1, 7, "https://tiktok.com/2")
    db.claim_next_job("test-worker")
    db.fail_job(jid2, "boom")
    row = db.job_status(jid2)
    assert row["status"] == "failed" and row["error"] == "boom"


def test_file_job_payload(fresh_db):
    jid = db.enqueue_job(1, 7, "uploaded-file", kind="file",
                         file_id="BQAD_FAKE", ack_message_id=9)
    got = db.claim_next_job("test-worker")
    assert got["id"] == jid and got["kind"] == "file" and got["file_id"] == "BQAD_FAKE"


# --- stale requeue -----------------------------------------------------------

def test_requeue_stale_jobs(fresh_db):
    jid = db.enqueue_job(1, 7, "https://tiktok.com/1")
    db.claim_next_job("test-worker")
    with db._conn() as c:
        c.execute("UPDATE jobs SET started_at=? WHERE id=?",
                  (int(time.time()) - 7200, jid))
    assert db.requeue_stale_jobs(max_age_seconds=3600) == 1
    row = db.job_status(jid)
    assert row["status"] == "pending" and row["worker"] is None


def test_requeue_keeps_fresh_processing(fresh_db):
    jid = db.enqueue_job(1, 7, "https://tiktok.com/1")
    db.claim_next_job("test-worker")
    assert db.requeue_stale_jobs(max_age_seconds=3600) == 0
    assert db.job_status(jid)["status"] == "processing"


# --- bot-level async seam ----------------------------------------------------

def test_link_ack_is_instant_and_job_queued(fresh_db, fake_api, stub_pipeline,
                                            no_billing):
    bot.handle_message(msg(TIKTOK))
    # immediate ack, no card yet, job queued for the worker
    assert fake_api.calls[0][0] == "sendMessage"
    assert "working on it" in fake_api.calls[0][1]["text"]
    assert not any(m == "editMessageText" for m, _p, _r in fake_api.calls)
    assert db.pending_job_count() == 1


def test_pump_resolves_ack_into_card(fresh_db, fake_api, stub_pipeline, no_billing, pump):
    bot.handle_message(msg(TIKTOK))
    assert pump() == 1
    card = [p for m, p, _r in fake_api.calls if m == "editMessageText"][-1]
    assert card["message_id"] == 1001  # the ack message
    assert "Worth Acting On" in card["text"] and "Make content" in card["text"]
    assert db.pending_job_count() == 0
    with db._conn() as c:
        row = c.execute("SELECT status FROM jobs WHERE id=1").fetchone()
    assert row["status"] == "done"


def test_file_message_queues_file_job(fresh_db, fake_api, stub_pipeline, no_billing):
    file_msg = {"chat": {"id": 1}, "from": {"id": 1, "username": "tester"},
                "video": {"file_id": "BQAD_FAKE_VIDEO"}}
    bot.handle_message(file_msg)
    assert "working on it" in fake_api.calls[0][1]["text"]
    assert db.pending_job_count() == 1
    with db._conn() as c:
        row = c.execute("SELECT kind, file_id FROM jobs WHERE id=1").fetchone()
    assert row["kind"] == "file" and row["file_id"] == "BQAD_FAKE_VIDEO"


def test_worker_failure_marks_job_failed(fresh_db, fake_api, stub_pipeline,
                                         no_billing, pump, monkeypatch):
    def boom(url):
        raise RuntimeError("transcription exploded")
    monkeypatch.setattr(bot.ingest, "ingest", boom)
    bot.handle_message(msg(TIKTOK))
    pump()
    with db._conn() as c:
        row = c.execute("SELECT status, error FROM jobs WHERE id=1").fetchone()
    assert row["status"] == "failed"
    assert "transcription exploded" in row["error"]
    # the user still hears something
    assert any(m == "editMessageText" for m, _p, _r in fake_api.calls)


def test_worker_thread_processes_job(fresh_db, fake_api, stub_pipeline, no_billing):
    """The real daemon thread picks the job up and finishes it."""
    bot.handle_message(msg(TIKTOK))
    bot.WORKER.start()
    try:
        deadline = time.time() + 5
        while time.time() < deadline and db.pending_job_count() > 0:
            time.sleep(0.05)
        assert db.pending_job_count() == 0
        with db._conn() as c:
            row = c.execute("SELECT status FROM jobs WHERE id=1").fetchone()
        assert row["status"] == "done"
        assert any(m == "editMessageText" for m, _p, _r in fake_api.calls)
    finally:
        bot.WORKER.stop()
