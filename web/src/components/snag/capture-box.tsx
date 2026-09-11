import { useState } from "react";
import {
  useSnag,
  previewToItem,
  type CapturePreview,
  type CaptureResponse,
} from "@/lib/snag-store";
import { NoteBody } from "./note-body";
import { SourceLine, StageBadge, MetricBadge } from "./badges";
import { GhostButton, PrimaryButton } from "./ui-bits";

function friendlyError(res: CaptureResponse): string {
  switch (res.kind) {
    case "loginwall":
      return `${res.error || "That site"} blocks auto-reading. Paste the text here instead, or try a different link.`;
    case "ingest":
      return "I couldn't capture that video. It may be private, deleted, or region-locked.";
    case "fetch":
      return "I couldn't read that page. Some sites block reading; try a different link.";
    case "duration":
      return `That video runs longer than the free plan allows (${res.duration ?? 0}s).`;
    case "social":
      return res.error || "I couldn't capture that.";
    default:
      return res.error || "I couldn't capture that.";
  }
}

export function CaptureBox() {
  const { captureUrl, saveCapture } = useSnag();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<CapturePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function onCapture(e: React.FormEvent) {
    e.preventDefault();
    const u = url.trim();
    if (!u || busy) return;
    setBusy(true);
    setError(null);
    setPreview(null);
    setSaved(false);
    try {
      const res = await captureUrl(u);
      if (res.ok && res.preview) setPreview(res.preview);
      else setError(friendlyError(res));
    } catch {
      setError("Couldn't reach the Snag service.");
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!preview || busy) return;
    setBusy(true);
    setError(null);
    const id = await saveCapture(preview);
    setBusy(false);
    if (id) {
      setSaved(true);
      setPreview(null);
      setUrl("");
    } else {
      setError("Save failed, try again.");
    }
  }

  const item = preview ? previewToItem(preview) : null;

  return (
    <div className="rounded-[22px] border border-border bg-surface p-4 shadow-[0_1px_1px_rgba(30,45,41,0.03)] md:p-5">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Save from anywhere</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Use your iPhone share sheet, or paste a link here.</p>
        </div>
        <span className="rounded-full bg-secondary px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-accent">Capture</span>
      </div>
      <form onSubmit={onCapture} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a link — TikTok, YouTube, an article, a post…"
          className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-accent"
          aria-label="Link to capture"
        />
        <PrimaryButton type="submit" disabled={busy || !url.trim()}>
          {busy ? "Capturing…" : "Capture"}
        </PrimaryButton>
      </form>

      {error && (
        <p className="text-sm text-muted-foreground" role="alert">
          {error}
        </p>
      )}

      {saved && <p className="text-sm text-foreground/80">Saved to your vault.</p>}

      {item && (
        <div className="mt-5 rounded-2xl border border-border bg-background p-5 md:p-6">
          <div className="space-y-3 border-b border-border pb-4">
            <SourceLine
              sourceType={item.sourceType}
              sourceUrl={item.sourceUrl}
              contentType={item.contentType}
            />
            <h2 className="text-lg font-semibold leading-tight">{item.title}</h2>
            <div className="flex flex-wrap gap-1.5">
              <StageBadge stage={item.stage} />
              <MetricBadge label="Impact" value={item.impact} />
              <MetricBadge label="Effort" value={item.effort} />
            </div>
          </div>
          <div className="pt-5">
            <NoteBody item={item} />
          </div>
          <div className="mt-6 flex gap-2 border-t border-border pt-4">
            <PrimaryButton onClick={onSave} disabled={busy}>
              {busy ? "Saving…" : "Save to vault"}
            </PrimaryButton>
            <GhostButton onClick={() => setPreview(null)} disabled={busy}>
              Discard
            </GhostButton>
          </div>
        </div>
      )}
    </div>
  );
}
