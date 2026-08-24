"""Read-only web viewer API tests (Increment 2 + 3).

Imports webview/api.py directly and exercises list/search/filter/item/stats/tags
against a fresh in-memory vault. No HTTP.
"""
import sys
from pathlib import Path

SN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SN))
sys.path.insert(0, str(SN / "webview"))

import api  # noqa: E402
from conftest import make_item  # noqa: E402


def test_list_all_newest_first(fresh_db):
    make_item(1, "first")
    make_item(1, "second")
    assert [i["summary"] for i in api.list_items()] == ["second", "first"]


def test_search_matches_content(fresh_db):
    make_item(1, "CRM automation", transcript="talks about pipelines")
    make_item(1, "something else", transcript="ai marketing")
    assert [i["summary"] for i in api.list_items(q="pipelines")] == ["CRM automation"]
    assert api.list_items(q="zzzznope") == []


def test_stage_filter_and_alias(fresh_db):
    make_item(1, "actionable", stage="Worth Acting On")
    make_item(1, "reference", stage="Reference")
    assert [i["summary"] for i in api.list_items(stage="act")] == ["actionable"]
    assert [i["summary"] for i in api.list_items(stage="Reference")] == ["reference"]


def test_tag_filter(fresh_db):
    make_item(1, "tagged one", tags="github,ai")
    make_item(1, "tagged two", tags="crm")
    assert [i["summary"] for i in api.list_items(tag="github")] == ["tagged one"]


def test_impact_filter(fresh_db):
    make_item(1, "high", impact=5)
    make_item(1, "low", impact=2)
    assert [i["summary"] for i in api.list_items(impact="5")] == ["high"]


def test_get_item(fresh_db):
    vid = make_item(1, "find me", tags="a,b")
    item = api.get_item(vid)
    assert item["summary"] == "find me"
    assert item["tags"] == "a,b"
    assert api.get_item(99999) is None


def test_stats_counts(fresh_db):
    make_item(1, "a", stage="Worth Acting On")
    make_item(1, "b", stage="Reference")
    make_item(1, "c", stage="Reference", status="done")
    s = api.stats()
    assert s["total"] == 3
    assert s["by_stage"] == {"Worth Acting On": 1, "Reference": 2}
    assert s["by_status"] == {"inbox": 2, "done": 1}


def test_all_tags_ranked(fresh_db):
    make_item(1, "a", tags="github")
    make_item(1, "b", tags="github,ai")
    tags = api.all_tags()
    assert tags[0]["tag"] == "github" and tags[0]["count"] == 2
