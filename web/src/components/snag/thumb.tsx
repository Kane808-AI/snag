import type { SnagItem } from "@/lib/snag-store";

type Props = {
  item: SnagItem;
  className?: string;
  /** Show the small source caption under the block. */
  caption?: boolean;
};

const isVideo = (t: string) => ["TikTok", "YouTube", "Podcast"].includes(t);

/** Source-type block, rendered in place of a thumbnail. Snag stores no images. */
export function Thumb({ item, className = "", caption = false }: Props) {
  const video = isVideo(item.sourceType);
  return (
    <figure className={className}>
      <div className="relative flex aspect-[16/10] w-full items-center justify-center overflow-hidden rounded-md border border-border bg-secondary">
        <div className="flex flex-col items-center gap-1.5">
          {video ? (
            <span className="block h-0 w-0 border-y-[6px] border-l-[10px] border-y-transparent border-l-accent" />
          ) : (
            <span className="h-2 w-2 rounded-full bg-accent" />
          )}
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-secondary-foreground/80">
            {item.sourceType}
          </span>
        </div>
      </div>
      {caption ? (
        <figcaption className="mt-2 text-[11px] text-muted-foreground/70">
          {item.contentType || item.sourceType}
        </figcaption>
      ) : null}
    </figure>
  );
}
