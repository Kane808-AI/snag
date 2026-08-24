"""db.py tests: schema, FTS5 search, actions queue, tags, status, lifecycle.

The migration test runs against a COPY of the live data/app.db, never the
original.
"""
import shutil
import sqlite3
import time

import pytest

import config
import db
from conftest import make_item, SN


def _fts_exists():
    with db._conn() as c:
        return c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_fts'"
        ).fetchone() is not None


def _trigger_names():
    with db._conn() as c:
        return {r["name"] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}


# --- schema and migration ----------------------------------------------------

def test_init_creates_fts_and_triggers(fresh_db):
    db.init()
    assert _fts_exists()
    assert {"vault_ai", "vault_ad", "vault_au"} <= _trigger_names()


def test_migration_on_live_db_copy(tmp_path, monkeypatch):
    """Run init() against a copy of the live app.db: FTS index, snooze_until,
    and status normalization must all land without data loss."""
    src = SN / "data" / "app.db"
    if not src.exists():
        pytest.skip("live app.db not present in workspace")
    dest = tmp_path / "app-copy.db"
    shutil.copy(src, dest)
    monkeypatch.setattr(config, "DB_PATH", str(dest))
    before = db.all_vault()
    db.init()
    after = db.all_vault()
    assert _fts_exists()
    assert len(after) == len(before), "migration must not lose rows"
    with db._conn() as c:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(vault)")]
    assert "snooze_until" in cols
    for row in after:
        assert row["status"] in db.STATUS_CYCLE
    # the live row is searchable through FTS
    uid = before[0]["telegram_id"] if before else None
    if uid:
        hits = db.search_vault(uid, "hireable")
        assert hits, "FTS search must find the migrated live row"


# --- save / list / pagination ------------------------------------------------

def test_save_and_list_newest_first(fresh_db):
    uid = 1
    make_item(uid, "first idea")
    make_item(uid, "second idea")
    make_item(uid, "third idea")
    items = db.list_vault(uid)
    assert [i["summary"] for i in items] == ["third idea", "second idea", "first idea"]
    assert set(items[0].keys()) >= {"id", "summary", "stage", "action_type", "impact",
                                    "effort", "status", "tags", "source_url", "ts"}


def test_list_pagination(fresh_db):
    uid = 1
    for i in range(25):
        make_item(uid, f"idea {i}")
    page1 = db.list_vault(uid, limit=20, offset=0)
    page2 = db.list_vault(uid, limit=20, offset=20)
    assert len(page1) == 20
    assert len(page2) == 5
    assert page1[0]["summary"] == "idea 24"
    assert db.count_vault(uid) == 25


def test_list_stage_filter(fresh_db):
    uid = 1
    make_item(uid, "actionable", stage="Worth Acting On")
    make_item(uid, "reference", stage="Reference")
    rows = db.list_vault(uid, stage="act")  # alias
    assert len(rows) == 1 and rows[0]["summary"] == "actionable"
    rows = db.list_vault(uid, stage="Reference")
    assert len(rows) == 1 and rows[0]["summary"] == "reference"
    assert db.count_vault(uid, stage="act") == 1


# --- FTS5 search -------------------------------------------------------------

def test_search_matches_content(fresh_db):
    uid = 1
    make_item(uid, "CRM automation strategies", transcript="talks about pipelines")
    make_item(uid, "something else", transcript="ai marketing tactics")
    assert len(db.search_vault(uid, "automation")) == 1
    assert len(db.search_vault(uid, "pipelines")) == 1
    assert len(db.search_vault(uid, "ai")) == 1
    assert len(db.search_vault(uid, "nonexistent-term-xyz")) == 0


def test_search_filters(fresh_db):
    uid = 1
    make_item(uid, "build an ai tool", stage="Worth Acting On", at="Build a tool",
              impact=4, effort=2, tags="github,ai-tools")
    make_item(uid, "crm notes", stage="Reference", at="Just reference",
              impact=2, effort=3, tags="crm")
    assert len(db.search_vault(uid, "stage:act")) == 1
    assert len(db.search_vault(uid, "stage:reference")) == 1
    assert len(db.search_vault(uid, "tag:ai-tools")) == 1
    assert len(db.search_vault(uid, "tag:crm")) == 1
    # tag filter must match whole tokens, not substrings
    assert len(db.search_vault(uid, "tag:ai")) == 0
    assert len(db.search_vault(uid, "impact:4")) == 1
    # combined
    assert len(db.search_vault(uid, "build stage:act tag:ai-tools impact:4")) == 1
    # filter-only query with no free text
    assert len(db.search_vault(uid, "tag:crm")) == 1


def test_search_pagination(fresh_db):
    uid = 1
    for i in range(5):
        make_item(uid, f"unique term alpha {i}")
    page1 = db.search_vault(uid, "alpha", limit=3, offset=0)
    page2 = db.search_vault(uid, "alpha", limit=3, offset=3)
    assert len(page1) == 3 and len(page2) == 2
    ids = {r["id"] for r in page1 + page2}
    assert len(ids) == 5


