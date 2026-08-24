"""Tests for the any-URL text ingestion path: classification and extraction.

No network: fetch_text's urlopen is stubbed. The extractor is exercised directly
with a sample HTML string.
"""

import ingest


def test_is_url():
    assert ingest.is_url("https://example.com/x")
    assert ingest.is_url("http://example.com/x")
    assert not ingest.is_url("not a url")
    assert not ingest.is_url("")
    assert not ingest.is_url("www.example.com")  # no scheme, not treated as link


def test_is_video_url_classifies_domains():
    assert ingest.is_video_url("https://www.tiktok.com/t/ZTD5K5MKb")
    assert ingest.is_video_url("https://vm.tiktok.com/abc")
    assert ingest.is_video_url("https://youtube.com/watch?v=abc")
    assert ingest.is_video_url("https://youtu.be/abc")
    assert not ingest.is_video_url("https://example.com/article")
    assert not ingest.is_video_url("https://x.com/user/status/123")
    assert not ingest.is_video_url("https://instagram.com/p/abc")


def test_html_to_text_extracts_title_description_and_body():
    html = (
        "<html><head><title>My Page</title>"
        "<meta name='description' content='A great summary'>"
        "<style>.x{color:red}</style>"
        "<script>alert('nope')</script></head>"
        "<body><h1>Hello</h1><p>First paragraph.</p><p>Second paragraph.</p>"
        "<nav>menu items</nav></body></html>"
    )
    text = ingest._html_to_text(html)
    assert "TITLE: My Page" in text
    assert "DESCRIPTION: A great summary" in text
    assert "Hello" in text
    assert "First paragraph." in text
    assert "Second paragraph." in text
    # script and style content must be stripped
    assert "alert" not in text
    assert "color:red" not in text


def _fake_resp(body, ctype="text/html; charset=utf-8"):
    class FakeResp:
        headers = {"Content-Type": ctype}

        def read(self, n=None):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return FakeResp()


def test_fetch_text_plain(monkeypatch):
    monkeypatch.setattr(
        ingest.urllib.request, "urlopen",
        lambda req, timeout=30: _fake_resp(b"just some plain text", "text/plain"),
    )
    ok, text, err = ingest.fetch_text("https://example.com/x.txt")
    assert ok and err == ""
    assert "plain text" in text


def test_fetch_text_html(monkeypatch):
    body = b"<html><head><title>Readable</title></head><body><p>article body</p></body></html>"
    monkeypatch.setattr(
        ingest.urllib.request, "urlopen",
        lambda req, timeout=30: _fake_resp(body),
    )
    ok, text, err = ingest.fetch_text("https://example.com/a")
    assert ok
    assert "TITLE: Readable" in text
    assert "article body" in text


def test_fetch_text_error(monkeypatch):
    def boom(req, timeout=30):
        raise OSError("connection refused")

    monkeypatch.setattr(ingest.urllib.request, "urlopen", boom)
    ok, text, err = ingest.fetch_text("https://example.com/x")
    assert not ok and text == ""
    assert "connection refused" in err
