import { Link } from "@tanstack/react-router";
import type { SnagItem } from "@/lib/snag-store";
import { StageBadge } from "./badges";
import { Thumb } from "./thumb";

export function ItemRow({ item }: { item: SnagItem }) {
  return (
    <Link
      to="/item/$id"
      params={{ id: item.id }}
      className="flex gap-4 border-b border-border px-1 py-4 transition-colors hover:bg-surface/60"
    >
      <Thumb item={item} className="w-24 shrink-0 sm:w-32" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {item.sourceType}
          </span>
          <StageBadge stage={item.stage} />
          <span className="ml-auto text-[11px] tabular-nums text-muted-foreground/70">
            {item.savedAt}
          </span>
        </div>
        <h3 className="mt-1.5 text-[15px] font-medium leading-snug text-foreground">
          {item.title}
        </h3>
        <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{item.action}</p>
        <div className="mt-2 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground/70">
          {item.tags.map((tag) => (
            <span key={tag}>#{tag}</span>
          ))}
        </div>
      </div>
    </Link>
  );
}
