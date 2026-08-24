# Snag PRD

Status: **draft** (code-verified 2026-08-21 against the live Hermes build)
Owner: Chris
Build: `~/.hermes/workspace/snag` (Telegram bot, stdlib Python, launchd)
Supersedes: the June 5, 2026 feature spec (HANDOFF_2026-06-05-1200-snag-prd-prep.md). Where that spec and the code disagree, the code wins.

---

## 1. Positioning & value prop

Snag is a Telegram bot that turns any link into a note and a searchable vault entry. Anything you can find on the internet, you can Snag: a website, an article, an X/Instagram/Facebook post, a TikTok, a YouTube video, an image, a PDF. The name is the product: snag it all.

**One-line value prop:** Send anything, get the idea back. Summary, why it matters, and what to do next, saved to a vault you can actually search.

The marketing line from launch prep still holds: "Your saved folder is a graveyard. Snag fixes that. Tap share, hit Snag, it saves the link, pulls a summary, and tags it automatically. One place. Actually searchable."

This is a capture app, not a social app. The job is to make anything you save cost nothing to find again and force a decision on it: act, reference, or discard.

## 2. Target user

**Primary user is Chris.** The analysis prompts are personalized to his four businesses and the triage rubric scores against them. This is a dogfooded solo-founder tool first.

The persona that generalizes: a solo operator running multiple businesses who saves links, posts, and videos from everywhere, never revisits them, and loses ideas in the saved-folder graveyard. The bot answers for them the way it answers for Chris: what is this, does it matter to my businesses, and what do I do next.

Public framing for marketing: busy founders and operators who save links and posts from everywhere for ideas and need a searchable idea vault with action triage, not a note-taking app for general links.

## 3. Core loop

Save → Transcribe → Understand → Recommend.

1. **Save.** User sends a TikTok link (tiktok.com, vm.tiktok, vt.tiktok) or uploads the video file to the bot. Quota is checked before work starts.
2. **Transcribe.** Primary path: ElevenLabs server-side transcription (authenticated `/v1/speech-to-text`, model `scribe_v2`, `source_url` + `xi-api-key`). No video is downloaded, so TikTok's anti-scraping block never applies. This is the fix for the original bug where every download path failed. Fallback path: download via 3-tier adapter failover (ScrapeCreators → ScrapTik/RapidAPI → yt-dlp) and transcribe locally with faster-whisper (`base`, CPU int8). Uploaded files go straight to local whisper.
3. **Understand.** DeepSeek text analysis, two passes. Pass one (`analyze_note`): summary, key ideas, why it matters for Chris's businesses, recommendations, tags. Pass two (`analyze_triage`, runs on save): stage (Worth Acting On / Reference / Inbox), action type (Build a tool / Make content / Test a strategy / Buy or try a tool / Just reference), impact 1-5, effort 1-5.
4. **Recommend.** The note's Recommendations section lists 2-4 concrete numbered actions tied to his businesses. The note is shown in Telegram with a 💾 Save button. Saving stores the full enriched note, the triage, and the full transcript in the vault. Retrieval is `/vault` (recent 20) and `/search <word>` (substring match across summary, key ideas, why it matters, recommendations, tags).

The loop is cost-first: text only, no video download on the primary path, no multimodal model. The old build sent every video to multimodal Gemini and that is what drove billing up. That path is gone.

## 4. Feature spec

### IN-SCOPE MVP (built and working today)

**Ingestion**
- TikTok links via Telegram message. Domain filter: tiktok.com, vm.tiktok, vt.tiktok.
- ElevenLabs server-side transcription as the primary path. No download, no auth wall on TikTok's side. The older no-auth ElevenLabs URL endpoint is retired (returns 401).
- Download failover when transcription fails: ScrapeCreators (proxy/session-backed, can return a native transcript), ScrapTik via RapidAPI, yt-dlp last resort. Local faster-whisper transcribes the downloaded file.
- Direct file upload (video, document, video note) accepted from Telegram, transcribed locally. This is the documented escape hatch for links that will not read.

