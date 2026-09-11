import { Link } from "@tanstack/react-router";
import type { SnagItem } from "@/lib/snag-store";
import { StageBadge } from "./badges";
import { Thumb } from "./thumb";

export function ItemRow({ item }: { item: SnagItem }) {
  return (
    <Link
      to="/item/$id"
      params={{ id: item.id }}
      className="group flex gap-3 rounded-2xl bg-surface p-3 shadow-[0_1px_1px_rgba(30,45,41,0.03)] transition-all hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(30,45,41,0.08)] md:gap-4 md:p-4"
    >
      <Thumb item={item} className="w-20 shrink-0 sm:w-32" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {item.sourceType}
          </span>
          <StageBadge stage={item.stage} />
          <span className="ml-auto text-[10px] tabular-nums text-muted-foreground/70">
            {item.savedAt}
          </span>
        </div>
        <h3 className="mt-1.5 text-[15px] font-medium leading-snug text-foreground transition-colors group-hover:text-accent">
          {item.title}
        </h3>
        <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">{item.action}</p>
        <div className="mt-2 flex flex-wrap gap-x-3 text-[11px] text-muted-foreground/70">
          {item.tags.map((tag) => (
            <span key={tag}>#{tag}</span>
          ))}
        </div>
      </div>
    </Link>
  );
}
