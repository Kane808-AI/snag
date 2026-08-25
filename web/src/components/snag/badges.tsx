import type { Stage } from "@/lib/snag-store";
import { cn } from "@/lib/utils";

export function Badge({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[3px] border border-border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StageBadge({ stage }: { stage: Stage }) {
  return (
    <Badge
      className={cn(
        stage === "Worth Acting On" &&
          "border-accent/40 bg-accent/10 text-accent",
        stage === "Reference" && "text-foreground/70",
      )}
    >
      {stage}
    </Badge>
  );
}

export function MetricBadge({ label, value }: { label: string; value: number }) {
  return (
    <Badge>
      {label}
      <span className="text-foreground">{value}</span>
    </Badge>
  );
}

export function SourceLine({
  sourceType,
  sourceUrl,
  contentType,
}: {
  sourceType: string;
  sourceUrl: string;
  contentType: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <span className="font-medium uppercase tracking-[0.14em] text-foreground/80">
        {sourceType}
      </span>
      <span aria-hidden className="text-border">
        /
      </span>
      <span>{contentType}</span>
      <span aria-hidden className="text-border">
        /
      </span>
      <a
        href={sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="max-w-full truncate underline decoration-border underline-offset-4 hover:text-accent"
      >
        {sourceUrl.replace(/^https?:\/\//, "")}
      </a>
    </div>
  );
}
