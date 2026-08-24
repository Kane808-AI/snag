#!/usr/bin/env python3
"""Transcribe a TikTok URL via ElevenLabs server-side speech-to-text.

Uses the official /v1/speech-to-text endpoint with source_url + xi-api-key.
This is the authenticated path (the no-auth /v1/speech-to-text/url endpoint was
undocumented and now returns 401, so it is retired). Server-side fetch means
TikTok's anti-scraping block never applies to our machine.

Returns the transcript string on success; raises on any other outcome.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
MODEL_ID = "scribe_v2"
DEFAULT_TIMEOUT = 300


class ElevenLabsTranscribeError(Exception):
    """Raised when the endpoint returns anything other than a valid transcript."""


def _load_env_key(name):
    env_path = os.path.expanduser("~/.hermes/workspace/snag/.env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{name}="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return val
    return os.environ.get(name, "")


def transcribe_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY") or _load_env_key("ELEVENLABS_API_KEY")
    if not api_key:
        raise ElevenLabsTranscribeError("ELEVENLABS_API_KEY not set")

    boundary = "----SnagElevenLabsBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="model_id"\r\n\r\n{MODEL_ID}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="source_url"\r\n\r\n{url}\r\n'
        f"--{boundary}--\r\n"
    ).encode()

    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "xi-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise ElevenLabsTranscribeError(f"HTTP {e.code}: {err_body}") from None
    except urllib.error.URLError as e:
        raise ElevenLabsTranscribeError(f"Network error: {e}") from None

    text = (data.get("text") or "").strip()
    if not text:
        raise ElevenLabsTranscribeError(f"Empty transcript in response: {list(data.keys())}")
    return text


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: elevenlabs_transcribe.py <tiktok_url>", file=sys.stderr)
        return 1
    try:
        print(transcribe_url(sys.argv[1]))
        return 0
    except ElevenLabsTranscribeError as e:
        print(f"ElevenLabs transcribe failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
