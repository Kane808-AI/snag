import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useSnag } from "@/lib/snag-store";

const navItems = [
  { to: "/", label: "Inbox" },
  { to: "/actions", label: "Actions" },
  { to: "/library", label: "Library" },
] as const;

function Wordmark() {
  return (
    <Link to="/" className="flex items-baseline gap-1.5">
      <span className="font-display text-lg font-semibold tracking-tight text-foreground">
        Snag
      </span>
      <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { actionQueue, items } = useSnag();
  const counts: Record<string, number> = {
    "/": items.length,
    "/actions": actionQueue.length,
    "/library": items.length,
  };

  return (
    <div className="min-h-screen md:flex">
      <header className="flex items-center justify-between border-b border-border bg-sidebar px-4 py-3 md:hidden">
        <Wordmark />
        <nav className="flex items-center gap-1">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              activeOptions={{ exact: item.to === "/" }}
              className="rounded-[4px] px-2.5 py-1.5 text-sm text-muted-foreground transition-colors data-[status=active]:bg-secondary data-[status=active]:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </header>

      <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-sidebar px-5 py-6 md:sticky md:top-0 md:flex md:h-screen">
        <Wordmark />
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          Save anything. Get the next action back.
        </p>
        <nav className="mt-8 flex flex-col gap-0.5">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              activeOptions={{ exact: item.to === "/" }}
              className="group flex items-center justify-between rounded-[4px] px-2.5 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-secondary data-[status=active]:text-foreground"
            >
              <span className="flex items-center gap-2.5">
                <span className="h-3.5 w-0.5 rounded-full bg-transparent group-data-[status=active]:bg-accent" />
                {item.label}
              </span>
              <span className="text-[11px] tabular-nums text-muted-foreground/70">
                {counts[item.to]}
              </span>
            </Link>
          ))}
        </nav>
        <div className="mt-auto border-t border-border pt-4 text-[11px] leading-relaxed text-muted-foreground/70">
          Local · your Snag vault
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-3xl px-5 py-8 md:px-10 md:py-12">{children}</div>
      </main>
    </div>
  );
}
