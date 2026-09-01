"""SQLite store: users, monthly usage metering, and the saved-ideas vault. Stdlib only.

The vault now stores the full enriched note + triage, so a save is a complete
organized idea, not just a summary. Search runs on SQLite FTS5 (external-content
table kept in sync by triggers) with stage/tag/impact/type filters layered on
top as SQL predicates.
"""
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import config

# Status lifecycle: inbox -> in progress -> done -> archived (cycles back to inbox)
STATUS_CYCLE = ["inbox", "in progress", "done", "archived"]

# Short aliases users can type for stage filters (/vault act, /search stage:act)
_STAGE_ALIASES = {
    "act": "Worth Acting On",
    "acting": "Worth Acting On",
    "worth": "Worth Acting On",
    "worth acting on": "Worth Acting On",
    "ref": "Reference",
    "reference": "Reference",
    "in": "Inbox",
    "inbox": "Inbox",
}


def _conn():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _vault_cols(c):
    return [r["name"] for r in c.execute("PRAGMA table_info(vault)").fetchall()]


def init():
    with _conn() as c:
        # Migration: the pre-enrichment vault had a different shape. It is safe to
        # drop because the table only ever held user saves (no source of truth).
        cols = _vault_cols(c)
        if cols and "key_ideas" not in cols:
            c.execute("DROP TABLE IF EXISTS vault_fts")
            c.execute("DROP TABLE vault")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id        INTEGER PRIMARY KEY,
                username           TEXT,
                plan               TEXT NOT NULL DEFAULT 'free',
                stripe_customer_id TEXT,
                created_at         INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS usage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                ym          TEXT NOT NULL,
                source_url  TEXT,
                ts          INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_usage_user_ym ON usage(telegram_id, ym);
            CREATE TABLE IF NOT EXISTS vault (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                source_url      TEXT,
                thumbnail_url   TEXT,
                summary         TEXT,
                key_ideas       TEXT,
                why_it_worked   TEXT,
                why_it_matters  TEXT,
                reusable_pattern TEXT,
                engagement      TEXT,
                recommendations TEXT,
                tags            TEXT,
                transcript      TEXT,
                content_type    TEXT,
                stage           TEXT DEFAULT 'Inbox',
                action_type     TEXT DEFAULT 'Just reference',
                impact          INTEGER DEFAULT 3,
                effort          INTEGER DEFAULT 3,
                status          TEXT DEFAULT 'inbox',
                snooze_until    INTEGER,
                ts              INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_vault_user ON vault(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_vault_user_ts ON vault(telegram_id, ts);
            CREATE INDEX IF NOT EXISTS idx_vault_user_stage ON vault(telegram_id, stage);
            CREATE TABLE IF NOT EXISTS jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id         INTEGER NOT NULL,
                telegram_id     INTEGER NOT NULL,
                source_url      TEXT,
                kind            TEXT NOT NULL DEFAULT 'link',
                file_id         TEXT,
                ack_message_id  INTEGER,
                status          TEXT NOT NULL DEFAULT 'pending',
                worker          TEXT,
                error           TEXT,
                created_at      INTEGER NOT NULL,
                started_at      INTEGER,
                finished_at     INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);
            """
        )
        # FTS5 search index, kept in sync by triggers (all vault writes go through
        # this module, so the index can never drift from the table).
        fts_exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vault_fts'"
        ).fetchone()
        if not fts_exists:
            c.execute(
                "CREATE VIRTUAL TABLE vault_fts USING fts5("
                "summary, key_ideas, why_it_matters, recommendations, tags, transcript, "
                "content='vault', content_rowid='id')"
            )
            c.executescript(
                """
                CREATE TRIGGER vault_ai AFTER INSERT ON vault BEGIN
                  INSERT INTO vault_fts(rowid, summary, key_ideas, why_it_matters,
                                        recommendations, tags, transcript)
                  VALUES (new.id, new.summary, new.key_ideas, new.why_it_matters,
                          new.recommendations, new.tags, new.transcript);
                END;
                CREATE TRIGGER vault_ad AFTER DELETE ON vault BEGIN
                  INSERT INTO vault_fts(vault_fts, rowid, summary, key_ideas,
                                        why_it_matters, recommendations, tags, transcript)
                  VALUES('delete', old.id, old.summary, old.key_ideas,
                         old.why_it_matters, old.recommendations, old.tags, old.transcript);
                END;
                CREATE TRIGGER vault_au AFTER UPDATE ON vault BEGIN
                  INSERT INTO vault_fts(vault_fts, rowid, summary, key_ideas,
                                        why_it_matters, recommendations, tags, transcript)
                  VALUES('delete', old.id, old.summary, old.key_ideas,
                         old.why_it_matters, old.recommendations, old.tags, old.transcript);
                  INSERT INTO vault_fts(rowid, summary, key_ideas, why_it_matters,
                                        recommendations, tags, transcript)
                  VALUES (new.id, new.summary, new.key_ideas, new.why_it_matters,
                          new.recommendations, new.tags, new.transcript);
                END;
                """
            )
            c.execute("INSERT INTO vault_fts(vault_fts) VALUES('rebuild')")
        # Schema evolution: snooze_until supports the F6 Snooze action.
        cols = _vault_cols(c)
        if "snooze_until" not in cols:
            c.execute("ALTER TABLE vault ADD COLUMN snooze_until INTEGER")
        # Schema evolution: content-aware note fields (why it worked + reusable
        # pattern), the "understand the content" half of the note.
        cols = _vault_cols(c)
        if "why_it_worked" not in cols:
            c.execute("ALTER TABLE vault ADD COLUMN why_it_worked TEXT")
        if "reusable_pattern" not in cols:
            c.execute("ALTER TABLE vault ADD COLUMN reusable_pattern TEXT")
        if "engagement" not in cols:
            c.execute("ALTER TABLE vault ADD COLUMN engagement TEXT")
        if "thumbnail_url" not in cols:
            c.execute("ALTER TABLE vault ADD COLUMN thumbnail_url TEXT")
        # Status normalization: the pre-increment default was 'New'.
        c.execute("UPDATE vault SET status='inbox' WHERE status='New'")
        c.execute("UPDATE vault SET status=lower(status) WHERE status IN "
                  "('Inbox','In Progress','Done','Archived')")


def _ym():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def upsert_user(telegram_id, username):
    with _conn() as c:
        c.execute(
            "INSERT INTO users (telegram_id, username, created_at) VALUES (?,?,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username",
            (telegram_id, username, int(time.time())),
        )


def get_user(telegram_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()
        return dict(row) if row else None


def is_pro(telegram_id):
    user = get_user(telegram_id)
    return bool(user and user["plan"] == "pro")


def set_plan(telegram_id, plan, stripe_customer_id=None):
    with _conn() as c:
        if stripe_customer_id:
            c.execute(
                "UPDATE users SET plan=?, stripe_customer_id=? WHERE telegram_id=?",
                (plan, stripe_customer_id, telegram_id),
            )
        else:
            c.execute("UPDATE users SET plan=? WHERE telegram_id=?", (plan, telegram_id))


def set_plan_by_customer(stripe_customer_id, plan):
    with _conn() as c:
        c.execute("UPDATE users SET plan=? WHERE stripe_customer_id=?", (plan, stripe_customer_id))


def month_usage(telegram_id):
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM usage WHERE telegram_id=? AND ym=?",
            (telegram_id, _ym()),
        ).fetchone()
        return row["n"]


def record_usage(telegram_id, source_url):
    with _conn() as c:
        c.execute(
            "INSERT INTO usage (telegram_id, ym, source_url, ts) VALUES (?,?,?,?)",
            (telegram_id, _ym(), source_url, int(time.time())),
        )


def quota_left(telegram_id):
    """Returns remaining videos this month, or None if unlimited (pro)."""
    if is_pro(telegram_id):
        return None
    return max(0, config.FREE_MONTHLY_LIMIT - month_usage(telegram_id))


def canonical_source_url(source_url):
    """Compare sources without fragments or common marketing-link noise."""
    value = (source_url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    query = [
        (key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit((
        parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/",
        urlencode(query, doseq=True), "",
    ))


def existing_note_for_source(telegram_id, source_url, include_all_users=False):
    """Return the newest saved item for this logical source URL, if any.

    The local mobile Library currently renders the shared dogfood vault, so its
    duplicate check can opt into that same visible scope. Telegram keeps the
    normal per-user scope.
    """
    canonical = canonical_source_url(source_url)
    if not canonical:
        return None
    with _conn() as c:
        if include_all_users:
            rows = c.execute(
                "SELECT id, source_url FROM vault WHERE status != 'archived' ORDER BY id DESC"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, source_url FROM vault WHERE telegram_id=? AND status != 'archived' ORDER BY id DESC",
                (telegram_id,),
            ).fetchall()
    for row in rows:
        if canonical_source_url(row["source_url"]) == canonical:
            return row["id"]
    return None


def save_note(telegram_id, source_url, note, transcript, triage, content_type="video", thumbnail_url=""):
    """Store the full enriched note + triage. Returns the new row id."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO vault (telegram_id, source_url, thumbnail_url, summary, key_ideas, "
            "why_it_worked, why_it_matters, reusable_pattern, recommendations, "
            "tags, transcript, content_type, engagement, "
            "stage, action_type, impact, effort, status, ts) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                telegram_id,
                source_url,
                thumbnail_url,
                note.get("summary", ""),
                note.get("key_ideas", ""),
                note.get("why_it_worked", ""),
                note.get("why_it_matters", ""),
                note.get("reusable_pattern", ""),
                note.get("recommendations", ""),
                ",".join(note.get("tags", [])),
                transcript,
                content_type,
                json.dumps(note.get("engagement") or {}),
                triage.get("stage", "Inbox"),
                triage.get("action_type", "Just reference"),
                triage.get("impact", 3),
                triage.get("effort", 3),
                "inbox",
                int(time.time()),
            ),
        )
        return cur.lastrowid


