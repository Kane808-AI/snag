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
import json
import shutil
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
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
    base = [YTDLP, "--no-update", "-f", "b[ext=mp4]/mp4/best", "-o", dest]
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


def transcript_from_url(url):
    """Primary path: ElevenLabs server-side transcription. No download, so
    TikTok's anti-scraping block never applies. Returns (ok, transcript, error).

    This is what makes Snag work when the download adapters fail. It mirrors the
    path in the OpenClaw tiktok_brain.py pipeline that Chris confirmed works.
    """
    import elevenlabs_transcribe

    try:
        text = elevenlabs_transcribe.transcribe_url(url)
    except elevenlabs_transcribe.ElevenLabsTranscribeError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", repr(e)

    if text and text.strip():
        return True, text.strip(), ""
    return False, "", "empty transcript"

