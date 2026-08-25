"""
TikTok ingestion with vendor failover.

Order of attempts:
  1. ScrapeCreators  (robust, proxy/session-backed; returns CDN URL + often a transcript)
  2. ScrapTik        (RapidAPI failover for status-10240 / region-locked)
  3. yt-dlp          (local last resort; works for most public videos)

Every path returns an IngestResult so the analyze layer is vendor-agnostic.
The whole point: when raw yt-dlp returns "video unavailable", a commercial vendor
with a real proxy pool usually still gets it.
"""
import gzip
import io
import json
import re
import shutil
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import config


@dataclass
class IngestResult:
    ok: bool
    file_path: str = ""          # local mp4 path for the analyze layer
    native_transcript: str = ""  # transcript if the vendor supplied one (saves a call)
    duration: int = 0
    source: str = ""             # which adapter succeeded
    error: str = ""
    meta: dict = field(default_factory=dict)


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
UA += "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _download_to(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def _workdir():
    Path(config.WORK_DIR).mkdir(parents=True, exist_ok=True)
    return config.WORK_DIR


# --- Adapter 1: ScrapeCreators ----------------------------------------------
def _via_scrapecreators(url, dest):
    if not config.SCRAPECREATORS_API_KEY:
        return None
    api = "https://api.scrapecreators.com/v1/tiktok/video?url=" + urllib.parse.quote(url, safe="")
    data = _http_get_json(api, headers={"x-api-key": config.SCRAPECREATORS_API_KEY, "User-Agent": UA})
    # Response shape is vendor-specific; pull the no-watermark download URL defensively.
    dl = (
        data.get("download_url")
        or data.get("video", {}).get("download_addr")
        or data.get("video", {}).get("play_addr")
        or data.get("aweme_detail", {}).get("video", {}).get("play_addr", {}).get("url_list", [None])[0]
    )
    if not dl:
        return None
    _download_to(dl, dest)
    transcript = data.get("transcript", "") or ""
    dur = int(data.get("duration", 0) or data.get("video", {}).get("duration", 0) or 0)
    return IngestResult(
        ok=True, file_path=dest, native_transcript=transcript,
        duration=dur, source="scrapecreators", meta={"raw_keys": list(data.keys())},
    )


# --- Adapter 2: ScrapTik (RapidAPI) -----------------------------------------
def _via_scraptik(url, dest):
    if not config.SCRAPTIK_API_KEY:
        return None
    api = "https://scraptik.p.rapidapi.com/web/video?url=" + urllib.parse.quote(url, safe="")
    headers = {
        "x-rapidapi-key": config.SCRAPTIK_API_KEY,
        "x-rapidapi-host": "scraptik.p.rapidapi.com",
        "User-Agent": UA,
    }
    data = _http_get_json(api, headers=headers)
    dl = None
    aweme = data.get("aweme_detail") or data
    pa = aweme.get("video", {}).get("play_addr", {})
    if isinstance(pa, dict):
        dl = (pa.get("url_list") or [None])[0]
    dl = dl or aweme.get("download_url")
    if not dl:
        return None
    _download_to(dl, dest)
    dur = int(aweme.get("video", {}).get("duration", 0) or 0) // 1000
    return IngestResult(ok=True, file_path=dest, duration=dur, source="scraptik")


# --- Adapter 3: yt-dlp ------------------------------------------------------
# Resolve absolute binary paths once — launchd services don't get the user's
# shell PATH, so a bare "yt-dlp" raises FileNotFoundError under launchd.
# Prefer the dedicated ~/.hermes venv yt-dlp (bundled with curl_cffi for TLS
# impersonation, which TikTok now requires); it survives `brew upgrade yt-dlp`.
_VENV_YTDLP = Path.home() / ".hermes" / "venv" / "ytdlp" / "bin" / "yt-dlp"
YTDLP = str(_VENV_YTDLP) if _VENV_YTDLP.exists() else (shutil.which("yt-dlp") or "/opt/homebrew/bin/yt-dlp")
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def _via_ytdlp(url, dest):
    # TikTok blocks anonymous yt-dlp via TLS fingerprinting ("Unexpected
    # response from webpage request"). --impersonate chrome (curl_cffi) mimics
    # Chrome's TLS so the request passes; a second attempt adds Chrome cookies
    # for login-only / age-gated videos. Verified 2026-08-22 against three URLs.
    # bestvideo+bestaudio (merged) always carries an audio track; the old
    # "b[ext=mp4]/mp4/best" selector fell through to a video-only mp4 (format
    # 399: av01, acodec=none), which crashed faster-whisper with IndexError.
    base = [YTDLP, "--no-update", "-f", "bestvideo*+bestaudio/best", "-o", dest]
    attempts = [
        base + ["--impersonate", "chrome", url],
        base + ["--impersonate", "chrome", "--cookies-from-browser", "chrome", url],
    ]
    last_err = "yt-dlp failed"
    for cmd in attempts:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except FileNotFoundError:
            return IngestResult(ok=False, source="yt-dlp", error=f"yt-dlp binary not found at {YTDLP}")
        except subprocess.TimeoutExpired:
            last_err = "download timed out"
            continue
        if proc.returncode == 0 and Path(dest).exists():
            break
        last_err = (proc.stderr or proc.stdout or "yt-dlp failed")[-500:]
    else:
        return IngestResult(ok=False, source="yt-dlp", error=last_err)
    dur = 0
    try:
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", dest],
            capture_output=True, text=True, timeout=30,
        )
        dur = int(float(probe.stdout.strip() or 0))
    except Exception:
        pass
    return IngestResult(ok=True, file_path=dest, duration=dur, source="yt-dlp")


