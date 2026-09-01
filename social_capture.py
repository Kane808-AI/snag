"""Instagram / Facebook capture via a logged-in browser (Playwright).

Tier-2 goal: extract the actual video (to transcribe) plus caption and author.
Falls back to DOM metadata (caption + author, no video) when the video cannot
be extracted, matching what Readwise Reader ships.

Mechanism = "assume the user is logged in": a persistent browser profile that
Chris logs into Instagram/Facebook in ONCE. Playwright reuses that profile, so
no cookie export and no per-capture login. Public Facebook videos often need no
login at all; Instagram needs the profile signed in. The profile lives at
config.SOCIAL_BROWSER_PROFILE (default data/browser-profile).

Known limits (v1): runs headless under launchd (no display), which Meta can
detect; engagement counts are not yet extracted from IG/FB DOM; the profile
cannot serve two captures at once (the bot is single-worker, so this is fine).
"""
import re
import shutil
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import config

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


@dataclass
class SocialCapture:
    ok: bool
    platform: str = ""
    file_path: str = ""       # local mp4 when the video was extracted
    caption: str = ""
    author: str = ""
    title: str = ""
    thumbnail_url: str = ""  # safe public Open Graph source image
    engagement: dict = field(default_factory=dict)
    degraded: bool = False    # metadata-only (no video)
    error: str = ""


def platform_of(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower().rstrip(".")
    except ValueError:
        return ""
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "instagram"
    if (host == "facebook.com" or host.endswith(".facebook.com")
            or host == "fb.com" or host.endswith(".fb.com")
            or host == "fb.watch" or host.endswith(".fb.watch")):
        return "facebook"
    return ""


def _is_login_wall(page):
    try:
        u = (page.url or "").lower()
        if "/accounts/login" in u or "/login" in u or "login.php" in u:
            return True
        return bool(page.evaluate(
            "() => !!document.querySelector('input[type=\"password\"]')"))
    except Exception:
        return False


def _extract_meta(page):
    js = """() => {
      const meta = (p) => {
        const el = document.querySelector('meta[property="' + p + '"]')
                 || document.querySelector('meta[name="' + p + '"]');
        return el ? (el.content || '').trim() : '';
      };
      const v = document.querySelector('video');
      const vsrc = v ? (v.currentSrc || v.src || '') : '';
      return {
        title: meta('og:title') || document.title || '',
        caption: meta('og:description') || '',
        author: meta('article:author') || meta('og:site_name') || '',
        image: meta('og:image') || meta('twitter:image') || '',
        video: vsrc,
      };
    }"""
    return page.evaluate(js)


def _download(url, dest, referer):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _safe_preview_url(candidate, page_url):
    try:
        value = urllib.parse.urljoin(page_url, candidate or "")
        parsed = urllib.parse.urlparse(value)
    except (TypeError, ValueError):
        return ""
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def capture(url, timeout_s=90):
    if sync_playwright is None:
        return SocialCapture(ok=False, error="playwright not installed")
    platform = platform_of(url)
    if not platform:
        return SocialCapture(ok=False, error="not an Instagram or Facebook link")

    profile = Path(config.SOCIAL_BROWSER_PROFILE)
    profile.mkdir(parents=True, exist_ok=True)
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    dest = str(Path(config.WORK_DIR) / f"social-{uuid.uuid4().hex[:12]}.mp4")

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile), headless=True, user_agent=UA,
                viewport={"width": 1280, "height": 900},
            )
            try:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded",
                          timeout=timeout_s * 1000)
                page.wait_for_timeout(5000)  # let the SPA render
                if _is_login_wall(page):
                    return SocialCapture(
                        ok=False, platform=platform,
                        error=(f"{platform.title()} is showing a login wall. "
                               "Sign in once in the Snag browser profile, then try again."))
                meta = _extract_meta(page)
                title = (meta.get("title") or "").strip()
                caption = (meta.get("caption") or "").strip()
                author = (meta.get("author") or "").strip()
                thumbnail_url = _safe_preview_url(meta.get("image"), page.url)
                video = (meta.get("video") or "").strip()

                if video.startswith("http"):
                    try:
                        _download(video, dest, url)
                        if Path(dest).stat().st_size > 10_000:
                            return SocialCapture(
                                ok=True, platform=platform, file_path=dest,
                                caption=caption, author=author, title=title,
                                thumbnail_url=thumbnail_url)
                    except Exception:
                        pass  # fall through to degraded metadata
                if caption or title:
                    return SocialCapture(
                        ok=True, platform=platform, caption=caption,
                        author=author, title=title, thumbnail_url=thumbnail_url,
                        degraded=True)
                return SocialCapture(
                    ok=False, platform=platform,
                    error="couldn't extract the video or caption from that page")
            finally:
                ctx.close()
    except Exception as e:
        return SocialCapture(ok=False, platform=platform, error=repr(e))
