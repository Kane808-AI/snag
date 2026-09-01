#!/usr/bin/env python3
"""Backfill missing Snag preview URLs without changing any saved content.

Run without --apply to inspect candidates. ``--apply`` only writes an empty
thumbnail field after resolving a public source image URL.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import ingest  # noqa: E402


def preview_for(item):
    url = item.get("source_url") or ""
    return ingest.youtube_thumbnail_url(url) or (
        ingest.video_thumbnail_url(url) if ingest.is_video_url(url) else ""
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill safe source preview URLs")
    parser.add_argument("--apply", action="store_true", help="write discovered previews")
    args = parser.parse_args()
    db.init()

    candidates = [item for item in db.all_vault()
                  if not (item.get("thumbnail_url") or "").strip() and item.get("source_url")]
    updated = 0
    for item in candidates:
        preview = preview_for(item)
        if not preview:
            print(f"skip {item['id']}: no public preview")
            continue
        if args.apply and db.set_thumbnail_url(item["telegram_id"], item["id"], preview):
            updated += 1
        print(f"{'set' if args.apply else 'would set'} {item['id']}: {preview}")
    print(f"{updated if args.apply else 0} previews written; {len(candidates)} saves checked")


if __name__ == "__main__":
    main()
