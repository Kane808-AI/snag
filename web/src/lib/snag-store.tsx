import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Stage = "Worth Acting On" | "Reference" | "Inbox";
export type SourceType = "TikTok" | "YouTube" | "Web" | "X" | "Newsletter" | "Podcast";

export type SnagItem = {
  id: string;
  title: string;
  sourceType: SourceType;
  sourceUrl: string;
  contentType: string;
  stage: Stage;
  impact: number;
  effort: number;
  summary: string;
  keyIdeas: string[];
  whyItWorked: string;
  whyItMatters: string;
  reusablePattern: string;
  action: string;
  actionType: string;
  tags: string[];
  thumb: string; // empty: the UI renders a source-type block instead of an image
  thumbAlt: string;
  savedAt: string;
  done?: boolean;
};

// The API lives on the Python server (port 8476). The frontend is a separate
// process (port 8080), so it always fetches the API cross-origin over localhost
// (server.py sends Access-Control-Allow-Origin: *).
const API_BASE = "http://localhost:8476";

export function sourceTypeFromUrl(url: string): SourceType {
  const u = (url || "").toLowerCase();
  if (u.includes("tiktok")) return "TikTok";
  if (u.includes("youtu")) return "YouTube";
  if (u.includes("x.com") || u.includes("twitter")) return "X";
  if (u.includes("substack") || u.includes("newsletter") || u.includes("buttondown")) return "Newsletter";
  if (u.includes("spotify") || u.includes("podcast") || u.includes("anchor.fm")) return "Podcast";
  return "Web";
}

function stripBullet(s: string): string {
  return s
    .replace(/^\s*[-*•]\s*/, "")
    .replace(/^\s*\d+[.)]\s*/, "")
    .trim();
}

function firstSentence(text: string): string {
  const t = (text || "").trim();
  const m = t.match(/^[^.!?\n]+[.!?]/);
  if (m) return m[0].trim();
  return t.slice(0, 90) || "(untitled)";
}

function mapItem(r: Record<string, unknown>): SnagItem {
  const keyIdeas = String(r.key_ideas ?? "")
    .split("\n")
    .map(stripBullet)
    .filter(Boolean);
  const recs = String(r.recommendations ?? "")
    .split("\n")
    .map(stripBullet)
    .filter(Boolean);
  const summary = String(r.summary ?? "").trim();
  return {
    id: String(r.id),
    title: firstSentence(summary),
    sourceType: sourceTypeFromUrl(String(r.source_url ?? "")),
    sourceUrl: String(r.source_url ?? ""),
    contentType: String(r.content_type ?? ""),
    stage: (r.stage as Stage) || "Inbox",
    impact: Number(r.impact ?? 3),
    effort: Number(r.effort ?? 3),
    summary,
    keyIdeas,
    whyItWorked: String(r.why_it_worked ?? ""),
    whyItMatters: String(r.why_it_matters ?? ""),
    reusablePattern: String(r.reusable_pattern ?? ""),
    action: recs[0] ?? "",
    actionType: String(r.action_type ?? "Just reference"),
    tags: String(r.tags ?? "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean),
    thumb: "",
    thumbAlt: "",
    savedAt: r.ts ? new Date(Number(r.ts) * 1000).toISOString().slice(0, 10) : "",
    done: String(r.status ?? "").toLowerCase() === "done",
  };
}

type SnagContextValue = {
  items: SnagItem[];
  captures: SnagItem[];
  actionQueue: SnagItem[];
  captureCount: number;
  saveItem: (item: SnagItem) => void;
  markDone: (id: string, done?: boolean) => Promise<void>;
  getItem: (id: string) => SnagItem | undefined;
};

const SnagContext = createContext<SnagContextValue | null>(null);

export function SnagProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<SnagItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/items`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled) setItems((d.items ?? []).map(mapItem));
      })
      .catch(() => {
        /* API unavailable: leave the list empty rather than crash */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const saveItem = useCallback((item: SnagItem) => {
    setItems((prev) => [item, ...prev]);
  }, []);

  const markDone = useCallback(async (id: string, done = true) => {
    // Optimistic update, then persist. On failure, roll the flag back.
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, done } : i)));
    try {
      await fetch(`${API_BASE}/api/items/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: done ? "done" : "inbox" }),
      });
    } catch {
      setItems((prev) => prev.map((i) => (i.id === id ? { ...i, done: !done } : i)));
    }
  }, []);

  const value = useMemo<SnagContextValue>(() => {
    const actionQueue = items
      .filter((i) => i.stage === "Worth Acting On" && !i.done)
      .sort((a, b) => b.impact / b.effort - a.impact / a.effort);
    return {
      items,
      captures: items.slice(0, 6),
      actionQueue,
      captureCount: items.length,
      saveItem,
      markDone,
      getItem: (id: string) => items.find((i) => i.id === id),
    };
  }, [items, saveItem, markDone]);

  return <SnagContext.Provider value={value}>{children}</SnagContext.Provider>;
}

export function useSnag() {
  const ctx = useContext(SnagContext);
  if (!ctx) throw new Error("useSnag must be used inside SnagProvider");
  return ctx;
}
