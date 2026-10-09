# Snag

Save anything. Get the idea back.

Snag is a capture app with one job: turn anything you save into something you can
actually use. Send it a link or a file and it comes back with a summary, the key
ideas, why it matters, and a triage that tells you what to do next. Everything
lands in a searchable vault, so nothing you save dies in a folder.

Two surfaces drive one pipeline: a Telegram bot and a local web app.

## The loop

Save, extract, understand, recommend.

1. **Save.** Send a link (TikTok, YouTube, X, Instagram, Facebook, any article)
   or upload a file.
2. **Extract.** Video is transcribed locally with faster-whisper. YouTube uses
   native captions. Text is pulled straight off the page. There is no paid
   speech-to-text anywhere in the pipeline.
3. **Understand.** DeepSeek writes the note: summary, key ideas, why it worked,
   why it matters, a reusable pattern, recommendations, and tags. A second pass
   adds a triage: stage, action type, impact, and effort. Real view, like, and
   save counts pulled from the source ground the impact score, so it reflects
   proven reach instead of a guess.
4. **Recommend.** Two to four concrete next actions, saved to the vault with the
   full transcript.

## Why it exists

Saved folders are where ideas go to die. Snag forces a decision on every save:
act on it, reference it, or file it. The name is the product. Snag it all.

## Architecture

Three tiers, one pipeline.

- `service.py`: the pure capture pipeline, zero Telegram imports.
  `capture_url`, `capture_file`, and `capture_text` each return a `CaptureResult`.
- `bot.py`: a thin Telegram adapter over the service.
- `webview/` and `web/`: a localhost web API and a TanStack Start frontend.

Supporting modules: `ingest.py` (yt-dlp plus ScrapeCreators and ScrapTik
failover), `social_capture.py` (Playwright for Instagram and Facebook),
`analyze.py` (faster-whisper plus DeepSeek), and `db.py` (SQLite vault with FTS5
search).

Cost first by design: text only analysis, free transcription, no multimodal
model. The original build sent every video to a multimodal model and paid per
minute of transcription. Those paths are gone.

## Built by an AI agent team

Snag is developed by a small team of AI agents orchestrated through Hermes and a
Kanban board. Work lands as pull requests: a Builder agent opens a feature branch
and a PR, a Verify agent runs QA, and changes merge on approval. Every feature
commit in this repo is the output of that loop.

## Run it

```bash
cp .env.example .env            # fill in your keys
python3 test_pipeline.py "https://www.tiktok.com/t/XXXX"
python3 bot.py
```

Tests:

```bash
pytest -q                        # 157 tests
```

See `.env.example` for the required keys. Transcription needs `faster-whisper`
and `ffmpeg`. TikTok download fallback needs `yt-dlp`.

## Find Snag

- Telegram: @snagcapturebot
- X: @snagcapture
