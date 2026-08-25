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
import server  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
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


# --- Fix 1: CORS / DNS-rebinding hardening ----------------------------------

def test_host_guard_accepts_localhost_only():
    assert server._host_ok("localhost:8476")
    assert server._host_ok("127.0.0.1:8476")
    assert server._host_ok("localhost")  # no port given (curl-style)
    assert not server._host_ok("evil.com:8476")
    assert not server._host_ok("localhost:9999")
    assert not server._host_ok("localhost:8476.evil.com")
    assert not server._host_ok("")
    assert not server._host_ok("[::1]:8476")


def _start_viewer(tmp_path, monkeypatch):
    """Boot the real HTTP server on an ephemeral port against a fresh vault."""
    p = tmp_path / "viewer.db"
    monkeypatch.setattr(config, "DB_PATH", str(p))
    db.init()
    srv = server.HTTPServer(("127.0.0.1", 0), server.Handler)
    monkeypatch.setattr(server, "PORT", srv.server_address[1])
    import threading
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_no_wildcard_cors_and_nosniff(monkeypatch, tmp_path):
    import http.client
    import json

    srv = _start_viewer(tmp_path, monkeypatch)
    try:
        port = srv.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/stats", headers={"Host": f"localhost:{port}"})
        resp = conn.getresponse()
        body = resp.read()
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()

        assert resp.status == 200
        # CORS is dropped entirely (same-origin viewer): no wildcard, no pinning
        assert "access-control-allow-origin" not in hdrs
        assert hdrs.get("x-content-type-options") == "nosniff"
        assert json.loads(body)["total"] == 0
    finally:
        srv.shutdown()
        srv.server_close()


def test_viewer_rejects_foreign_host_header(monkeypatch, tmp_path):
    import http.client

    srv = _start_viewer(tmp_path, monkeypatch)
    try:
        port = srv.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        # A DNS-rebinding attacker points a remote domain at 127.0.0.1; the
        # Host header is the only thing left to trust.
        conn.request("GET", "/", headers={"Host": f"evil.example.com:{port}"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 403
    finally:
        srv.shutdown()
        srv.server_close()


# --- Fix 3: viewer works on a fresh machine (db.init before serve) ----------

def test_viewer_api_works_on_brand_new_db_path(tmp_path, monkeypatch):
    """api.list_items must work against a never-initialized DB after init."""
    p = tmp_path / "brand_new.db"
    monkeypatch.setattr(config, "DB_PATH", str(p))
    db.init()
    assert api.list_items() == []
    assert api.stats()["total"] == 0
    assert api.all_tags() == []


def test_main_inits_db_before_serving(tmp_path, monkeypatch):
    p = tmp_path / "fresh_machine.db"
    monkeypatch.setattr(config, "DB_PATH", str(p))

    class FakeServer:
        def __init__(self, addr, handler):
            self.addr = addr
            self.handler = handler

        def serve_forever(self):
            pass

    monkeypatch.setattr(server, "HTTPServer", FakeServer)
    server.main()
    # After main() (which calls db.init()), the schema exists and queries work.
    assert api.list_items() == []
    assert api.stats()["total"] == 0


def test_db_init_is_idempotent_and_does_not_clobber_vault(tmp_path, monkeypatch):
    p = tmp_path / "vault.db"
    monkeypatch.setattr(config, "DB_PATH", str(p))
    db.init()
    vid = make_item(1, "precious")
    db.init()  # second init on an existing vault must not drop anything
    assert [r["id"] for r in db.all_vault()] == [vid]
    assert api.list_items()[0]["summary"] == "precious"


# --- write-back (PATCH) ------------------------------------------------------

def test_patch_requires_localhost_origin(monkeypatch, tmp_path):
    import http.client
    import json

    srv = _start_viewer(tmp_path, monkeypatch)
    try:
        port = srv.server_address[1]
        # no Origin header -> 403 (CSRF defense)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("PATCH", "/api/items/1", body=json.dumps({"status": "done"}),
                     headers={"Host": f"localhost:{port}",
                              "Content-Type": "application/json"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 403
        # remote origin -> 403 too
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("PATCH", "/api/items/1", body=json.dumps({"status": "done"}),
                     headers={"Host": f"localhost:{port}",
                              "Content-Type": "application/json",
                              "Origin": "https://evil.example.com"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.status == 403
    finally:
        srv.shutdown()
        srv.server_close()


def test_patch_updates_status_with_localhost_origin(monkeypatch, tmp_path):
    import http.client
    import json

    srv = _start_viewer(tmp_path, monkeypatch)
    try:
        port = srv.server_address[1]
        vid = make_item(1, "do me", stage="Worth Acting On")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        body = json.dumps({"status": "done", "impact": 5})
        conn.request("PATCH", f"/api/items/{vid}", body=body,
                     headers={"Host": f"localhost:{port}",
                              "Content-Type": "application/json",
                              "Origin": "http://localhost:8080"})
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        assert resp.status == 200 and payload.get("ok") is True
        row = db.get_vault_item(1, vid)
        assert row["status"] == "done"
        assert row["impact"] == 5
    finally:
        srv.shutdown()
        srv.server_close()