_ROW_COLS = ("id, summary, stage, action_type, impact, effort, status, tags, "
             "source_url, ts")


def list_vault(telegram_id, limit=20, offset=0, stage=None):
    """Recent vault rows, newest first. Optional stage filter and pagination."""
    sql = f"SELECT {_ROW_COLS} FROM vault WHERE telegram_id=?"
    params = [telegram_id]
    if stage:
        sql += " AND stage=?"
        params.append(normalize_stage(stage))
    sql += " ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def count_vault(telegram_id, stage=None):
    sql = "SELECT COUNT(*) AS n FROM vault WHERE telegram_id=?"
    params = [telegram_id]
    if stage:
        sql += " AND stage=?"
        params.append(normalize_stage(stage))
    with _conn() as c:
        row = c.execute(sql, params).fetchone()
        return row["n"]


def normalize_stage(stage):
    """Map user shorthand (act, ref, inbox) to the canonical triage stage."""
    s = (stage or "").strip().lower()
    if s in _STAGE_ALIASES:
        return _STAGE_ALIASES[s]
    return stage


def _parse_search_filters(query):
    """Split a /search query into free-text terms and stage/tag/impact/type filters."""
    filters = {"stage": None, "tag": None, "impact": None, "type": None}
    terms = []
    for token in (query or "").split():
        lowered = token.lower()
        matched = False
        for key in filters:
            if lowered.startswith(f"{key}:"):
                filters[key] = token.split(":", 1)[1]
                matched = True
                break
        if not matched:
            terms.append(token)
    return terms, filters


