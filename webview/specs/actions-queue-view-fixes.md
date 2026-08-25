# Snag Webview — Actions Queue View Fixes (Spec)

Follow-up fix pass to the Actions queue view build. Two defects, both
frontend-only, both in `webview/index.html`. Do not touch any other file.

## Fix 1: active chip clipped on mobile (new defect from the Actions build)

On a 390px viewport the filter chip row uses `overflow-x: auto; flex-wrap:
nowrap`, and the new "Actions" chip (appended last) sits past the right edge,
so in Actions mode the user sees only "A...". The row scrolls but nothing
scrolls the active chip into view.

Requirement: when any chip becomes active (including Actions), it must be
scrolled into view horizontally so it is fully visible at rest. Implement in
`renderChips()` after the chips render and the active chip is marked: call
`scrollIntoView({ block: "nearest", inline: "nearest" })` on the active chip,
guarded to run after the DOM settles (wrap in `requestAnimationFrame`). Do not
change the single-row horizontal-scroll design and do not wrap the chips onto
multiple lines. Do not change the `.filters` CSS.

## Fix 2: impact dots render as vertical bars (pre-existing, now prominent)

In the list rows, `.item-impact` contains bare `.dot` spans that are
`display: inline`, so their `width`/`height` are ignored and each dot renders
as a 2px-wide vertical bar (the "barcode" artifact). The new Impact/Effort
scales render correctly because their dots sit inside a `.dots` container with
`display: inline-flex`.

Requirement: make the list-row impact dots render as circles, using the same
mechanism the scales already use. Wrap the `dots()` output inside
`.item-impact` in a `.dots` container (the existing `.dots` class already
provides `display: inline-flex; gap: 3px; align-items: center`). This must fix
BOTH the Library view and the Actions view since both share `renderList()`.
Do not remove the impact dots and do not change their color or count.

## Hard boundaries

- Frontend only. Edit `webview/index.html`. Do NOT touch `server.py`,
  `api.py`, `db.py`, or any other file.
- Match existing design tokens and classes. No new colors, no new deps.
- No em dashes, no semicolons, no filler, no corporate words.

## Acceptance (verify before reporting)

1. `/opt/homebrew/bin/python3 -m pytest` in `/Users/chriskaneshiro/.hermes/
   workspace/snag/` stays green (94 passing).
2. The `<script>` block still parses (node --check on the extracted block).
3. On a 390px viewport, entering Actions mode shows the full "Actions" chip
   (scrollIntoView worked). Verified via `browser_exec` DOM check: the active
   chip's `getBoundingClientRect()` is fully within the container's visible
   width.
4. The `.item-impact` dots render as circles: each `.dot` now has a
   `getBoundingClientRect()` of approximately equal width and height (about
   6px), not 2px x 20px. Verify in both the Library and Actions views.
5. No console errors on load.

Return the 5-field evidence-gated report (files changed / commands run /
outputs produced / unresolved risks / verification steps) with captured
output for every check.