**Analysis**
- DeepSeek text-only (`deepseek-v4-flash` default, temperature 0.3, max 4096 tokens). JSON mode for triage.
- Note output: Summary, Key Ideas, Why It Matters, Recommendations, Tags. One prompt, personalized to Chris's four businesses (Brand75, SalesBridge, Callahan Law SEO, his AI TikTok).
- Triage output on save: stage, action type, impact, effort. Strict rubric, calibrated to be selective. Harsh impact scoring, "Worth Acting On" only for a concrete near-term move for one of his businesses.
- Failure defaults: analysis failure shows a friendly retry message; triage failure defaults to Inbox / Just reference / 3 / 3 rather than blocking the save.

**Freemium gate**
- Free tier: 10 videos per month (config default, `.env` overridable). Metered in SQLite by calendar month (UTC).
- Quota decrements after a successful analysis, whether or not the user saves to the vault.
- On quota exhaustion the bot blocks the capture and sends a paywall message with an ⭐ Upgrade button.
- Pro users are unlimited (quota check returns None). Plan lives on the users table.

**Vault**
- SQLite (`data/app.db`), three tables: users, usage, vault. Stdlib only, no server.
- Flat structure, no folders. Auto tags from DeepSeek.
- A saved row holds the full note plus triage plus the full transcript, so a save is a complete organized idea, not a summary stub.
- `/vault` lists the 20 most recent, `/search <q>` does LIKE substring search across five text fields.
- Dashboard: a local static HTML dashboard (port 8475) renders the same vault from `data.json` and writes status updates back to the same `app.db`. The bot and the dashboard share one store.

**Billing**
- Stripe Checkout, subscription mode, single Pro price (price ID from env, amount set in Stripe).
- Checkout keyed to the Telegram user ID via `client_reference_id`.
- Webhook handler (HMAC-signed, 5-minute clock skew tolerance) flips the user to pro on `checkout.session.completed` and back to free on subscription deleted or paused.
- `/upgrade` sends the Checkout link. Promotion codes allowed.
- Landing site with terms and privacy pages exists in `site/`.

**Deployment**
- launchd agent (`com.hermes.snag.plist`), long-polling bot, stdlib only, logs in `logs/`.
- Proven end to end 2026-08-21: the exact URL that previously failed with "all ingestion adapters failed" returns a transcript, content type, and action block via ElevenLabs + DeepSeek.

### PARKED (designed or dreamed, not built, no code)

- **On-screen text extraction moat.** The differentiator that was supposed to read text burned into videos (what the eye reads on screen, not the spoken transcript). Parked until there is demand signal. No code exists.
- **Multimodal video.** Sending full videos to a vision model on every capture. Removed deliberately. It was the old build's billing driver. Cost-first text strategy wins until the moat clears a real bar.
- **Adaptive content-type modes.** The June 5 spec promised one prompt that auto-detects content type (recipe, business idea, tutorial, news) and reshapes output, plus a one-tap mode override. What exists is one strong personalized prompt with no content-type detection and no override. `modes.py` holds the two prompt constants only. The lens idea is parked.
- **Vault chat.** Chat with a saved item (Phase 1) and chat with the whole vault via vector search / pgvector (Phase 2). No code.
- **Multi-source capture.** Split as of 2026-08-24. Content types (YouTube, articles, posts, images, PDFs) are core scope, not parked; see §6. Capture surfaces (iOS share sheet, Chrome extension, web form) remain parked behind validation. None of it exists yet. The June 5 launch order (web first, extension second, iOS third) was inverted: a Telegram bot shipped first because it is the lowest-friction capture surface.
- **Tiered pricing.** Pro+ at $14.99, lifetime at $99, PDF support with a 25-page cap, 30-minute video caps. None exists. One Pro price only.
- **Manual tags and notes post-save.** The spec allowed the user to add tags and notes after saving. The bot has no such command. The vault row has a status field and the dashboard can edit status, but the bot does not.
- **Duration cap enforcement.** `FREE_MAX_VIDEO_SECONDS` is configured (180s) but no code enforces it.

## 5. Monetization model

Stripe subscription via Checkout, one Pro price, recurring. Net ~95% of revenue.

