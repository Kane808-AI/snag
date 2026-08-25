"""DeepSeek analysis for Snag. Text-only, two passes:

- analyze_note(transcript)  -> structured note: summary, key_ideas, why_it_matters,
                               recommendations, tags. Renders in Telegram, stores to vault.
- analyze_triage(note)      -> JSON triage: stage, action_type, impact, effort.

Plus transcribe_local() for the video-file fallback path.
"""
import json
import re
import urllib.request
from pathlib import Path

import config
import modes

_DEEPSEEK_URL = f"{config.DEEPSEEK_BASE_URL}/chat/completions"


def _call_deepseek(messages, json_mode=False):
    body = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        _DEEPSEEK_URL,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"]


def _section(text, name):
    """Extract a **NAME** section body from the note markdown."""
    m = re.search(rf"\*\*{re.escape(name)}\*\*\s*\n+(.+?)(?=\n\*\*|\Z)", text, re.I | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def analyze_note(transcript):
    """Transcript -> structured note via DeepSeek. Returns dict of fields + raw."""
    full = modes.NOTE_PROMPT + "\n\nCONTENT:\n" + transcript
    raw = _call_deepseek([{"role": "user", "content": full}])

    tags_raw = _section(raw, "TAGS")
    tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]

    summary = _section(raw, "SUMMARY")
    key_ideas = _section(raw, "KEY IDEAS")
    why = _section(raw, "WHY IT MATTERS")
    recs = _section(raw, "RECOMMENDATIONS")

    return {
        "summary": summary,
        "key_ideas": key_ideas,
        "why_it_matters": why,
        "recommendations": recs,
        "tags": tags,
        "raw": raw,
    }


def _extract_json(text):
    """Pull the first JSON object out of a model reply that may have prose around it."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0) if m else text)


def analyze_triage(note):
    """Structured note -> JSON triage: stage, action_type, impact, effort."""
    prompt = modes.TRIAGE_PROMPT.format(
        title=note["summary"][:120],
        summary=note["summary"],
        transcript=(note.get("transcript") or "")[:4000],
    )
    raw = _call_deepseek([{"role": "user", "content": prompt}], json_mode=True)
    try:
        d = _extract_json(raw)
    except json.JSONDecodeError:
        return {
            "stage": "Inbox",
            "action_type": "Just reference",
            "impact": 3,
            "effort": 3,
        }
    return {
        "stage": d.get("stage", "Inbox"),
        "action_type": d.get("action_type", "Just reference"),
        "impact": max(1, min(5, int(d.get("impact", 3)))),
        "effort": max(1, min(5, int(d.get("effort", 3)))),
    }


def transcribe_local(file_path):
    """Transcribe a local video/audio file with faster-whisper. Returns text."""
    import os
    import shutil
    import subprocess
    import tempfile

    from faster_whisper import WhisperModel

    # Normalize to 16kHz mono WAV first. faster-whisper's PyAV decoder raises
    # IndexError on files with no audio stream (e.g. a video-only mp4) or on
    # codecs PyAV can't enumerate. Extracting audio up front makes that class
    # of failure impossible and works for any input ffmpeg can read.
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    wav = tempfile.mktemp(prefix="snag-audio-", suffix=".wav")
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-i", file_path,
             "-vn", "-ac", "1", "-ar", "16000", wav],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode != 0 or not os.path.isfile(wav) or os.path.getsize(wav) == 0:
            lines = (proc.stderr or "").strip().splitlines()
            detail = lines[0] if lines else "no audio stream"
            raise RuntimeError(f"no usable audio track: {detail}")
        model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(wav, beam_size=5)
        return " ".join([s.text for s in segments]).strip()
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
