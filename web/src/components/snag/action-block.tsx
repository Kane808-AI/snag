import { Badge } from "./badges";

export function ActionBlock({
  action,
  actionType,
  impact,
  effort,
  prominent = false,
  children,
}: {
  action: string;
  actionType: string;
  impact: number;
  effort: number;
  prominent?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <section
      className={
        prominent
          ? "rounded-md border-2 border-accent bg-secondary p-5 md:p-6"
          : "rounded-md border border-border bg-surface p-4"
      }
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-accent">
          Recommended next action
        </h3>
        <Badge>{actionType}</Badge>
      </div>
      <p
        className={
          prominent
            ? "mt-3 font-display text-xl leading-snug text-foreground md:text-2xl"
            : "mt-2 text-base leading-snug text-foreground"
        }
      >
        {action}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span>
          Impact <span className="text-foreground tabular-nums">{impact}</span>/5
        </span>
        <span>
          Effort <span className="text-foreground tabular-nums">{effort}</span>/5
        </span>
        <span>
          Priority{" "}
          <span className="text-highlight tabular-nums">{(impact / effort).toFixed(1)}</span>
        </span>
      </div>
      {children ? <div className="mt-5 flex flex-wrap gap-2">{children}</div> : null}
    </section>
  );
}