def search_vault(telegram_id, query, limit=20, offset=0):
    """FTS5 full-text search with stage:/tag:/impact:/type: filters.

    Free-text terms run through the FTS5 index. Filters are applied as SQL
    predicates so stage and impact match exactly and tags match whole tokens.
    """
    terms, filters = _parse_search_filters(query)
    params = [telegram_id]

    # Free-text terms: join through the FTS index. No terms: plain table scan,
    # filters only (avoids FTS match-all syntax, which is not portable).
    if terms:
        match_q = " AND ".join(f'"{t.replace(chr(34), "")}"' for t in terms if t.replace(chr(34), ""))
        if not match_q:
            return []
        cols = ", ".join("v." + col for col in _ROW_COLS.split(", "))
        sql = (
            f"SELECT {cols} FROM vault v "
            "JOIN vault_fts f ON f.rowid = v.id "
            "WHERE v.telegram_id=? AND vault_fts MATCH ?"
        )
        params.append(match_q)
        order = " ORDER BY v.ts DESC, v.id DESC"
        p = "v."
    else:
        sql = f"SELECT {_ROW_COLS} FROM vault WHERE telegram_id=?"
        order = " ORDER BY ts DESC, id DESC"
        p = ""

    stage = filters.get("stage")
    if stage:
        sql += f" AND {p}stage=?"
        params.append(normalize_stage(stage))
    tag = filters.get("tag")
    if tag:
        sql += f" AND (',' || {p}tags || ',') LIKE ?"
        params.append(f"%,{tag.lower()},%")
    impact = filters.get("impact")
    if impact and impact.isdigit():
        sql += f" AND {p}impact=?"
        params.append(int(impact))
    ctype = filters.get("type")
    if ctype:
        sql += f" AND {p}content_type=?"
        params.append(ctype)

    sql += order + " LIMIT ? OFFSET ?"
    params += [limit, offset]
    try:
        with _conn() as c:
            rows = c.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        # FTS index unavailable (should not happen after init): fall back to LIKE.
        like = f"%{query}%"
        with _conn() as c:
            rows = c.execute(
                "SELECT id, summary, stage, action_type, impact, effort, status, tags, "
                "source_url, ts FROM vault WHERE telegram_id=? AND "
                "(summary LIKE ? OR key_ideas LIKE ? OR why_it_matters LIKE ? "
                "OR recommendations LIKE ? OR tags LIKE ?) "
                "ORDER BY ts DESC LIMIT ?",
                (telegram_id, like, like, like, like, like, limit),
            ).fetchall()
            return [dict(r) for r in rows]


