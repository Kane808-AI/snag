# Snag

Turn a saved TikTok into your next action.

Snag is a capture app. Send it a TikTok link (or upload the video file), and it
returns the transcript, an AI-written note, and a triage pass. Save it to a
searchable vault, and an Actions queue surfaces what to do next.

## The loop

Save → Transcribe → Understand → Act.

1. Send a TikTok link or video file to the bot.
2. It transcribes the audio (ElevenLabs server-side, falling back to local faster-whisper).
3. DeepSeek writes the note (summary, key ideas, why it matters, recommendations, tags) and the triage (stage, action type, impact, effort).
4. Save it, search it, and act on it from the Actions queue.

## Why it exists

Saved folders are where ideas go to die. Snag forces a decision on every save:
act on it, reference it, or file it.

## Lineage

Snag is v2 of TikTok Brain, an OpenClaw-era capture → transcribe → categorize
pipeline with a ClickUp-backed triage dashboard. Snag is the same loop rebuilt
as a standalone consumer product: text-only and cost-first (ElevenLabs +
DeepSeek), a SQLite vault, no ClickUp, and an Actions queue no competitor ships.

## Current state

- Live and dogfooded on Telegram. TikTok links and video files work.
- The web app and native share-sheet capture are on the roadmap, gated on validation.
- TikTok links only for now. Other sources come later.

## How it's built

- Telegram bot (long polling), stdlib Python, launchd on macOS.
- ElevenLabs server-side transcription (fast path) plus local faster-whisper fallback.
- DeepSeek for note and triage, text-only, no vision.
- SQLite vault (users, usage, vault, jobs) with an async job queue.

## Run it

```bash
cp .env.example .env            # fill in your keys
python3 test_pipeline.py "https://www.tiktok.com/t/XXXX"
python3 bot.py
```

See `.env.example` for the required keys. Transcription needs `faster-whisper`
and `ffmpeg`; TikTok download fallback needs `yt-dlp`. Tests: `pytest -q`.

## Find Snag

- Telegram: @snagcapturebot
- X: @snagcapture
