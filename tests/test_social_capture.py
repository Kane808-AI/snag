"""Tests for social_capture (Instagram/Facebook browser capture)."""
import pytest

import config
import social_capture


# --- platform_of -------------------------------------------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/reel/ABC123/", "instagram"),
    ("https://instagram.com/tv/XYZ/", "instagram"),
    ("https://www.facebook.com/watch/?v=123", "facebook"),
    ("https://facebook.com/videos/999", "facebook"),
    ("https://fb.com/share/v/abc/", "facebook"),
    ("https://fb.watch/xyz/", "facebook"),
    ("https://sub.fb.watch/xyz/", "facebook"),
    ("https://www.tiktok.com/@x/video/1", ""),
    ("https://www.youtube.com/watch?v=x", ""),
    ("https://example.com/", ""),
    ("https://instagram.com.evil.com/reel/x/", ""),
    ("https://notfacebook.com/watch?v=1", ""),
])
def test_platform_of(url, expected):
    assert social_capture.platform_of(url) == expected


# --- guard paths (no browser needed) ----------------------------------------

def test_capture_non_social():
    cap = social_capture.capture("https://example.com/article")
    assert not cap.ok
    assert "Instagram or Facebook" in cap.error


def test_capture_no_playwright(monkeypatch):
    monkeypatch.setattr(social_capture, "sync_playwright", None)
    cap = social_capture.capture("https://www.instagram.com/reel/x/")
    assert not cap.ok
    assert "playwright" in cap.error.lower()


# --- degraded path (mocked browser) -----------------------------------------

class _FakePage:
    def __init__(self, meta):
        self._meta = meta
        self.url = "https://www.instagram.com/reel/x/"

    def goto(self, *a, **k):
        pass

    def wait_for_timeout(self, *a, **k):
        pass

    def evaluate(self, js):
        if "password" in js:
            return False  # not a login wall
        return self._meta


class _FakeCtx:
    def __init__(self, page):
        self._page = page

    def new_page(self):
        return self._page

    def close(self):
        pass


class _FakeChromium:
    def __init__(self, page):
        self._page = page

    def launch_persistent_context(self, *a, **k):
        return _FakeCtx(self._page)


class _FakeP:
    def __init__(self, page):
        self._page = page

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    @property
    def chromium(self):
        return _FakeChromium(self._page)


def test_capture_degraded(monkeypatch, tmp_path):
    meta = {"title": "Some reel", "caption": "Here is the caption",
            "author": "somecreator", "video": ""}
    monkeypatch.setattr(social_capture, "sync_playwright", lambda: _FakeP(_FakePage(meta)))
    monkeypatch.setattr(config, "SOCIAL_BROWSER_PROFILE", str(tmp_path / "profile"))
    cap = social_capture.capture("https://www.instagram.com/reel/x/")
    assert cap.ok
    assert cap.degraded
    assert cap.caption == "Here is the caption"
    assert cap.author == "somecreator"
    assert cap.file_path == ""


def test_capture_login_wall(monkeypatch, tmp_path):
    # A page whose evaluate reports a password field -> login wall.
    page = _FakePage({"title": "Log in", "caption": "", "author": "", "video": ""})
    page.url = "https://www.instagram.com/accounts/login/"
    monkeypatch.setattr(social_capture, "sync_playwright", lambda: _FakeP(page))
    monkeypatch.setattr(config, "SOCIAL_BROWSER_PROFILE", str(tmp_path / "profile"))
    cap = social_capture.capture("https://www.instagram.com/reel/x/")
    assert not cap.ok
    assert "login" in cap.error.lower()