def get_vault_item(telegram_id, item_id):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM vault WHERE telegram_id=? AND id=?", (telegram_id, item_id)
        ).fetchone()
        return dict(row) if row else None


def set_thumbnail_url(telegram_id, item_id, thumbnail_url):
    """Persist a vetted source preview URL without touching note content."""
    value = (thumbnail_url or "").strip()
    if not value.startswith(("https://", "http://")):
        raise ValueError("thumbnail_url must be an http(s) URL")
    with _conn() as c:
        cur = c.execute(
            "UPDATE vault SET thumbnail_url=? WHERE telegram_id=? AND id=? "
            "AND (thumbnail_url IS NULL OR thumbnail_url='')",
            (value, telegram_id, item_id),
        )
        return cur.rowcount > 0


def next_status(status):
    s = (status or "inbox").lower().strip()
    if s not in STATUS_CYCLE:
        return "inbox"
    return STATUS_CYCLE[(STATUS_CYCLE.index(s) + 1) % len(STATUS_CYCLE)]


def set_status(telegram_id, item_id, status):
    s = (status or "").lower().strip()
    if s not in STATUS_CYCLE:
        raise ValueError(f"invalid status: {status}")
    with _conn() as c:
        c.execute(
            "UPDATE vault SET status=? WHERE telegram_id=? AND id=?",
            (s, telegram_id, item_id),
        )


def set_stage(telegram_id, item_id, stage):
    with _conn() as c:
        c.execute(
            "UPDATE vault SET stage=? WHERE telegram_id=? AND id=?",
            (normalize_stage(stage), telegram_id, item_id),
        )


def snooze(telegram_id, item_id, until_ts):
    with _conn() as c:
        c.execute(
            "UPDATE vault SET snooze_until=? WHERE telegram_id=? AND id=?",
            (int(until_ts), telegram_id, item_id),
        )


