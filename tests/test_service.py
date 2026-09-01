"""service.py tests: the shared capture pipeline, Telegram-free.

ingest / analyze / social_capture are stubbed so nothing touches the network or
a browser. The point is routing + result shape + plan gates, not real capture.
"""
import pytest

import db
import service


TIKTOK = "https://www.tiktok.com/t/ZTD5K5MKb"
ARTICLE = "https://example.com/some-article"


@pytest.fixture
def stub_pipeline(monkeypatch):
    note = {"summary": "AI tools", "key_ideas": "build in public",
            "why_it_worked": "hook", "why_it_matters": "matters",
            "reusable_pattern": "[task] -> [fix]", "recommendations": "ship",
            "tags": ["ai"], "raw": "raw", "engagement": {}}
    triage = {"stage": "Worth Acting On", "action_type": "Make content",
              "impact": 4, "effort": 2}
    monkeypatch.setattr(service.analyze, "analyze_note", lambda t, engagement=None: dict(note))
    monkeypatch.setattr(service.analyze, "analyze_triage", lambda n: dict(triage))
    return note, triage


def test_capture_text_analyzes(stub_pipeline):
    res = service.capture_text("some text", 1, content_type="text")
    assert res.ok
    assert res.note["summary"] == "AI tools"
    assert res.triage["stage"] == "Worth Acting On"
    assert res.content_type == "text"
    assert res.analysis_state == "complete"


def test_capture_text_empty_is_rejected(stub_pipeline):
    res = service.capture_text("   ", 1)
    assert not res.ok and res.kind == "file_empty"


def test_capture_text_saves_an_honest_reference_when_analysis_fails(stub_pipeline, monkeypatch):
    monkeypatch.setattr(
        service,
        "_analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    res = service.capture_text("some text", 1)
    assert res.ok
    assert res.note["summary"] == "some text"
    assert res.note["why_it_matters"] == "AI analysis is temporarily unavailable. The original content was saved for review."
    assert res.note["tags"] == []
    assert res.triage["stage"] == "Inbox"
    assert res.analysis_state == "awaiting_ai"


def test_capture_url_routes_video(fresh_db, stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: True)
    monkeypatch.setattr(service.ingest, "probe_duration", lambda url: None)
    monkeypatch.setattr(service.ingest, "is_youtube", lambda url: False)
    monkeypatch.setattr(service.ingest, "ingest",
                        lambda url: service.ingest.IngestResult(
                            ok=True, file_path="/tmp/fake.mp4", duration=30, source="yt-dlp"))
    monkeypatch.setattr(service.analyze, "transcribe_local", lambda path: "words")
    res = service.capture_url(TIKTOK, 1)
    assert res.ok and res.content_type == "video"
    assert res.transcript == "words"


def test_capture_url_routes_text(stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(service.ingest, "is_social_video", lambda url: False)
    monkeypatch.setattr(service.ingest, "fetch_text", lambda url: (True, "article body", ""))
    res = service.capture_url(ARTICLE, 1)
    assert res.ok and res.content_type == "article"


def test_capture_article_keeps_preview_url(stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(service.ingest, "is_social_video", lambda url: False)
    monkeypatch.setattr(service.ingest, "fetch_text",
                        lambda url, include_preview=False: (True, "article body", "", "https://example.com/cover.jpg"))
    res = service.capture_url(ARTICLE, 1)
    assert res.ok and res.thumbnail_url == "https://example.com/cover.jpg"


def test_youtube_native_transcript_keeps_thumbnail(fresh_db, stub_pipeline, monkeypatch):
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: True)
    monkeypatch.setattr(service.ingest, "probe_duration", lambda url: None)
    monkeypatch.setattr(service.ingest, "is_youtube", lambda url: True)
    monkeypatch.setattr(service.ingest, "youtube_transcript", lambda url: (True, "words", ""))
    res = service.capture_url(url, 1)
    assert res.ok and res.thumbnail_url.endswith("/dQw4w9WgXcQ/hqdefault.jpg")


def test_social_capture_keeps_preview_url(stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(service.ingest, "is_social_video", lambda url: True)
    monkeypatch.setattr(service.social_capture, "capture", lambda url: service.social_capture.SocialCapture(
        ok=True, title="Post", caption="A useful post", degraded=True,
        thumbnail_url="https://images.instagram.com/cover.jpg"))
    res = service.capture_url("https://www.instagram.com/p/example/", 1)
    assert res.ok and res.thumbnail_url == "https://images.instagram.com/cover.jpg"


def test_capture_url_loginwall(stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: False)
    monkeypatch.setattr(service.ingest, "is_social_video", lambda url: False)
    monkeypatch.setattr(service.ingest, "fetch_text", lambda url: (False, "", "403"))
    monkeypatch.setattr(service.ingest, "is_social_blocked", lambda url: "Facebook")
    res = service.capture_url("https://facebook.com/post/1", 1)
    assert not res.ok and res.kind == "loginwall" and res.error == "Facebook"


def test_capture_url_ingest_failure(fresh_db, stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: True)
    monkeypatch.setattr(service.ingest, "probe_duration", lambda url: None)
    monkeypatch.setattr(service.ingest, "is_youtube", lambda url: False)
    monkeypatch.setattr(service.ingest, "ingest",
                        lambda url: service.ingest.IngestResult(ok=False, error="gone"))
    res = service.capture_url(TIKTOK, 1)
    assert not res.ok and res.kind == "ingest" and "gone" in res.error


def test_duration_gate_rejects_free_user(fresh_db, stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: True)
    monkeypatch.setattr(service.ingest, "probe_duration", lambda url: 9999)
    res = service.capture_url(TIKTOK, 1)
    assert not res.ok and res.kind == "duration" and res.duration == 9999


def test_pro_user_skips_duration_probe(fresh_db, stub_pipeline, monkeypatch):
    db.upsert_user(1, "tester")
    db.set_plan(1, "pro")
    probe_calls = []
    monkeypatch.setattr(service.ingest, "is_video_url", lambda url: True)
    monkeypatch.setattr(service.ingest, "probe_duration",
                        lambda url: probe_calls.append(url) or 9999)
    monkeypatch.setattr(service.ingest, "is_youtube", lambda url: False)
    monkeypatch.setattr(service.ingest, "ingest",
                        lambda url: service.ingest.IngestResult(
                            ok=True, file_path="/tmp/f.mp4", duration=30, source="yt-dlp"))
    monkeypatch.setattr(service.analyze, "transcribe_local", lambda path: "words")
    res = service.capture_url(TIKTOK, 1)
    assert res.ok
    assert probe_calls == []


def test_capture_file_caption_fallback(fresh_db, stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.analyze, "transcribe_local", lambda path: "")
    res = service.capture_file("/tmp/f.mp4", 1, url="uploaded-file", caption="Listing caption")
    assert res.ok and res.content_type == "article"
    assert "Listing caption" in res.transcript


def test_capture_file_empty_no_caption(fresh_db, stub_pipeline, monkeypatch):
    monkeypatch.setattr(service.analyze, "transcribe_local", lambda path: "")
    res = service.capture_file("/tmp/f.mp4", 1, url="uploaded-file")
    assert not res.ok and res.kind == "file_empty"
