# Snag — capture-to-action prototype

A clickable, local-only app prototype. Paste a link, watch a short processing state, get a sourced note with one recommended next action, then Save or Discard.

## Views

**Inbox (`/`)** — Snag wordmark, left nav (Inbox / Actions / Library), large capture field with placeholder "Paste a link to snag it", primary Capture button, the line "Every save becomes a sourced note and a clear next step.", and a Recent captures list below.

Capture flow: submit → ~1.6s processing state with staged status text → result card built from mock data, showing source URL + content type, Summary, Key ideas, Why it matters, Recommended next action, and compact Stage / Impact / Effort badges, with Save and Discard buttons. Save pushes the item into Library (and Actions if stage is Worth Acting On); Discard clears it.

**Actions (`/actions`)** — only items with stage "Worth Acting On", ranked by impact ÷ effort, with rank numbers, action type, impact and effort, plus Open and Done buttons. Done removes the item from the queue. Empty state: "Nothing worth acting on yet."

**Library (`/library`)** — clean list of saved items, mock search over title/tags, filter chips for All / Worth Acting On / Reference / Inbox, and per-row tags, source type, stage, saved date. Rows open the item detail.

**Item detail (`/item/$id`)** — the payoff view: source URL and type pinned at the top and always visible, then Summary, Key ideas, Why it matters, and a visually dominant Recommended action block in the coral accent with Mark done / Back to queue. Calm spacing, no decorative stats.

## Data

Four seeded items exactly as specified (TikTok hooks, solo founder research loop, competitor pricing page, weekly reporting automation) with their stage, impact, effort, and recommended actions. Plus a small pool of mock capture results the Capture flow draws from, keyed loosely off the pasted URL's domain.

State lives in a React context with `useState` — no backend, no persistence beyond the session.

## Visual direction

Dark charcoal surfaces, warm off-white text, single coral accent reserved for Snag actions (Capture, Recommended action, active nav). Restrained cards, hairline borders, strong spacing, compact uppercase badges. No gradients, no hero, no imagery, no dashboard widgets. Responsive: sidebar collapses to a top bar on mobile.

## Technical notes

- Routes: `src/routes/index.tsx` (replacing the placeholder), `actions.tsx`, `library.tsx`, `item.$id.tsx`; shared shell + nav rendered in `__root.tsx`.
- Store: `src/lib/snag-store.tsx` (context + seed data + derived selectors for the ranked queue).
- Components under `src/components/snag/`: `CaptureCard`, `ResultCard`, `ItemRow`, `Badges`, `ActionBlock`.
- Design tokens (charcoal background, off-white foreground, coral accent) added to `src/styles.css` as oklch semantic tokens; no hardcoded color classes in components.
- Per-route `head()` metadata with unique titles/descriptions.
