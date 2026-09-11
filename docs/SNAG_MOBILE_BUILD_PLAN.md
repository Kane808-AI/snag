# Snag Mobile Build Plan

Status: active native iPhone build. The current objective is a calm, source-first
library that makes saved ideas easy to revisit and act on.

## Delivery rule

New ideas are triaged instead of automatically interrupting the build:

1. **Build now** only when it blocks the active user flow.
2. **Build next** when it is the next coherent slice of the product.
3. **Park for later** when it needs product decisions, backend work, or belongs
   after the core loop is complete.

## Quality baseline

Every screen ships with working touch scrolling, safe-area spacing, reachable
controls, clear loading/empty/error states, and the shared visual system. These
are default requirements, not separate feature detours. A baseline gap is fixed
within the active slice when it blocks use.

## Done

- Native Library, source filters, saved-item detail, search, Today queue, and
  Save flow.
- Item-level Ask Snag interface and local API wiring.
- Visual card library, source-aware metadata, and native navigation.
- Source access, a scrollable transcript reader, and item management for Done
  and Later.
- User-managed tags that safely merge with analysis tags.
- Snooze choices for Tomorrow or Next week, with Today advancing to the next
  available idea.
- Source previews in Library cards, saved-item detail, and transcript reader.
  New article, Instagram, and Facebook saves keep safe Open Graph images;
  YouTube saves keep their native thumbnail.
- Ask Snag starter prompts and a clear completion acknowledgement in Today.
- Paste-to-save persists the completed analysis, then refreshes Library when
  the user returns. Capture failures now explain the actual state instead of
  implying the phone is disconnected.
- Library-wide Ask Snag: a dedicated conversation tab that answers from a
  small, relevant set of saved ideas and lists the source cards used.
- Topic browsing: Library → More → Browse topics surfaces the tags already on
  saved ideas, then opens the matching search results without introducing
  folders or collections.
- Recoverable Trash: Manage an item → Move to Trash hides it from the Library,
  Today, search, and topics. Library → More → Trash restores it when needed.
- Shared text with a web link now follows the same capture path as a native
  URL share. Text without a link explains exactly what Snag needs.
- Ask Snag degrades honestly when its AI provider is unavailable: it labels a
  Quick library read and surfaces the most relevant saved recommendation with
  its source links.
- Item-level Ask uses the same honest fallback, labelled Quick item read and
  grounded in that item’s saved recommendation or key idea.
- A failed shared-link capture now names the AI-analysis outage without exposing
  provider details, offers one in-place retry, and keeps Paste to Save as a
  clear recovery route.
- AI outages no longer discard a capture: Snag saves extracted source text as
  an honest Inbox reference with no invented recommendations or tags. The
  native Safari Share Sheet handoff was verified in the iOS Simulator.
- The mobile save flow now correctly unwraps the API's `preview` response
  before posting a completed capture to the Library.
- Duplicate shared links are stopped at the save boundary. Snag says **Already
  saved**, opens the existing Library item, ignores harmless tracking-query and
  fragment differences, and permits intentional re-saves after an item is put
  in Trash.

## Next

- Device-level Share Sheet QA from Safari or another source app. Simulator
  handoff is verified; the next fresh shared link should be confirmed as a
  newly visible Library card after the save-response fix.
- Decide the next organizing primitive after the core loop: collections,
  richer tag browsing, or a lightweight weekly digest.

## Native build status

- An unsigned iOS Simulator development build now compiles, installs, and
  visually identifies its Share Sheet extension as **Snag**. It uses
  `com.kane808.snag`, the
  `group.com.kane808.snag` app group, and accepts text plus one web URL.
- The Simulator handoff route is verified with an isolated disposable payload:
  it reached Snag’s native share screen and safely rejected an invalid link.
- Physical-device Share Sheet testing remains separate because that requires
  Apple development signing. No Apple credentials were created or used for the
  Simulator build.

## Later

- Signed iOS Share Sheet capture for TikTok, YouTube, Safari, Instagram, and
  Facebook.
- Shareable text, collections, export, trash, digest, settings, and quota.
- Public Snag API for a user's own agents: scoped access tokens plus endpoints
  to save a source, list/search saved ideas, retrieve an item, and ask over the
  library. Build this after user identity and account isolation exist.
- Bring-your-own AI provider: let a user route enrichment to their own OpenAI
  or Anthropic API project. This reduces Snag's model cost but does not use a
  ChatGPT or Claude chat subscription; API billing stays with the provider
  account. Keys must be stored server-side with encryption, revocation, and
  per-user spend limits, never in the mobile app.
