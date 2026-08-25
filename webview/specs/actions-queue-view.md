# Snag Webview — Actions Queue View (Spec)

Approved spec for the first real build through the builder→qa loop.
Product owner: Atlas. Implementer: builder agent. Verifier: qa agent.

## Goal

Add an "Actions" view to the read-only web viewer. It ranks your
"Worth Acting On" saves by priority (impact over effort) so the first thing
you see is what to do next. This is Snag's differentiator: no competitor
computes a prioritized next action.

## Scope (hard boundaries)

- Frontend only. Edit `webview/index.html`. Do NOT touch `server.py`,
  `api.py`, `db.py`, or any backend file. No new API endpoint is needed.
- Read-only. No write path, no "mark done" buttons, no persistence changes.
- stdlib/vanilla only. No new dependencies, no build step, no frameworks,
  no external fonts or CDNs.
- This is a single-file dark-theme app. Match the existing design tokens
  (the `:root` CSS variables in `index.html`) exactly. Do not invent colors.

## Data model (already available, do not change)

`GET /api/items?q=&stage=` returns `{"items": [...]}`. Each item has:
`id`, `summary`, `key_ideas`, `why_it_matters`, `recommendations`, `tags`,
`stage`, `action_type`, `impact`, `effort`, `status`, `source_url`,
`content_type`, `transcript`, `ts`.

- `impact` and `effort` are 1-5, returned as strings. Parse with `parseInt`.
- `stage` values: `"Worth Acting On"`, `"Reference"`, `"Inbox"`.
- `ts` is a unix epoch seconds.

## Behavior

1. Add a new chip labeled "Actions" to the filter nav (`#stageChips`).
   - Render it at the END of the chip row, visually separated from the
     stage chips by a subtle vertical divider (use `--border-subtle`).
   - It is a mode toggle, not a stage filter. When "Actions" is active it
     is the only active chip; all stage chips render inactive.

2. When "Actions" is active:
   - Load items matching the current search `q` AND `stage == "Worth Acting On"`.
     Reuse the existing `/api/items?q=<q>&stage=Worth%20Acting%20On` request.
   - Sort the returned items by priority, highest first:
     1. `impact / effort` ratio descending.
     2. Tie-break: higher `impact` first.
     3. Tie-break: higher `ts` (most recent) first.
   - Render each item as a list row with, in this order:
     a. A rank number ("#1", "#2", ...) as a small muted left-aligned label
        (tabular numerals, `--muted` color). This is the priority rank.
     b. The existing item content (summary, stage/status/action badges, tags)
        exactly as the normal list renders it today.
     c. BOTH impact and effort dots side by side, reusing the existing
        `.dots` / `.scale` markup, labeled "Impact" and "Effort" (impact dots
        use the accent color, effort dots the slate color — already in the
        CSS via `.dots-effort`).
   - The list header/count (`#listCount` / list title) must reflect the
     ranked count, e.g. "3 worth acting on".

3. Interaction rules:
   - Clicking an item still opens the detail view exactly as today.
   - Typing in search still filters (within Actions mode: search + stage).
   - Clicking any stage chip ("All", "Worth Acting On", "Reference",
     "Inbox") exits Actions mode and behaves exactly as today.
   - Clicking "Actions" from any state enters Actions mode.

4. Empty state:
   - If no "Worth Acting On" items exist (or none match the search), show the
     existing empty-state pattern with the title "Nothing worth acting on yet"
     and the sub-line "Save a link in Telegram and Snag will rank what matters
     next." Do not invent new empty-state styling; reuse the `.empty` pattern.

5. State management:
   - Add a boolean to the existing `state` object (e.g. `state.actions`).
   - `renderChips()` must render the Actions chip and mark it active when
     `state.actions` is true.
   - `loadItems()` must respect `state.actions` (apply the stage filter and
     client-side sort described above).
   - "Actions" mode is a view, not persisted. No URL hash, no localStorage.

## Visual direction (do not improvise beyond this)

- Reuse existing classes: `.chip`, `.item`, `.item-main`, `.item-summary`,
  `.item-meta`, `.badge`, `.tags`, `.tag`, `.scale`, `.dots`, `.dot`,
  `.empty`. If a new element is needed, style it from the existing tokens.
- Rank number: `font-variant-numeric: tabular-nums`, `font-size: 11px`,
  `color: var(--muted)`, `font-weight: 700`, fixed min-width so `#1` and
  `#10` align. Place it as the first child of `.item-main` or a new
  `.item-rank` element.
- The Actions chip divider: a `1px` vertical rule, `height: 16px`,
  `background: var(--border-subtle)`, with matching gap.
- No new font, no new color outside the existing `:root` tokens.

## Copy rules (hard)

- No em dashes, no semicolons, no filler, no corporate words (leverage,
  streamline, synergy, navigate, transformative).
- Direct, plain voice. Sentence case for empty-state text.

## Acceptance criteria (builder must verify before reporting)

1. `pytest` still green: run `/opt/homebrew/bin/python3 -m pytest` in
   `~/.hermes/workspace/snag/` (the existing 77 tests).
2. The page loads with no console errors. (You are vision-blind; a JS parse
   error that breaks the script is exactly what QA will catch, so run your
   own read-back of the script block and confirm it parses.)
3. "Actions" chip renders, toggles the ranked view, and sorting is correct
   for the live data at `http://localhost:8476` (2 items today, both
   "Worth Acting On").
4. Search, stage chips, and item→detail navigation all still work.

## Definition of done

The builder returns the 5-field report (files changed / commands run /
outputs produced / unresolved risks / verification steps) with captured
output. A qa PASS is a separate, later gate. A builder report without
captured verification output is a fail.
