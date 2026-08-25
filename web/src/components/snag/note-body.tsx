import type { SnagItem } from "@/lib/snag-store";
import { SectionTitle } from "./ui-bits";

export function NoteBody({ item }: { item: SnagItem }) {
  return (
    <div className="space-y-7">
      <section>
        <SectionTitle>Summary</SectionTitle>
        <p className="mt-2 text-[15px] leading-relaxed text-foreground/85">{item.summary}</p>
      </section>

      <section>
        <SectionTitle>Key ideas</SectionTitle>
        <ul className="mt-2 space-y-2">
          {item.keyIdeas.map((idea) => (
            <li key={idea} className="flex gap-3 text-[15px] leading-relaxed text-foreground/85">
              <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
              {idea}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>Why it matters</SectionTitle>
        <p className="mt-2 text-[15px] leading-relaxed text-foreground/85">{item.whyItMatters}</p>
      </section>
    </div>
  );
}
