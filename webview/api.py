"""Read-only query layer for the Snag web viewer (Increment 2 + 3).

Pure functions over db.all_vault(): list with filters/search, item detail,
stats, and tags. No writes, no HTTP. Testable in isolation.

The single-user dogfood vault is small (dozens of rows), so filtering and
substring search run in Python over the full vault rather than FTS5. If the
vault grows into the hundreds, move search onto db.search_vault.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

# Columns the viewer renders. Everything else is stripped so the JSON stays lean.
_PUBLIC = ("id", "summary", "key_ideas", "why_it_worked", "why_it_matters",
           "reusable_pattern", "recommendations",
           "tags", "stage", "action_type", "impact", "effort", "status",
           "source_url", "content_type", "transcript", "ts")


def _split_tags(item):
    return [t.strip() for t in (item.get("tags") or "").split(",") if t.strip()]


def _matches(item, q, stage, tag, impact, status):
    if q:
        hay = " ".join([
            item.get("summary") or "", item.get("key_ideas") or "",
            item.get("why_it_worked") or "", item.get("why_it_matters") or "",
            item.get("reusable_pattern") or "", item.get("recommendations") or "",
            item.get("tags") or "", item.get("transcript") or "",
        ]).lower()
        if q.lower() not in hay:
            return False
    if stage:
        if (item.get("stage") or "").lower() != db.normalize_stage(stage).lower():
            return False
    if tag:
        tags = {t.lower() for t in _split_tags(item)}
        if tag.lower() not in tags:
            return False
    if impact and str(item.get("impact")) != str(impact):
        return False
    if status and (item.get("status") or "").lower() != status.lower():
        return False
    return True


def list_items(q=None, stage=None, tag=None, impact=None, status=None,
               limit=200, offset=0):
    out = []
    for r in db.all_vault():
        if _matches(r, q, stage, tag, impact, status):
            out.append({k: r.get(k) for k in _PUBLIC})
    return out[offset:offset + limit]


def get_item(item_id):
    for r in db.all_vault():
        if r.get("id") == item_id:
            return {k: r.get(k) for k in _PUBLIC}
    return None


def stats():
    by_stage = {}
    by_status = {}
    for r in db.all_vault():
        s = r.get("stage") or "Inbox"
        st = r.get("status") or "inbox"
        by_stage[s] = by_stage.get(s, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
    return {"total": len(db.all_vault()), "by_stage": by_stage, "by_status": by_status}


def all_tags(limit=50):
    counts = {}
    for r in db.all_vault():
        for t in _split_tags(r):
            t = t.lower()
            counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"tag": t, "count": c} for t, c in ranked[:limit]]
