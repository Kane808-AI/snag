import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useSnag } from "@/lib/snag-store";
import { Bookmark, CheckCircle2, Library, Sparkles } from "lucide-react";

const navItems = [
  { to: "/", label: "Library", icon: Library },
  { to: "/actions", label: "Act now", icon: Sparkles },
  { to: "/library", label: "All saves", icon: Bookmark },
] as const;

function Wordmark() {
  return <Link to="/" className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-[11px] bg-foreground text-surface shadow-sm">
        <span className="font-display text-base leading-none">S</span>
      </span>
      <span className="font-display text-[1.15rem] font-semibold tracking-tight text-foreground">Snag</span>
    </Link>
}

export function MobileNav() {
  return (
    <nav className="fixed inset-x-3 bottom-3 z-20 flex h-[68px] items-center justify-around rounded-[24px] border border-border/80 bg-surface/95 px-2 shadow-[0_12px_40px_rgba(30,45,41,0.15)] backdrop-blur md:hidden">
      {navItems.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          activeOptions={{ exact: item.to === "/" }}
          className="flex min-w-16 flex-col items-center gap-1 rounded-xl px-3 py-1.5 text-[10px] font-medium text-muted-foreground transition-colors data-[status=active]:text-foreground"
        >
          <item.icon className="h-[18px] w-[18px] stroke-[1.8]" />
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
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
    <div className="min-h-screen bg-background md:flex">
      <header className="sticky top-0 z-10 flex items-center justify-between bg-background/90 px-5 py-4 backdrop-blur md:hidden">
        <Wordmark />
        <span className="grid h-9 w-9 place-items-center rounded-full bg-secondary text-xs font-semibold text-accent">CK</span>
      </header>
      <MobileNav />

      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-sidebar px-6 py-7 md:sticky md:top-0 md:flex md:h-screen">
        <Wordmark />
        <p className="mt-4 max-w-40 text-xs leading-relaxed text-muted-foreground">
          Save what matters. Know what to do next.
        </p>
        <nav className="mt-8 flex flex-col gap-0.5">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              activeOptions={{ exact: item.to === "/" }}
              className="group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-surface data-[status=active]:text-foreground data-[status=active]:shadow-sm"
            >
              <span className="flex items-center gap-2.5">
                <item.icon className="h-4 w-4 stroke-[1.8]" />
                {item.label}
              </span>
              <span className="text-[11px] tabular-nums text-muted-foreground/70">
                {counts[item.to]}
              </span>
            </Link>
          ))}
        </nav>
        <div className="mt-auto rounded-2xl bg-secondary/70 p-3.5 text-[11px] leading-relaxed text-muted-foreground">
          <CheckCircle2 className="mb-2 h-4 w-4 text-accent" />
          Your ideas stay organized and ready to use.
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-4xl px-5 pb-28 pt-4 md:px-12 md:py-12">{children}</div>
      </main>
    </div>
  );
}
