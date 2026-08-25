import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useSnag } from "@/lib/snag-store";
import { Badge } from "@/components/snag/badges";
import { GhostButton, PrimaryButton } from "@/components/snag/ui-bits";
import { Thumb } from "@/components/snag/thumb";


export const Route = createFileRoute("/actions")({
  head: () => ({
    meta: [
      { title: "Actions — Snag" },
      {
        name: "description",
        content:
          "The Snag actions queue: saved items worth acting on, ranked by impact divided by effort, with one concrete next step each.",
      },
      { property: "og:title", content: "Actions queue — Snag" },
      {
        property: "og:description",
        content: "Items worth acting on, ranked by impact divided by effort.",
      },
    ],
  }),
  component: ActionsPage,
});

function ActionsPage() {
  const { actionQueue, markDone } = useSnag();
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold md:text-3xl">Actions</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Worth acting on, ranked by impact divided by effort.
        </p>
      </header>

      {actionQueue.length === 0 ? (
        <div className="rounded-md border border-dashed border-border px-5 py-14 text-center">
          <p className="text-sm text-muted-foreground">Nothing worth acting on yet.</p>
        </div>
      ) : (
        <ol className="divide-y divide-border border-y border-border">
          {actionQueue.map((item, i) => (
            <li key={item.id} className="flex gap-4 py-5 md:gap-6">
              <span className="mt-0.5 w-7 shrink-0 font-display text-2xl font-semibold tabular-nums text-accent">
                {i + 1}
              </span>
              <Thumb item={item} className="hidden w-28 shrink-0 sm:block" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">

                  <Badge className="border-accent/40 bg-accent/10 text-accent">
                    {item.actionType}
                  </Badge>
                  <Badge>{item.sourceType}</Badge>
                </div>
                <p className="mt-2 text-[15px] font-medium leading-snug text-foreground">
                  {item.action}
                </p>
                <p className="mt-1 line-clamp-1 text-xs text-muted-foreground">
                  From “{item.title}”
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                  <span>
                    Impact <span className="tabular-nums text-foreground">{item.impact}</span>/5
                  </span>
                  <span>
                    Effort <span className="tabular-nums text-foreground">{item.effort}</span>/5
                  </span>
                  <span>
                    Priority{" "}
                    <span className="tabular-nums text-highlight">
                      {(item.impact / item.effort).toFixed(1)}
                    </span>
                  </span>
                </div>
                <div className="mt-4 flex gap-2">
                  <PrimaryButton
                    onClick={() => navigate({ to: "/item/$id", params: { id: item.id } })}
                  >
                    Open
                  </PrimaryButton>
                  <GhostButton onClick={() => markDone(item.id)}>Done</GhostButton>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
