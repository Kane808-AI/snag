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


def test_is_url_case_insensitive_scheme():
    assert ingest.is_url("HTTP://EXAMPLE.COM/x")
    assert ingest.is_url("Https://example.com/x")
    assert not ingest.is_url("httpfoo")  # no :// -> not a URL
    assert not ingest.is_url("http:/example.com")


def test_first_url_finds_mid_message_url():
    assert ingest.first_url("check this https://x.com out") == "https://x.com"
    assert ingest.first_url("see HTTP://A.com and https://b.com") == "HTTP://A.com"
    assert ingest.first_url("no links here") is None
    assert ingest.first_url("") is None


def test_is_video_url_classifies_domains():
    assert ingest.is_video_url("https://www.tiktok.com/t/ZTD5K5MKb")
    assert ingest.is_video_url("https://vm.tiktok.com/abc")
    assert ingest.is_video_url("https://youtube.com/watch?v=abc")
    assert ingest.is_video_url("https://youtu.be/abc")
    assert not ingest.is_video_url("https://example.com/article")
    assert not ingest.is_video_url("https://x.com/user/status/123")
    assert not ingest.is_video_url("https://instagram.com/p/abc")


def test_is_video_url_rejects_lookalike_hosts():
    # Substring matching used to misroute all of these to the video pipeline.
    assert not ingest.is_video_url("https://notyoutube.com/article")
    assert not ingest.is_video_url("https://youtube.com.evil.com/x")
    assert not ingest.is_video_url("https://www.youtube.com.evil.com/x")
    assert not ingest.is_video_url("https://example.com/blog?ref=tiktok.com")
    assert not ingest.is_video_url("https://example.com/youtube.com")


def test_is_video_url_real_video_host_variants():
    assert ingest.is_video_url("https://www.tiktok.com/t/ZTD5K5MKb")
    assert ingest.is_video_url("https://vm.tiktok.com/abc")
    assert ingest.is_video_url("https://youtube.com/watch?v=abc")
    assert ingest.is_video_url("https://youtu.be/abc")
    assert ingest.is_video_url("http://m.youtube.com/x")
    assert ingest.is_video_url("HTTPS://WWW.YOUTUBE.COM/watch?v=abc")


def test_is_social_blocked_returns_platform_names():
    assert ingest.is_social_blocked("https://facebook.com/post/123") == "Facebook"
    assert ingest.is_social_blocked("https://www.fb.com/x") == "Facebook"
    assert ingest.is_social_blocked("https://instagram.com/p/abc") == "Instagram"
    assert ingest.is_social_blocked("https://x.com/user/status/1") == "X"
    assert ingest.is_social_blocked("https://twitter.com/user/status/1") == "X"
    assert ingest.is_social_blocked("https://linkedin.com/posts/1") == "LinkedIn"


def test_is_social_blocked_rejects_non_social_and_lookalikes():
    # Hostname matching, not substring: lookalikes and query refs must not match.
    assert ingest.is_social_blocked("https://creativeatishay.in/article") is None
    assert ingest.is_social_blocked("https://facebook.com.evil.com/x") is None
    assert ingest.is_social_blocked("https://www.facebook.com.evil.com/x") is None
    assert ingest.is_social_blocked("https://notx.com/1") is None
    assert ingest.is_social_blocked("https://example.com/blog?ref=instagram.com") is None
    assert ingest.is_social_blocked("") is None


def test_is_social_video_instagram_reels_tv():
    assert ingest.is_social_video("https://www.instagram.com/reel/ABC/")
    assert ingest.is_social_video("https://www.instagram.com/reels/ABC/")
    assert ingest.is_social_video("https://www.instagram.com/tv/ABC/")


def test_is_social_video_facebook_watch_and_videos():
    assert ingest.is_social_video("https://www.facebook.com/share/v/123/")
    assert ingest.is_social_video("https://www.facebook.com/watch/?v=123")


def test_is_social_video_rejects_text_posts_homepages_and_non_social():
    assert not ingest.is_social_video("https://www.instagram.com/p/ABC/")
    assert not ingest.is_social_video("https://www.instagram.com/")
    assert not ingest.is_social_video("https://www.facebook.com/groups/x/posts/1")
    assert not ingest.is_social_video("https://example.com/reel/foo")


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


def test_unclosed_title_does_not_swallow_body():
    # No </title>: the body start tag must reset the title state so the body
    # text is still extracted instead of being swallowed into the title.
    html = "<html><head><title>Broken page<body><p>REAL BODY TEXT</p></body></html>"
    text = ingest._html_to_text(html)
    assert "REAL BODY TEXT" in text
    assert "TITLE: Broken page" in text


def test_title_accumulation_is_capped():
    html = "<html><head><title>" + "x" * 2000 + "</title><body><p>BODY KEPT</p></body></html>"
    text = ingest._html_to_text(html)
    title = text.split("TITLE: ")[1].split("\n")[0]
    assert len(title) == ingest._TextExtractor._MAX_TITLE_CHARS
    assert "BODY KEPT" in text


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


def test_fetch_text_requests_gzip(monkeypatch):
    seen = {}

    def capture(req, timeout=30):
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _fake_resp(b"hi", "text/plain")

    monkeypatch.setattr(ingest.urllib.request, "urlopen", capture)
    ok, text, err = ingest.fetch_text("https://example.com/x")
    assert ok
    assert seen["headers"].get("accept-encoding") == "gzip"


def test_fetch_text_rejects_pdf(monkeypatch):
    body = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    monkeypatch.setattr(
        ingest.urllib.request, "urlopen",
        lambda req, timeout=30: _fake_resp(body, "application/pdf"),
    )
    ok, text, err = ingest.fetch_text("https://example.com/a.pdf")
    assert not ok
    assert "isn't supported yet" in err


def test_fetch_text_gunzips_html(monkeypatch):
    import gzip

    html = b"<html><head><title>Zipped</title></head><body><p>gzip content here</p></body></html>"
    monkeypatch.setattr(
        ingest.urllib.request, "urlopen",
        lambda req, timeout=30: _fake_resp(gzip.compress(html), "text/html"),
    )
    ok, text, err = ingest.fetch_text("https://example.com/z")
    assert ok and err == ""
    assert "TITLE: Zipped" in text
    assert "gzip content here" in text


def test_fetch_text_rejects_binary_garbage(monkeypatch):
    body = bytes(range(256)) * 4  # control bytes + invalid-UTF-8 -> high mojibake ratio
    monkeypatch.setattr(
        ingest.urllib.request, "urlopen",
        lambda req, timeout=30: _fake_resp(body, "text/plain"),
    )
    ok, text, err = ingest.fetch_text("https://example.com/bin")
    assert not ok
    assert "couldn't read" in err