def update_item_fields(item_id, fields):
    """Web write-back: update whitelisted triage fields by vault id.

    The localhost web viewer is single-user and writes by id (no telegram_id).
    Status, stage, impact, effort, snooze time, and explicit tag additions/removals are
    writable. The summary and transcript remain AI-owned. Tag operations merge
    with the existing AI tags rather than replacing them. Returns True when a row
    was updated, False when the id didn't exist.
    """
    setters = {}
    if "status" in fields:
        s = (fields.get("status") or "").lower().strip()
        if s not in STATUS_CYCLE:
            raise ValueError(f"invalid status: {fields.get('status')}")
        setters["status"] = s
    if "stage" in fields:
        setters["stage"] = normalize_stage(fields.get("stage"))
    for key, lo, hi in (("impact", 1, 5), ("effort", 1, 5)):
        if key in fields:
            try:
                v = int(fields.get(key))
            except (TypeError, ValueError):
                raise ValueError(f"invalid {key}: {fields.get(key)}")
            if not (lo <= v <= hi):
                raise ValueError(f"{key} out of range {lo}-{hi}")
            setters[key] = v
    if "snooze_until" in fields:
        value = fields.get("snooze_until")
        if value is None:
            setters["snooze_until"] = None
        else:
            try:
                setters["snooze_until"] = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"invalid snooze_until: {value}")
    tag_ops = {}
    for key in ("add_tags", "remove_tags"):
        if key not in fields:
            continue
        values = fields.get(key)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError(f"{key} must be a list of strings")
        tag_ops[key] = [value.strip().lower() for value in values if value.strip()]
    if not setters and not tag_ops:
        return False
    with _conn() as c:
        row = c.execute("SELECT tags FROM vault WHERE id=?", (item_id,)).fetchone()
        if not row:
            return False
        if tag_ops:
            tags = _split_tags(row["tags"])
            existing = {tag.lower() for tag in tags}
            for tag in tag_ops.get("add_tags", []):
                if tag not in existing and len(tags) < 12:
                    tags.append(tag)
                    existing.add(tag)
            remove = set(tag_ops.get("remove_tags", []))
            setters["tags"] = ",".join(tag for tag in tags if tag.lower() not in remove)
        assignments = ", ".join(f"{k}=?" for k in setters)
        params = list(setters.values()) + [item_id]
        cur = c.execute(f"UPDATE vault SET {assignments} WHERE id=?", params)
        return cur.rowcount > 0


def update_note(telegram_id, item_id, note):
    """Overwrite the AI note fields (regenerate path). Transcript and triage stay."""
    with _conn() as c:
        c.execute(
            "UPDATE vault SET summary=?, key_ideas=?, why_it_worked=?, "
            "why_it_matters=?, reusable_pattern=?, recommendations=?, tags=? "
            "WHERE telegram_id=? AND id=?",
            (
                note.get("summary", ""),
                note.get("key_ideas", ""),
                note.get("why_it_worked", ""),
                note.get("why_it_matters", ""),
                note.get("reusable_pattern", ""),
                note.get("recommendations", ""),
                ",".join(note.get("tags", [])),
                telegram_id,
                item_id,
            ),
        )


def delete_note(telegram_id, item_id):
    with _conn() as c:
        c.execute("DELETE FROM vault WHERE telegram_id=? AND id=?", (telegram_id, item_id))


def _split_tags(tags):
    return [t.strip() for t in (tags or "").split(",") if t.strip()]


def get_tags(telegram_id, item_id):
    item = get_vault_item(telegram_id, item_id)
    return _split_tags(item["tags"]) if item else []


def add_tags(telegram_id, item_id, new_tags):
    """Merge user tags with the DeepSeek auto-tags. Case-insensitive, capped at 12."""
    item = get_vault_item(telegram_id, item_id)
    if not item:
        return None
    existing = _split_tags(item["tags"])
    existing_lower = {t.lower() for t in existing}
    for t in new_tags:
        t = t.strip().lower()
        if t and t not in existing_lower and len(existing) < 12:
            existing.append(t)
            existing_lower.add(t)
    with _conn() as c:
        c.execute("UPDATE vault SET tags=? WHERE telegram_id=? AND id=?",
                  (",".join(existing), telegram_id, item_id))
    return existing


def remove_tags(telegram_id, item_id, tags_to_remove):
    item = get_vault_item(telegram_id, item_id)
    if not item:
        return None
    remove = {t.lower() for t in tags_to_remove}
    kept = [t for t in _split_tags(item["tags"]) if t.lower() not in remove]
    with _conn() as c:
        c.execute("UPDATE vault SET tags=? WHERE telegram_id=? AND id=?",
                  (",".join(kept), telegram_id, item_id))
    return kept


