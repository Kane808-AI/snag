import { createFileRoute } from "@tanstack/react-router";
import { useSnag } from "@/lib/snag-store";
import { ItemRow } from "@/components/snag/item-row";
import { CaptureBox } from "@/components/snag/capture-box";

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
  const { captures } = useSnag();

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-semibold md:text-3xl">Inbox</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Every save becomes a sourced note and a clear next step.
        </p>
      </header>

      <div className="rounded-md border border-border bg-surface p-5 md:p-6">
        <p className="text-sm leading-relaxed text-muted-foreground">
          Paste a link to turn it into a sourced note with one recommended next
          action, then save it to your vault. The Telegram bot captures the same
          way, so both surfaces stay in sync.
        </p>
      </div>

      <CaptureBox />

      <section>
        <div className="flex items-baseline justify-between border-b border-border pb-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            Recent captures
          </h2>
          <span className="text-[11px] tabular-nums text-muted-foreground/70">
            {captures.length}
          </span>
        </div>
        <div>
          {captures.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-5 py-14 text-center">
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
