import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useSnag } from "@/lib/snag-store";
import { MetricBadge, SourceLine, StageBadge } from "@/components/snag/badges";
import { ActionBlock } from "@/components/snag/action-block";
import { NoteBody } from "@/components/snag/note-body";
import { GhostButton, PrimaryButton } from "@/components/snag/ui-bits";
import { Thumb } from "@/components/snag/thumb";


export const Route = createFileRoute("/item/$id")({
  head: () => ({
    meta: [
      { title: "Saved note — Snag" },
      {
        name: "description",
        content:
          "A sourced Snag note: summary, key ideas, why it matters, and the one recommended next action.",
      },
      { property: "og:title", content: "Saved note — Snag" },
      {
        property: "og:description",
        content: "Summary, key ideas, why it matters, and one recommended next action.",
      },
    ],
  }),
  component: ItemDetail,
});

function ItemDetail() {
  const { id } = Route.useParams();
  const { getItem, markDone } = useSnag();
  const navigate = useNavigate();
  const item = getItem(id);

  if (!item) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold">Item not found</h1>
        <p className="text-sm text-muted-foreground">
          This capture is no longer in your library.
        </p>
        <Link to="/library" className="text-sm text-accent underline underline-offset-4">
          Back to Library
        </Link>
      </div>
    );
  }

  return (
    <article className="space-y-8">
      <Link
        to="/library"
        className="text-xs text-muted-foreground underline decoration-border underline-offset-4 hover:text-foreground"
      >
        ← Library
      </Link>

      <div className="sticky top-0 z-10 -mx-1 space-y-3 border-b border-border bg-background/95 px-1 py-4 backdrop-blur">
        <SourceLine
          sourceType={item.sourceType}
          sourceUrl={item.sourceUrl}
          contentType={item.contentType}
        />
        <h1 className="text-2xl font-semibold leading-tight md:text-[2rem]">{item.title}</h1>
        <div className="flex flex-wrap gap-1.5">
          <StageBadge stage={item.stage} />
          <MetricBadge label="Impact" value={item.impact} />
          <MetricBadge label="Effort" value={item.effort} />
          <span className="ml-auto self-center text-[11px] tabular-nums text-muted-foreground/70">
            Saved {item.savedAt}
          </span>
        </div>
      </div>

      <Thumb item={item} caption className="max-w-lg" />

      <ActionBlock

        prominent
        action={item.action}
        actionType={item.actionType}
        impact={item.impact}
        effort={item.effort}
      >
        {item.done ? (
          <GhostButton onClick={() => markDone(item.id, false)}>Undo</GhostButton>
        ) : (
          <PrimaryButton onClick={() => markDone(item.id)}>Mark done</PrimaryButton>
        )}
        <GhostButton onClick={() => navigate({ to: "/actions" })}>Back to queue</GhostButton>
      </ActionBlock>

      <NoteBody item={item} />

      <footer className="flex flex-wrap gap-x-3 border-t border-border pt-5 text-[11px] text-muted-foreground/70">
        {item.tags.map((tag) => (
          <span key={tag}>#{tag}</span>
        ))}
      </footer>
    </article>
  );
}