Telegram Stars was the alternative and lost on economics: ~55-70% net after Apple tax and the Fragment spread, versus ~95% with Stripe, plus Stripe gives automatic renewals and dunning. Decision is made, Stripe is the processor.

- Free: 10 captures per month, paywalled at the 11th.
- Pro: unlimited captures, single price set in Stripe (not in the repo).
- No usage-based or cost-based tiering yet. The free cap protects margins by limiting ElevenLabs + DeepSeek spend per user, but the cost per capture is not tracked anywhere (see open questions).

## 6. Multi-channel roadmap

**Live now: TikTok (and video file) via Telegram.** One content type fully working end to end.

**Core scope (Chris, 2026-08-24): capture any URL on the internet.** Snag is not a TikTok tool; it is a capture-anything tool. Any link, any content type: websites, articles, X/Instagram/Facebook posts, YouTube, images, PDFs. The core pipeline is URL → extract content → analyze → vault, where extract means transcribe (video), parse text (articles and posts), or OCR (images and PDFs). Content-type breadth is a first-class feature, not a gated nice-to-have.

Staged honestly by engine cost:
- Near-term (text content): articles, web pages, X/IG/FB posts, YouTube. Text extraction is cheaper than transcription, so these are easier than the video path that already ships.
- Later (vision content): images and PDFs need OCR/vision, which the cost-first text strategy deliberately removed. Reopen on demand signal.

**Capture surfaces stay downstream of validation:** iOS share sheet, browser extension, web form. These are where-you-capture, not what-you-capture. They still ship after the bot proves the loop. The June 5 order (web first, extension second, iOS third) is unchanged.

Validation is not defined quantitatively yet. That is an open question.

## 7. Open questions & decisions needed

1. **Pro price.** Not in the repo. The June 5 spec said $7.99. Confirm the Stripe price before any public push.
2. **Stripe webhook has no live route.** `handle_webhook` is a function waiting to be wired to an HTTP endpoint. The dashboard server does not expose it. Until that route exists with `PUBLIC_BASE_URL` set, checkout links open but no webhook flips plans in production. This is the biggest gap between "billing code exists" and "billing works."
3. **`FREE_MAX_VIDEO_SECONDS` is dead config.** 180s cap is set but never enforced. Either wire a duration gate into the ingestion path to protect margins or delete the setting.
4. **Quota counts analyses, not saves.** A free user can burn 10 captures by analyzing and never saving. Intentional or not, decide and document it.
5. **Search is LIKE, not full-text.** Substring scan across five fields per query. Fine at small vault sizes, will not scale. Decide the trigger point for moving to SQLite FTS5.
6. **Status field has no bot surface.** Vault rows carry a status and the dashboard edits it, but `/vault` does not show status and no bot command changes it. Decide whether status is a feature or dead weight.
7. **Mode override.** The June 5 "one-tap override" for content-type detection does not exist and nothing auto-detects content type. Add a real `/mode` lens system or formally drop the promise.
8. **Unit economics are untracked.** Metering counts user quota, not cost. ElevenLabs scribe_v2 per-minute cost plus DeepSeek per-capture cost is the real margin driver. Add cost accounting before user count grows.
9. **Bot identity.** The bot shares the `@tttest75bot` token with the retired OpenClaw build. Fine for testing, decide whether a fresh bot and branding launch with the public push.
10. **Validation criteria for new channels.** What counts as demand signal for X, Instagram, or the web clipper? Pick a concrete metric (capture volume, vault saves, upgrade rate, a direct ask) or the roadmap stalls on vibes.
11. **On-screen text moat trigger.** "Parked until demand signal" is a decision, the trigger is not. Define what demand would reopen it.

---

### Provenance

- Files changed: `PRD.md` created (this file). Read-only on all code.
- Commands run: none beyond reads.
- Sources: HANDOFF_2026-06-05-1200-snag-prd-prep.md, README.md, bot.py, ingest.py, analyze.py, modes.py, db.py, billing.py, config.py, elevenlabs_transcribe.py, set_bot_commands.py, dashboard/server.py, dashboard/build.py, .env.example.