def all_tags(telegram_id, limit=10):
    """Most-used tags across the user's vault, for autocomplete. Returns [(tag, count)]."""
    with _conn() as c:
        rows = c.execute("SELECT tags FROM vault WHERE telegram_id=?", (telegram_id,)).fetchall()
    counts = {}
    for r in rows:
        for t in _split_tags(r["tags"]):
            counts[t.lower()] = counts.get(t.lower(), 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]


def actions(telegram_id, limit=15):
    """The Actions queue: Worth Acting On, not done or archived, not snoozed.
    Sorted by impact over effort (impact desc, effort asc)."""
    now = int(time.time())
    with _conn() as c:
        rows = c.execute(
            "SELECT id, summary, stage, action_type, impact, effort, status FROM vault "
            "WHERE telegram_id=? AND stage='Worth Acting On' "
            "AND status NOT IN ('done','archived') "
            "AND (snooze_until IS NULL OR snooze_until < ?) "
            "ORDER BY impact DESC, effort ASC, ts DESC LIMIT ?",
            (telegram_id, now, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def actions_total(telegram_id):
    now = int(time.time())
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM vault "
            "WHERE telegram_id=? AND stage='Worth Acting On' "
            "AND status NOT IN ('done','archived') "
            "AND (snooze_until IS NULL OR snooze_until < ?)",
            (telegram_id, now),
        ).fetchone()
        return row["n"]


# --- background job queue ----------------------------------------------------
# The bot's async seam: handle_message enqueues, the in-process worker claims.
# Every write here goes through this module, so the jobs table can never drift
# from the schema created in init().

JOB_STATUSES = ("pending", "processing", "done", "failed")


def enqueue_job(chat_id, telegram_id, source_url, kind="link", file_id=None,
                ack_message_id=None):
    """Queue a processing job. Returns the new job id."""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO jobs (chat_id, telegram_id, source_url, kind, file_id, "
            "ack_message_id, status, created_at) VALUES (?,?,?,?,?,?,'pending',?)",
            (chat_id, telegram_id, source_url, kind, file_id, ack_message_id,
             int(time.time())),
        )
        return cur.lastrowid


def claim_next_job(worker):
    """Atomically claim the oldest pending job. Returns the row dict, or None.

    A single UPDATE with RETURNING claims and reads in one statement, so two
    workers can never grab the same job.
    """
    now = int(time.time())
    with _conn() as c:
        row = c.execute(
            "UPDATE jobs SET status='processing', worker=?, started_at=? "
            "WHERE id = (SELECT id FROM jobs WHERE status='pending' "
            "            ORDER BY id LIMIT 1) "
            "RETURNING id, chat_id, telegram_id, source_url, kind, file_id, "
            "ack_message_id, status, worker, created_at, started_at",
            (worker, now),
        ).fetchone()
        return dict(row) if row else None


def complete_job(job_id, error=None):
    """Mark a job finished. error set marks it failed, otherwise done."""
    status = "failed" if error else "done"
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status=?, error=?, finished_at=? WHERE id=?",
            (status, error, int(time.time()), job_id),
        )


def fail_job(job_id, error):
    complete_job(job_id, error=error)


def requeue_stale_jobs(max_age_seconds=3600):
    """Reset jobs stuck in 'processing' back to pending.

    Covers a worker crash or bot restart mid-job. Returns the number reset.
    """
    cutoff = int(time.time()) - max_age_seconds
    with _conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status='pending', worker=NULL, started_at=NULL "
            "WHERE status='processing' AND started_at < ?",
            (cutoff,),
        )
        return cur.rowcount


def job_status(job_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def pending_job_count():
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status='pending'"
        ).fetchone()
        return row["n"]


def all_vault():
    """Full vault, for the dashboard build. Returns every row, newest first."""
    with _conn() as c:
        rows = c.execute("SELECT * FROM vault ORDER BY ts DESC, id DESC").fetchall()
        return [dict(r) for r in rows]
