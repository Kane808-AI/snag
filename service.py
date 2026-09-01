"""Shared capture service for Snag. Pure URL / file / text -> note pipeline.

No Telegram. Both the Telegram bot (bot.py) and the web viewer (webview/server.py
POST /api/capture) drive this same pipeline, so the capture logic is never forked.

Public entry points (each returns a CaptureResult):

    capture_url(url, user_id)      route a link: video / social / text, then
                                   ingest -> transcribe -> analyze -> triage
    capture_file(file_path, ...)   transcribe a local media file, then analyze
    capture_text(text, ...)        analyze text that is already in hand

ok=True carries the note + triage + transcript ready for any surface to render
and (optionally) save. ok=False carries a machine-readable `kind` plus a
human-facing `error`/`duration` so each surface maps it to its own UI copy.
"""

from dataclasses import dataclass, field
import re

import config
import db
import ingest
import analyze
import social_capture


@dataclass
class CaptureResult:
    ok: bool
    # success payload (ready to render and save)
    note: dict = field(default_factory=dict)       # summary, key_ideas, why_it_worked, ...
    triage: dict = field(default_factory=dict)     # stage, action_type, impact, effort
    transcript: str = ""                           # full transcript / caption / article text
    content_type: str = "video"                    # "video" | "article" | "text"
    url: str = ""
    engagement: dict = field(default_factory=dict)
    thumbnail_url: str = ""
    analysis_state: str = "complete"  # "complete" | "awaiting_ai"
    # failure payload
    kind: str = ""      # "" | "duration" | "analyze" | "file_empty" | "social" |
                        # "social_empty" | "loginwall" | "fetch" | "ingest"
    error: str = ""     # detail: platform name, ingest error, fetch error, ...
    duration: int = 0   # seconds, when the duration gate rejected


def _is_free(user_id):
    return not db.is_pro(user_id)


def _duration_gate(user_id, duration):
    """True when a free user's video runs past the free-plan cap."""
    return bool(_is_free(user_id) and duration and duration > config.FREE_MAX_VIDEO_SECONDS)


def _analyze(transcript, engagement=None, caption=""):
    """transcript (+ optional caption) -> (note, triage, full_transcript).

    Raises on note failure (the caller maps it to kind="analyze").
    """
    if caption:
        transcript = f"Caption: {caption.strip()}\n\n{transcript}".strip()
    note = analyze.analyze_note(transcript, engagement=engagement)
    try:
        triage = analyze.analyze_triage({**note, "transcript": transcript})
    except Exception:
        triage = {"stage": "Inbox", "action_type": "Just reference", "impact": 3, "effort": 3}
    return note, triage, transcript


def _success(note, triage, transcript, content_type, url, engagement, thumbnail_url="", analysis_state="complete"):
    return CaptureResult(
        ok=True, note=note, triage=triage, transcript=transcript,
        content_type=content_type, url=url,
        engagement=engagement or note.get("engagement") or {},
        thumbnail_url=thumbnail_url,
        analysis_state=analysis_state,
    )


def _offline_note(text, engagement=None):
    """Create an honest, saveable Inbox reference when analysis is unavailable.

    Capture must not depend on a paid model being reachable. This deliberately
    does not invent key ideas, tags, or recommendations. The extracted source
    text stays available for a later AI pass.
    """
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    title = normalized[:180].rsplit(" ", 1)[0] if len(normalized) > 180 else normalized
    return {
        "summary": title or "Saved link",
        "key_ideas": "",
        "why_it_worked": "",
        "why_it_matters": db.AWAITING_AI_MESSAGE,
        "reusable_pattern": "",
        "recommendations": "",
        "tags": [],
        "engagement": engagement or {},
        "raw": "",
    }


def capture_text(text, user_id, url="", engagement=None, caption="",
                 content_type="text", thumbnail_url=""):
    """Analyze text that is already available (paste, caption, native transcript)."""
    if not (text or "").strip():
        return CaptureResult(ok=False, kind="file_empty", error="")
    try:
        note, triage, transcript = _analyze(text, engagement=engagement, caption=caption)
    except Exception:
        transcript = f"Caption: {caption.strip()}\n\n{text}".strip() if caption else text.strip()
        return _success(
            _offline_note(transcript, engagement),
            {"stage": "Inbox", "action_type": "Just reference", "impact": 3, "effort": 3},
            transcript,
            content_type,
            url,
            engagement,
            thumbnail_url,
            "awaiting_ai",
        )
    return _success(note, triage, transcript, content_type, url, engagement, thumbnail_url)


