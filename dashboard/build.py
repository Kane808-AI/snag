#!/usr/bin/env python3
"""Build data.json + last_built.json for the Hermes Snag dashboard.

Reads the Hermes Snag SQLite vault (the same store the bot writes on save) and
emits the same shape the OpenClaw dashboard's index.html expects, so the UI is
drop-in compatible. No OpenClaw paths, no Netlify.

Reads:  ~/.hermes/workspace/snag/data/app.db (vault table)
Writes: ~/.hermes/workspace/snag/dashboard/data.json + last_built.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
DATA_PATH = OUT_DIR / "data.json"
BUILT_PATH = OUT_DIR / "last_built.json"

THEME_MAP = [
    ("ai building", ["openclaw", "agent", "claude code", "claude-code", "automation",
                     "anthropic", "skill", "mcp", "codex"]),
    ("coding", ["coding", "developer", "front-end", "frontend", "engineer", "ui design"]),
    ("business", ["business", "money", "monetiz", "affiliate", "strategy", "outreach",
                  "amazon", "ecommerce", "crm", "sales"]),
    ("marketing", ["marketing", "tiktok", "pinterest", "social", "seo", "content",
                   "instagram", "youtube"]),
]


def derive_theme(tags, title):
    haystack = " ".join([tags or "", title or ""]).lower()
    for theme, keywords in THEME_MAP:
        if any(k in haystack for k in keywords):
            return theme
    return "other"


def slug_from_summary(summary):
    words = (summary or "").lower().split()
    s = "-".join(w.strip(".,;:!?") for w in words if w.strip(".,;:!?"))[:60]
    return s or "idea"


def main() -> int:
    db.init()
    rows = db.all_vault()

    ideas = []
    for r in rows:
        tags_list = [t for t in (r.get("tags") or "").split(",") if t.strip()]
        summary = r.get("summary") or ""
        date = datetime.fromtimestamp(r.get("ts", 0), tz=timezone.utc).strftime("%Y-%m-%d")
        ideas.append({
            "id": f"live:{r['id']}",
            "slug": slug_from_summary(summary),
            "date": date,
            "title": (summary or "(no summary)")[:120],
            "tags": tags_list,
            "summary": summary,
            "theme": derive_theme(r.get("tags"), summary),
            "source_url": r.get("source_url") or "",
            "source_folder": "live",
            "key_ideas": r.get("key_ideas") or "",
            "why_it_matters": r.get("why_it_matters") or "",
            "recommendations": r.get("recommendations") or "",
            "transcript": r.get("transcript") or "",
            "status": r.get("status") or "New",
            "stage": r.get("stage") or "Inbox",
            "action_type": r.get("action_type") or "Just reference",
            "impact": r.get("impact", 3),
            "effort": r.get("effort", 3),
        })

    ideas.sort(key=lambda i: (i["date"], i["id"]), reverse=True)

    DATA_PATH.write_text(json.dumps({"ideas": ideas, "schema_version": 1}, indent=2, ensure_ascii=False))
    BUILT_PATH.write_text(json.dumps({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "idea_count": len(ideas),
        "live_count": len(ideas),
        "archive_count": 0,
        "errors": [],
    }, indent=2))

    print(f"[build] {len(ideas)} ideas -> data.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