def test_search_fallback_to_like_when_fts_missing(fresh_db):
    uid = 1
    make_item(uid, "fallback needle")
    with db._conn() as c:
        c.execute("DROP TABLE vault_fts")
        for t in ("vault_ai", "vault_ad", "vault_au"):
            c.execute(f"DROP TRIGGER IF EXISTS {t}")
    hits = db.search_vault(uid, "fallback")
    assert len(hits) == 1


# --- FTS trigger sync --------------------------------------------------------

def test_fts_syncs_on_insert_update_delete(fresh_db):
    uid = 1
    vid = make_item(uid, "original text", transcript="before")
    assert len(db.search_vault(uid, "original")) == 1
    db.update_note(uid, vid, {"summary": "regenerated text", "key_ideas": "",
                              "why_it_matters": "", "recommendations": "",
                              "tags": ["new-tag"]})
    assert len(db.search_vault(uid, "regenerated")) == 1
    assert len(db.search_vault(uid, "original")) == 0
    db.delete_note(uid, vid)
    assert len(db.search_vault(uid, "regenerated")) == 0


# --- actions queue -----------------------------------------------------------

def test_actions_sorted_by_impact_over_effort(fresh_db):
    uid = 1
    make_item(uid, "low impact", stage="Worth Acting On", impact=2, effort=5)
    make_item(uid, "high impact easy", stage="Worth Acting On", impact=5, effort=1)
    make_item(uid, "high impact hard", stage="Worth Acting On", impact=5, effort=4)
    make_item(uid, "reference only", stage="Reference", impact=5, effort=1)
    make_item(uid, "already done", stage="Worth Acting On", impact=5, effort=1, status="done")
    make_item(uid, "archived", stage="Worth Acting On", impact=5, effort=1, status="archived")
    rows = db.actions(uid)
    assert [r["summary"] for r in rows] == ["high impact easy", "high impact hard", "low impact"]
    assert db.actions_total(uid) == 3


def test_snooze_hides_until_expiry(fresh_db):
    uid = 1
    vid = make_item(uid, "snoozed item", stage="Worth Acting On", impact=4, effort=2)
    assert db.actions(uid)[0]["id"] == vid
    db.snooze(uid, vid, int(time.time()) + 86400)
    assert db.actions(uid) == []
    db.snooze(uid, vid, int(time.time()) - 60)  # expired
    assert [r["id"] for r in db.actions(uid)] == [vid]


def test_later_moves_to_reference(fresh_db):
    uid = 1
    vid = make_item(uid, "later item", stage="Worth Acting On", impact=4, effort=2)
    db.set_stage(uid, vid, "Reference")
    assert db.actions(uid) == []
    assert db.get_vault_item(uid, vid)["stage"] == "Reference"


# --- tags --------------------------------------------------------------------

def test_add_tags_merges_with_auto_tags(fresh_db):
    uid = 1
    vid = make_item(uid, "tagged", tags="auto-one,auto-two")
    db.add_tags(uid, vid, ["user-one", "auto-one", "USER-ONE"])
    tags = db.get_tags(uid, vid)
    assert tags == ["auto-one", "auto-two", "user-one"]  # deduped, no dupes
    db.remove_tags(uid, vid, ["auto-two"])
    assert db.get_tags(uid, vid) == ["auto-one", "user-one"]


def test_all_tags_ranked(fresh_db):
    uid = 1
    make_item(uid, "a", tags="github")
    make_item(uid, "b", tags="github,ai-tools")
    make_item(uid, "c", tags="ai-tools,github,crm")
    ranked = db.all_tags(uid, limit=10)
    assert ranked[0] == ("github", 3)
    assert ranked[1] == ("ai-tools", 2)
    assert ranked[2] == ("crm", 1)


# --- status lifecycle --------------------------------------------------------

def test_status_cycle(fresh_db):
    assert db.next_status("inbox") == "in progress"
    assert db.next_status("in progress") == "done"
    assert db.next_status("done") == "archived"
    assert db.next_status("archived") == "inbox"
    assert db.next_status("weird") == "inbox"


def test_set_status_validates(fresh_db):
    uid = 1
    vid = make_item(uid, "status item")
    db.set_status(uid, vid, "DONE")  # case-insensitive
    assert db.get_vault_item(uid, vid)["status"] == "done"
    with pytest.raises(ValueError):
        db.set_status(uid, vid, "bogus")


def test_save_default_status_is_inbox(fresh_db):
    uid = 1
    vid = make_item(uid, "fresh")
    assert db.get_vault_item(uid, vid)["status"] == "inbox"


def test_quota_and_pro(fresh_db):
    uid = 1
    db.upsert_user(uid, "tester")
    assert db.quota_left(uid) == config.FREE_MONTHLY_LIMIT
    for _ in range(config.FREE_MONTHLY_LIMIT):
        db.record_usage(uid, "https://tiktok.com/x")
    assert db.quota_left(uid) == 0
    db.set_plan(uid, "pro")
    assert db.quota_left(uid) is None
    assert db.is_pro(uid)
