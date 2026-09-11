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
export type Engagement = {
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  save_count?: number;
  repost_count?: number;
};

export type SnagItem = {
  id: string;
  title: string;
  sourceType: SourceType;
  sourceUrl: string;
  contentType: string;
  stage: Stage;
  impact: number;
  effort: number;
  engagement: Engagement;
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

function parseEngagement(raw: unknown): Engagement {
  if (typeof raw === "string" && raw.trim()) {
    try {
      return (JSON.parse(raw) as Engagement) || {};
    } catch {
      return {};
    }
  }
  if (raw && typeof raw === "object") return raw as Engagement;
  return {};
}

function fmtCount(n?: number): string {
  if (!n) return "0";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function engagementLine(eng: Engagement): string {
  const parts: string[] = [];
  const map: [keyof Engagement, string][] = [
    ["view_count", "views"],
    ["like_count", "likes"],
    ["comment_count", "comments"],
    ["save_count", "saves"],
    ["repost_count", "reposts"],
  ];
  for (const [k, label] of map) {
    const v = eng[k];
    if (v) parts.push(`${fmtCount(v)} ${label}`);
  }
  return parts.join(", ");
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
    engagement: parseEngagement(r.engagement),
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

export type CapturePreview = {
  note: Record<string, unknown>;
  triage: {
    stage: Stage;
    action_type: string;
    impact: number;
    effort: number;
  };
  transcript: string;
  content_type: string;
  url: string;
};

export type CaptureResponse = {
  ok: boolean;
  preview?: CapturePreview;
  kind?: string;
  error?: string;
  duration?: number;
};

// The capture endpoint returns a preview shaped like a raw vault row plus a
// triage block. Fold it through the same mapper so the preview renders with the
// exact same NoteBody / badges as a saved item.
export function previewToItem(p: CapturePreview): SnagItem {
  const note = p.note ?? {};
  const rawTags = note["tags"];
  const tags = Array.isArray(rawTags)
    ? (rawTags as string[]).join(",")
    : String(rawTags ?? "");
  return mapItem({
    ...note,
    tags,
    source_url: p.url,
    content_type: p.content_type,
    stage: p.triage.stage,
    action_type: p.triage.action_type,
    impact: p.triage.impact,
    effort: p.triage.effort,
    id: "preview",
    ts: Math.floor(Date.now() / 1000),
    status: "inbox",
  });
}

export function buildActionQueue(items: SnagItem[]): SnagItem[] {
  return items
    .filter((item) => item.stage === "Worth Acting On" && !item.done)
    .map((item, index) => ({ item, index }))
    .sort(
      (a, b) =>
        b.item.impact / b.item.effort - a.item.impact / a.item.effort ||
        a.index - b.index,
    )
    .map(({ item }) => item);
}

type SnagContextValue = {
  items: SnagItem[];
  captures: SnagItem[];
  actionQueue: SnagItem[];
  captureCount: number;
  saveItem: (item: SnagItem) => void;
  markDone: (id: string, done?: boolean) => Promise<void>;
  getItem: (id: string) => SnagItem | undefined;
  captureUrl: (url: string) => Promise<CaptureResponse>;
  saveCapture: (preview: CapturePreview) => Promise<string | null>;
};

const SnagContext = createContext<SnagContextValue | null>(null);

export function SnagProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<SnagItem[]>([]);

  const refresh = useCallback(async () => {
    try {
      const d = await (await fetch(`${API_BASE}/api/items`)).json();
      setItems((d.items ?? []).map(mapItem));
    } catch {
      /* API unavailable: leave the list as-is rather than crash */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

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

  const captureUrl = useCallback(async (url: string): Promise<CaptureResponse> => {
    const r = await fetch(`${API_BASE}/api/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    return r.json();
  }, []);

  const saveCapture = useCallback(async (preview: CapturePreview): Promise<string | null> => {
    const r = await fetch(`${API_BASE}/api/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: preview.url,
        note: preview.note,
        triage: preview.triage,
        transcript: preview.transcript,
        content_type: preview.content_type,
      }),
    });
    const d = (await r.json()) as { ok?: boolean; id?: string };
    if (d.ok && d.id) {
      await refresh();
      return d.id;
    }
    return null;
  }, [refresh]);

  const value = useMemo<SnagContextValue>(() => {
    const actionQueue = buildActionQueue(items);
    return {
      items,
      captures: items.slice(0, 6),
      actionQueue,
      captureCount: items.length,
      saveItem,
      markDone,
      getItem: (id: string) => items.find((i) => i.id === id),
      captureUrl,
      saveCapture,
    };
  }, [items, saveItem, markDone, captureUrl, saveCapture]);

  return <SnagContext.Provider value={value}>{children}</SnagContext.Provider>;
}

export function useSnag() {
  const ctx = useContext(SnagContext);
  if (!ctx) throw new Error("useSnag must be used inside SnagProvider");
  return ctx;
}
