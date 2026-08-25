import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useSnag, type Stage } from "@/lib/snag-store";
import { ItemRow } from "@/components/snag/item-row";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/library")({
  head: () => ({
    meta: [
      { title: "Library — Snag" },
      {
        name: "description",
        content:
          "Every link you snagged, kept as a sourced note with tags, stage and saved date. Search and filter your saved captures.",
      },
      { property: "og:title", content: "Library — Snag" },
      {
        property: "og:description",
        content: "Search and filter every sourced note you saved in Snag.",
      },
    ],
  }),
  component: LibraryPage,
});

const filters: Array<"All" | Stage> = ["All", "Worth Acting On", "Reference", "Inbox"];

function LibraryPage() {
  const { items } = useSnag();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"All" | Stage>("All");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((item) => {
      const stageOk = filter === "All" || item.stage === filter;
      const queryOk =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.tags.some((t) => t.includes(q)) ||
        item.sourceType.toLowerCase().includes(q);
      return stageOk && queryOk;
    });
  }, [items, query, filter]);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold md:text-3xl">Library</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Everything you snagged, with its source kept intact.
        </p>
      </header>

      <div className="space-y-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search titles, tags, source"
          className="w-full rounded-[4px] border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-accent/60"
        />
        <div className="flex flex-wrap gap-1.5">
          {filters.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-[3px] border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.1em] transition-colors",
                filter === f
                  ? "border-accent/50 bg-accent/10 text-accent"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {results.length === 0 ? (
        <div className="rounded-md border border-dashed border-border px-5 py-14 text-center">
          <p className="text-sm text-muted-foreground">No saved items match that.</p>
        </div>
      ) : (
        <div className="border-t border-border">
          {results.map((item) => (
            <ItemRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