def ingest(url):
    """Try each adapter in reliability order; return the first success."""
    import uuid
    dest = str(Path(_workdir()) / f"video-{uuid.uuid4().hex[:12]}.mp4")
    Path(dest).unlink(missing_ok=True)

    errors = []
    for adapter in (_via_scrapecreators, _via_scraptik):
        try:
            res = adapter(url, dest)
            if res and res.ok:
                return res
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as e:
            errors.append(f"{adapter.__name__}: {e}")

    # Local fallback
    res = _via_ytdlp(url, dest)
    if res.ok:
        return res
    errors.append(f"yt-dlp: {res.error}")

    return IngestResult(
        ok=False,
        error="All ingestion adapters failed. The video may be deleted, private, or "
              "region-locked.\n" + "\n".join(errors),
    )


def probe_duration(url):
    """Lightweight duration check without downloading the video.

    Uses yt-dlp in metadata-only mode. Returns seconds as int, or None when the
    duration cannot be determined (region locks, private videos, network). The
    caller must treat None as "unknown, allow it" so a probe failure never
    blocks a legitimate user.
    """
    try:
        proc = subprocess.run(
            [YTDLP, "--no-update", "--skip-download", "--print", "%(duration)s", url],
            capture_output=True, text=True, timeout=45,
        )
        val = (proc.stdout or "").strip()
        return int(float(val)) if val and val != "NA" else None
    except Exception:
        return None


def probe_file_duration(path):
    """Duration of a local video/audio file via ffprobe. None on any failure."""
    try:
        probe = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return int(float(probe.stdout.strip() or 0))
    except Exception:
        return None


# --- Any-URL text ingestion (capture anything, Chris 2026-08-24) ------------

# Domains that route through the video pipeline (transcribe). Everything else
# is treated as text: fetched, extracted, and analyzed directly. Instagram /
# Facebook / X posts land on the text path (their og:title / og:description meta
# carries the caption), which is a good first cut until reel/OCR support lands.
VIDEO_DOMAINS = (
    "tiktok.com", "vm.tiktok", "vt.tiktok",
    "youtube.com", "youtu.be", "m.youtube.com",
)


def is_url(text):
    """True for a bare URL whose scheme is http:// or https:// (case-insensitive).

    Requires the ``://`` so bare words like "httpfoo" are not treated as links.
    """
    if not text:
        return False
    low = text.lower()
    return low.startswith("http://") or low.startswith("https://")


# Matches the first http(s) URL anywhere in a message, e.g. the URL inside
# "check this https://x.com out". Case-insensitive on the scheme.
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


def first_url(text):
    """First URL found anywhere in a message, or None if there isn't one."""
    if not text:
        return None
    m = _URL_RE.search(text)
    return m.group(0) if m else None


def is_video_url(text):
    if not is_url(text):
        return False
    # Hostname matching, not substring: youtube.com.evil.com / notyoutube.com /
    # ?ref=tiktok.com in the query must NOT route to the video pipeline.
    try:
        host = urllib.parse.urlparse(text).netloc.lower().rstrip(".")
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in VIDEO_DOMAINS)


def is_social_video(url):
    """True when a URL is a login-walled social VIDEO: Instagram reels/tv and
    Facebook watch/videos. These are video content, but they cannot be fetched
    anonymously (login wall), so the bot gives an honest message instead of
    producing a garbage note or a raw HTTP error.

    Same hostname-suffix matching as is_video_url (exact host or dot-suffix),
    so instagram.com.evil.com / notfacebook.com never match. False for text
    posts (/p/, /groups/, /marketplace/), the homepages, and non-social hosts.
    """
    if not is_url(url):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower().rstrip(".")
        path = parsed.path.lower()
    except ValueError:
        return False
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "/reel/" in path or "/reels/" in path or "/tv/" in path
    if (host == "facebook.com" or host.endswith(".facebook.com")
            or host == "fb.com" or host.endswith(".fb.com")):
        return "/share/v/" in path or "/watch/" in path or "/videos/" in path
    return False


YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com")


def is_youtube(url):
    """True for YouTube watch/short URLs (hostname-suffix match like is_video_url)."""
    if not is_url(url):
        return False
    try:
        host = urllib.parse.urlparse(url).netloc.lower().rstrip(".")
    except ValueError:
        return False
    return any(host == d or host.endswith("." + d) for d in YOUTUBE_DOMAINS)


def youtube_transcript(url):
    """Extract YouTube's native captions via yt-dlp. Free, fast, no API key.

    Returns (ok, text, error). This is the primary YouTube path: ElevenLabs
    source_url rejects watch-page URLs (it wants a direct media link), and the
    local faster-whisper fallback is slow on CPU and unreliable. Captions
    handle any video length and cost nothing.
    """
    import glob
    import tempfile

    tmp = tempfile.mkdtemp(prefix="snag-subs-")
    out_tmpl = str(Path(tmp) / "sub")
    try:
        subprocess.run(
            [YTDLP, "--no-update", "--skip-download", "--write-auto-subs",
             "--write-subs", "--sub-langs", "en.*", "--sub-format", "vtt",
             "--output", out_tmpl, url],
            capture_output=True, text=True, timeout=180,
        )
        vtt_files = sorted(glob.glob(str(Path(tmp) / "sub*.vtt")))
        if not vtt_files:
            return False, "", "no captions available on this video"
        chosen = next((f for f in vtt_files if f.endswith(".en.vtt")), vtt_files[0])
        with open(chosen, encoding="utf-8", errors="replace") as f:
            text = _clean_vtt(f.read())
        if not text.strip():
            return False, "", "empty captions"
        return True, text.strip(), ""
    except subprocess.TimeoutExpired:
        return False, "", "caption download timed out"
    except Exception as e:
        return False, "", repr(e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _clean_vtt(text):
    """Strip VTT timing/metadata and return clean caption text.

    YouTube auto-captions are VTT with word-level timing: rolling-window cues
    carry inline <00:00:00.000> timestamps and <c> tags, plus duplicate
    "snapshot" cues. Keep only the clean snapshot lines, drop exact repeats.
    """
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if "-->" in line:
            continue
        if "<" in line:  # word-timed line (carries <c> / <00:00:00.000> tags)
            continue
        if out and out[-1] == line:
            continue
        out.append(line)
    return " ".join(out)


# Social platforms that block anonymous fetching (login walls). When fetch_text
# fails on one of these, the user gets a clear "paste the text instead" message
# rather than a raw HTTP error.
SOCIAL_LOGINWALL_DOMAINS = ("facebook.com", "fb.com", "instagram.com", "x.com", "twitter.com", "linkedin.com")

_SOCIAL_LOGINWALL_NAMES = {
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "instagram.com": "Instagram",
    "x.com": "X",
    "twitter.com": "X",
    "linkedin.com": "LinkedIn",
}


def is_social_blocked(url):
    """Platform display name when the host is a login-walled social site.

    Same hostname matching as is_video_url (exact host or dot-suffix), so
    facebook.com.evil.com / notfacebook.com never match. Returns None for
    everything else.
    """
    if not is_url(url):
        return None
    try:
        host = urllib.parse.urlparse(url).netloc.lower().rstrip(".")
    except ValueError:
        return None
    for domain in SOCIAL_LOGINWALL_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return _SOCIAL_LOGINWALL_NAMES[domain]
    return None


class _TextExtractor(HTMLParser):
    """Strip a page to readable text: title, meta description, and body.

    Skips script/style/noscript/svg/head/template. Emits newlines at block
    boundaries so paragraphs survive. stdlib only.
    """

    SKIP = {"script", "style", "noscript", "iframe", "svg", "template"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6",
             "article", "section", "blockquote", "tr", "pre"}

    _MAX_TITLE_CHARS = 500

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._chunks = []
        self._skip_depth = 0
        self._in_title = False
        self._title_buf = []
        self._title_len = 0

    def _finalize_title(self):
        """Stop collecting title text and commit what we have.

        Called from </title> AND from <body>, so a page with an unclosed
        <title> (broken HTML) no longer swallows the whole body.
        """
        if not self.title and self._title_buf:
            self.title = "".join(self._title_buf).strip()[:self._MAX_TITLE_CHARS]
        self._title_buf = []
        self._title_len = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "body":
            # A body start tag means the head (and any broken <title>) is done.
            self._finalize_title()
        elif tag == "meta":
            d = dict(attrs)
            key = (d.get("name") or d.get("property") or "").lower()
            content = (d.get("content") or "").strip()
            if key == "og:title" and not self.title and content:
                self.title = content
            elif key in ("og:description", "description") and not self.description and content:
                self.description = content
        elif tag in self.BLOCK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._finalize_title()
        elif tag in self.BLOCK:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            # Cap the accumulated title so a pathological page can't grow
            # unbounded memory; the cap also applies at finalize time.
            room = self._MAX_TITLE_CHARS - self._title_len
            if room > 0:
                chunk = data[:room]
                self._title_buf.append(chunk)
                self._title_len += len(chunk)
            return
        self._chunks.append(data)

    def text(self):
        lines = [re.sub(r"\s+", " ", ln).strip() for ln in "".join(self._chunks).split("\n")]
        return "\n".join(ln for ln in lines if ln)


def _close_unclosed_title(html):
    """Close a missing </title> so the body is still parsed.

    CPython's HTMLParser (3.13+) reads <title> as raw text buffered until
    </title>, so a broken page with a missing </title> swallows everything
    after it — the <body> tag never even fires. Insert the close tag at the
    first <body ...> boundary so the rest of the page parses normally.
    """
    if "</title" in html.lower():
        return html
    m = re.search(r"<title\b[^>]*>", html, re.IGNORECASE)
    if not m:
        return html
    rest = html[m.end():]
    b = re.search(r"<body\b", rest, re.IGNORECASE)
    if not b:
        return html
    cut = m.end() + b.start()
    return html[:cut] + "</title>" + html[cut:]


def _html_to_text(html):
    p = _TextExtractor()
    try:
        p.feed(_close_unclosed_title(html))
    except Exception:
        pass
    head = []
    if p.title:
        head.append("TITLE: " + p.title)
    if p.description:
        head.append("DESCRIPTION: " + p.description)
    body = p.text()
    if head:
        return "\n\n".join(head + ["", body]).strip()
    return body


_MAX_PAGE_BYTES = 2_000_000
_MAX_TEXT_CHARS = 8000

# Content types we refuse to treat as text, with a friendly message. Keeps
# PDFs / images / archives / raw binaries from becoming mojibake notes.
_UNSUPPORTED_CTYPES = {
    "application/pdf", "application/octet-stream", "application/zip", "application/gzip",
}
_UNSUPPORTED_CTYPE_PREFIXES = ("image/", "video/", "audio/")
_HTML_CTYPES = {"text/html", "application/xhtml+xml"}


def _looks_binary(text):
    """True when a decoded payload is mostly control / replacement characters.

    U+FFFD appears for every undecodable UTF-8 byte; \x00-\x08 are control
    bytes that never appear in real prose. A high ratio means mojibake, not
    text, so the caller should treat it as unreadable.
    """
    if not text:
        return False
    bad = sum(1 for ch in text if ch == "\ufffd" or "\x00" <= ch <= "\x08")
    return bad / len(text) > 0.30


def _gunzip(data, limit):
    """Decompress gzip bytes, capping output at `limit`. None on failure."""
    out = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            while True:
                chunk = gz.read(65536)
                if not chunk:
                    break
                out += chunk
                if len(out) >= limit:
                    break
    except Exception:
        return None
    return bytes(out[:limit])


def fetch_text(url):
    """Fetch a URL and extract readable text. Returns (ok, text, error).

    Handles HTML (title + description + body) and plain text. Accepts gzip
    (Content-Encoding / magic bytes) transparently, whitelists text/* and
    application/xhtml+xml content types, rejects binary payloads with a
    friendly error, and caps the output so a huge page never blows the note
    prompt.
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            data = r.read(_MAX_PAGE_BYTES)
    except Exception as e:
        return False, "", repr(e)

    # Transparent gzip: some servers send gzip with the wrong/absent
    # Content-Encoding header, so sniff the magic bytes as well.
    if data[:2] == b"\x1f\x8b":
        data = _gunzip(data, _MAX_PAGE_BYTES)
        if data is None:
            return False, "", "couldn't decompress that response"

    # Content-type gate: whitelist text/* and XHTML; reject obvious binaries.
    if ctype:
        if ctype in _UNSUPPORTED_CTYPES or ctype.startswith(_UNSUPPORTED_CTYPE_PREFIXES):
            return False, "", f"this file type isn't supported yet ({ctype})"
        if not (ctype.startswith("text/") or ctype in _HTML_CTYPES):
            return False, "", f"this file type isn't supported yet ({ctype})"

    try:
        html = data.decode("utf-8", errors="replace")
    except Exception:
        html = data.decode("latin-1", errors="replace")

    if ctype in _HTML_CTYPES or "<html" in html[:500].lower():
        text = _html_to_text(html)
    else:
        text = html.strip()

    if _looks_binary(text):
        return False, "", "couldn't read that content (binary or garbled data)"

    if not text.strip():
        return False, "", "no readable text on that page"
    return True, text.strip()[:_MAX_TEXT_CHARS], ""