def capture_file(file_path, user_id, url="", engagement=None, caption="", thumbnail_url=""):
    """Transcribe a local media file, then analyze. Caption fallback when silent."""
    dur = ingest.probe_file_duration(file_path) if _is_free(user_id) else None
    if _duration_gate(user_id, dur):
        return CaptureResult(ok=False, kind="duration", duration=dur or 0)
    try:
        transcript = analyze.transcribe_local(file_path)
    except Exception:
        transcript = ""
    if not transcript.strip():
        if (caption or "").strip():
            # No speech to transcribe (music-only / slideshow); analyze the caption.
            return capture_text(caption, user_id, url=url, engagement=engagement,
                                content_type="article", thumbnail_url=thumbnail_url)
        return CaptureResult(ok=False, kind="file_empty", error="")
    return capture_text(transcript, user_id, url=url, engagement=engagement,
                        caption=caption, content_type="video", thumbnail_url=thumbnail_url)


def capture_url(url, user_id):
    """Route a link to the right pipeline and capture it. No Telegram."""
    if ingest.is_video_url(url):
        return _capture_video(url, user_id)
    if ingest.is_social_video(url):
        return _capture_social(url, user_id)
    return _capture_text_url(url, user_id)


def _capture_video(url, user_id):
    """TikTok / YouTube path: native captions first, then download + local whisper."""
    dur = ingest.probe_duration(url) if _is_free(user_id) else None
    if _duration_gate(user_id, dur):
        return CaptureResult(ok=False, kind="duration", duration=dur or 0)
    if ingest.is_youtube(url):
        ok, transcript, _err = ingest.youtube_transcript(url)
        if ok:
            return capture_text(transcript, user_id, url=url, content_type="video",
                                thumbnail_url=ingest.youtube_thumbnail_url(url))
    result = ingest.ingest(url)
    if not result.ok:
        return CaptureResult(ok=False, kind="ingest", error=result.error, url=url)
    if _duration_gate(user_id, result.duration):
        return CaptureResult(ok=False, kind="duration", duration=result.duration)
    thumbnail_url = (result.meta or {}).get("thumbnail") or ""
    if result.native_transcript.strip():
        return capture_text(result.native_transcript, user_id, url=url,
                            engagement=result.engagement, content_type="video", thumbnail_url=thumbnail_url)
    return capture_file(result.file_path, user_id, url=url, engagement=result.engagement, thumbnail_url=thumbnail_url)


def _capture_social(url, user_id):
    """Instagram / Facebook path: browser capture (video or degraded metadata).

    Public Facebook videos are handled by yt-dlp first (verified anonymous),
    then everything else goes through the persistent logged-in browser profile.
    """
    if social_capture.platform_of(url) == "facebook":
        result = ingest.ingest(url)  # yt-dlp handles public FB videos anonymously
        if result.ok:
            meta = result.meta or {}
            caption = "\n\n".join(
                x for x in (meta.get("description"), meta.get("title")) if x).strip()
            return capture_file(result.file_path, user_id, url=url,
                                engagement=result.engagement, caption=caption,
                                thumbnail_url=(meta.get("thumbnail") or ""))
    cap = social_capture.capture(url)
    if not cap.ok:
        return CaptureResult(ok=False, kind="social",
                             error=cap.error or "I couldn't capture that.", url=url)
    if cap.file_path:
        return capture_file(cap.file_path, user_id, url=url,
                            engagement=cap.engagement, caption=cap.caption,
                            thumbnail_url=cap.thumbnail_url)
    if cap.caption or cap.title:
        text = "\n\n".join(x for x in (cap.title, cap.caption) if x).strip()
        return capture_text(text, user_id, url=url, engagement=cap.engagement,
                            content_type="article", thumbnail_url=cap.thumbnail_url)
    return CaptureResult(ok=False, kind="social_empty", error="", url=url)


def _capture_text_url(url, user_id):
    """Text path for any non-video, non-social URL: fetch, extract, analyze."""
    try:
        fetched = ingest.fetch_text(url, include_preview=True)
    except TypeError:
        # Keeps older adapters and deliberately simple test doubles compatible.
        fetched = ingest.fetch_text(url)
    ok, text, err = fetched[:3]
    thumbnail_url = fetched[3] if len(fetched) > 3 else ""
    if not ok:
        platform = ingest.is_social_blocked(url)
        if platform:
            return CaptureResult(ok=False, kind="loginwall", error=platform, url=url)
        return CaptureResult(ok=False, kind="fetch", error=err or "", url=url)
    return capture_text(text, user_id, url=url, content_type="article",
                        thumbnail_url=thumbnail_url)
