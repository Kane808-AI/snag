# Snag G3 Validation — Test Matrix

Status: **not started** (pre-validation). We are still building, not validating.

## What "ready for G3" means

G3 = the loop is proven end-to-end with real content before any public posting.
Passing is concrete, not a feeling. We pass when every row below is checked with a
real result and no manual restart was needed along the way.

## 1. Capture reliability

| URL type | Expected | Result |
|---|---|---|
| YouTube (has captions, any length) | note from native captions, ~1s | |
| YouTube (no captions) | graceful fallback message | |
| TikTok (public) | capture + local whisper transcript | |
| TikTok (private/deleted) | clean "couldn't capture" message | |
| TikTok (geo-blocked / status-10240) | clean failure, no crash | |
| Instagram reel / Facebook video | honest login-wall message | |
| Garbage URL / non-video | clean "not supported" | |

Pass bar: every row behaves as listed, zero unhandled exceptions in bot logs.

## 2. Transcription (local whisper-small)

| Case | Expected |
|---|---|
| TikTok with clear single voice | accurate transcript, reasonable time |
| TikTok with music/no speech | "no speech detected" or empty, no crash |
| Non-English voice | graceful (even if imperfect) |

Pass bar: 3+ real TikTok transcriptions reviewed, no IndexError-style crashes.

## 3. Analysis quality (content-aware + engagement)

Eyeball on 5+ varied captures (not just one creator/genre):

- WHY IT WORKED names a real hook/structure/trigger, not boilerplate
- REUSABLE PATTERN is a usable fill-in-the-blank template
- impact score tracks real engagement (high views/saves scores higher)
- tags are relevant, recommendations are actionable

Pass bar: Chris reviews and would actually act on 3 of the 5 notes.

## 4. Full loop (dogfood over days)

- capture -> note -> triage -> action queue -> mark done -> revisit, repeatedly
- write-back (PATCH) persists and survives reload
- no manual restart required across multiple days

## 5. Plumbing soak

- reboot Mac, confirm bot/api/web all come back via launchd
- DB migrations hold (why_it_worked, reusable_pattern, engagement columns present)
- no orphan processes or port conflicts on 8476 / 8080

## Pass bar (G3 = ready)

All of sections 1, 2, 4, 5 green. Section 3 at the review bar above.
Only then is public posting (G2) unlocked.
