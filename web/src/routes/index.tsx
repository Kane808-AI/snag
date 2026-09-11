import { createFileRoute } from "@tanstack/react-router";
import { useNavigate } from "@tanstack/react-router";
import { useSnag } from "@/lib/snag-store";
import { ItemRow } from "@/components/snag/item-row";
import { CaptureBox } from "@/components/snag/capture-box";
import { ArrowUpRight, Sparkles } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Inbox — Snag: save anything, get the next action back" },
      {
        name: "description",
        content:
          "Every link you snag becomes a sourced note with one clear next action. View your recent captures and the actions queue.",
      },
      { property: "og:title", content: "Snag — Save anything. Get the next action back." },
      {
        property: "og:description",
        content: "Capture-to-action for solo operators: a sourced note and one concrete next step.",
      },
    ],
  }),
  component: InboxPage,
});

function InboxPage() {
  const { captures, actionQueue } = useSnag();
  const navigate = useNavigate();
  const topAction = actionQueue[0];

  return (
    <div className="space-y-8 md:space-y-10">
      <header className="snag-enter">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">Your library</p>
        <h1 className="mt-2 text-3xl font-semibold leading-[1.05] md:text-5xl">Ideas worth keeping.</h1>
        <p className="mt-3 max-w-md text-sm leading-relaxed text-muted-foreground">
          Everything you share lands here, organized into one place.
        </p>
      </header>

      {topAction ? (
        <button
          onClick={() => navigate({ to: "/item/$id", params: { id: topAction.id } })}
          className="group relative w-full overflow-hidden rounded-[26px] bg-foreground p-5 text-left text-surface shadow-[0_16px_40px_rgba(29,45,40,0.16)] transition-transform hover:-translate-y-0.5 md:p-7"
        >
          <div className="absolute -right-12 -top-14 h-44 w-44 rounded-full bg-accent/30 blur-2xl" />
          <div className="relative flex items-start justify-between gap-5">
            <div>
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.15em] text-secondary">
                <Sparkles className="h-3.5 w-3.5" /> Act now
              </span>
              <p className="mt-4 max-w-xl font-display text-xl font-medium leading-snug md:text-2xl">{topAction.action}</p>
              <p className="mt-2 text-sm text-surface/60">From {topAction.sourceType} · {topAction.title}</p>
            </div>
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-surface/10 transition-colors group-hover:bg-surface/20"><ArrowUpRight className="h-5 w-5" /></span>
          </div>
        </button>
      ) : (
        <div className="rounded-[26px] bg-secondary p-5 md:p-7">
          <p className="font-display text-xl font-medium">Your next good idea is one share away.</p>
          <p className="mt-2 text-sm text-muted-foreground">Use the share sheet in any app to send something to Snag.</p>
        </div>
      )}

      <CaptureBox />

      <section>
        <div className="flex items-baseline justify-between px-1 pb-1">
          <h2 className="font-display text-xl font-medium">
            Saved recently
          </h2>
          <span className="text-xs text-muted-foreground">
            {captures.length} saved
          </span>
        </div>
        <div>
          {captures.length === 0 ? (
            <div className="rounded-[22px] border border-dashed border-border bg-surface px-5 py-14 text-center">
              <p className="text-sm text-muted-foreground">
                Nothing captured yet. Paste a link above, or send one to the bot, and it
                will show up here.
              </p>
            </div>
          ) : (
            captures.map((item) => <ItemRow key={item.id} item={item} />)
          )}
        </div>
      </section>
    </div>
  );
}
