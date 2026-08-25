# Snag Webview — Redesign Brief

You are redesigning the visual layer of a real product. Follow the claude-design
doctrine you were given (surface-first, anti-slop, slop diagnostic). Do not
improvise past this brief.

## What this app is

Snag is a "capture anything" app. A user saves a link in a Telegram bot; the bot
turns each save into an organized note (summary, key ideas, why it matters,
recommendations, tags) plus a triage (Stage: Worth Acting On / Reference / Inbox;
Impact 1-5; Effort 1-5). This web viewer is the browser surface over that vault.

## The surface (commit to this before any tokens)

This is a **Monitor / Operate** surface, not a marketing page. The user comes
here to see what they saved and decide what to do next. Density, glanceability,
clear hierarchy, and action affordances dominate. NO hero, NO feature-card grid,
NO centered marketing empty states, NO decorative stats.

The primary composition is already structurally correct (a list pane + a detail
pane + a ranked "Actions" mode). Your job is to make that composition look like
a product a real design team shipped, not to invent a new information structure.

## The file

`/Users/chriskaneshiro/.hermes/workspace/snag/webview/index.html` — a single
file, inline CSS + JS, roughly 700 lines. READ IT FULLY before changing anything.

## The API (do not change the wiring)

- `GET /api/items?q=&stage=` -> `{"items": [{id, summary, key_ideas,
  why_it_matters, recommendations, tags, stage, action_type, impact, effort,
  status, source_url, content_type, transcript, ts}, ...]}`
- `GET /api/items/<id>` -> one item object
- `GET /api/stats` -> `{total, by_stage, by_status}`
- `GET /api/tags` -> `{tags: [{tag, count}]}`

## Hard constraints (non-negotiable)

1. **Preserve every feature exactly.** List rendering, debounced search, the
   stage chips + the "Actions" chip (ranked Worth-Acting-On list sorted by
   impact/effort, with rank numbers and impact + effort dot scales), item to
   detail navigation, the Back button (label is context-aware: "Back to actions"
   in Actions mode, "Back to library" otherwise), responsive behavior (desktop
   two-pane, mobile single-pane), keyboard shortcuts (`/` to focus search, `Esc`
   to close), empty states. You may restyle or lightly restructure the markup,
   but every interaction and every piece of data shown must keep working
   identically. Do not touch the fetch calls, the state object, or the sort
   logic (`compareByPriority`).
2. **Single file, stdlib only.** No external fonts, no CDNs, no JS libraries,
   no build step. The result must still open directly in a browser.
3. **Dark theme is the default posture** (it is a focused-work tool). Refine the
   palette, type, and spacing if it genuinely improves the result, but keep it
   dark and keep one coherent token system.
4. **Copy rules:** no em dashes, no semicolons, no filler, no corporate words
   (leverage, streamline, synergy, navigate, transformative). Direct plain voice.
5. **Anti-slop:** avoid tech gradients, generic indigo, feature-tile grids,
   accent rails, glassmorphism, oversized rounded rectangles as hierarchy, and
   default-Inter-everything. Choose deliberately.

## Design directive

- Run the slop diagnostic on the CURRENT file and state the score (out of 10,
  10 = max slop) and which tells fired. Then design to a low score, and state
  the after score.
- Aim for the restraint and polish of a real product (Linear, Notion, Arc,
  Things, Raycast are good reference points for posture, not to clone).
- Use typography, spacing, and hierarchy to carry the design before boxes,
  icons, or color. Tabular numerals for numbers (impact/effort/ranks).
- Keep mobile hit targets at least 44px.

## Deliverable

Rewrite `/Users/chriskaneshiro/.hermes/workspace/snag/webview/index.html`.
Do not modify any other file.

## Verification (run before you report)

1. `/opt/homebrew/bin/python3 -m pytest` in `/Users/chriskaneshiro/.hermes/
   workspace/snag/` -> must stay 94 passed.
2. Extract the `<script>` block and run `node --check` on it -> must parse.
3. Load http://localhost:8476 and confirm zero console errors and that the list
   renders (2 items today).

## Report

Report concisely: what changed (composition, type, color, spacing), the slop
score before vs after, verification output, and any risk you left.
