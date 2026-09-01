import { useCallback, useEffect, useMemo, useState } from 'react';
import { useFocusEffect } from 'expo-router';

export type SnagItem = { id: string; title: string; summary: string; sourceType: 'TikTok' | 'YouTube' | 'Web'; sourceUrl: string; thumbnailUrl?: string; transcript: string; stage: 'Worth Acting On' | 'Reference' | 'Inbox'; status: 'inbox' | 'in progress' | 'done' | 'archived'; snoozedUntil?: number; action: string; actionType: string; impact: number; effort: number; savedAt: string; keyIdeas: string[]; whyItMatters: string; recommendations: string[]; tags: string[]; done?: boolean };
type ItemUpdate = Partial<Pick<SnagItem, 'stage' | 'status'>> & { snooze_until?: number | null };
type TagUpdate = { add_tags?: string[]; remove_tags?: string[] };

const API_BASE = process.env.EXPO_PUBLIC_SNAG_API_URL ?? 'http://127.0.0.1:8476';
const LOCAL_API_HEADERS = { 'Content-Type': 'application/json', Origin: 'http://localhost:8081' };

export class SnagCaptureError extends Error {
  constructor(message: string, readonly kind = '') {
    super(message);
    this.name = 'SnagCaptureError';
  }
}
const sampleItems: SnagItem[] = [
  { id: 'sample-1', title: 'How a small product team uses customer language to make better landing pages.', summary: 'Save customer phrases before they get cleaned up. The wording is the signal.', sourceType: 'TikTok', sourceUrl: 'https://www.tiktok.com', transcript: 'The useful language is not the language you invent in a workshop. It is the language customers use when they explain the problem to each other. Save those phrases before they are polished away. The pattern you want is specific, emotional, and repeatable.', stage: 'Worth Acting On', status: 'inbox', action: 'Pull five phrases from recent conversations and test them in the Snag landing page.', actionType: 'Try this', impact: 5, effort: 2, savedAt: 'Today', keyIdeas: ['Raw customer language is more specific than a polished brand claim.', 'The most useful phrases show up in support and sales conversations.'], whyItMatters: 'Snag needs a message that makes people feel seen in the first few seconds.', recommendations: ['Pull five phrases from recent conversations.', 'Test one phrase in the Snag landing-page headline.'], tags: ['positioning', 'copywriting'] },
  { id: 'sample-2', title: 'A simpler way to turn saved content into a weekly idea list.', summary: 'A light review ritual keeps the library useful without becoming another inbox.', sourceType: 'YouTube', sourceUrl: 'https://www.youtube.com', transcript: 'A saved library only becomes valuable when you return to it. Keep the ritual small. Once a week, open the list, pick one thing worth moving forward, and leave the rest alone. The goal is not perfect organization. The goal is a better next decision.', stage: 'Worth Acting On', status: 'inbox', action: 'Block 20 minutes Friday to select the one saved idea worth acting on next week.', actionType: 'Make a ritual', impact: 4, effort: 2, savedAt: 'Yesterday', keyIdeas: ['The library needs a review habit, not more organization.', 'One good decision is more valuable than revisiting everything.'], whyItMatters: 'This is the behavior Snag should make effortless once people have a library.', recommendations: ['Block 20 minutes Friday for your weekly review.', 'Select one saved idea to act on next week.'], tags: ['habit', 'product'] },
  { id: 'sample-3', title: 'Why the best capture tools disappear until you need your ideas back.', summary: 'Fast capture works only when retrieval feels calm and obvious.', sourceType: 'Web', sourceUrl: 'https://example.com', transcript: 'Capture should take one move from the app where the idea appeared. Retrieval should be quiet. When someone opens the library, they should see useful material and a clear next action, not a system to maintain.', stage: 'Reference', status: 'inbox', action: '', actionType: 'Just reference', impact: 3, effort: 1, savedAt: 'Aug 29', keyIdeas: ['Capture needs to disappear into the operating system.', 'Retrieval should feel lighter than a folder tree.'], whyItMatters: 'The mobile UI needs to get out of the way while making saved material easy to reopen.', recommendations: [], tags: ['ux', 'research'] },
];

function sourceTypeFromUrl(url: string): SnagItem['sourceType'] { const value = url.toLowerCase(); return value.includes('tiktok') ? 'TikTok' : value.includes('youtu') ? 'YouTube' : 'Web'; }
function youtubeThumbnail(url: string): string | undefined { try { const parsed = new URL(url); const id = parsed.hostname.includes('youtu.be') ? parsed.pathname.slice(1) : parsed.searchParams.get('v'); return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : undefined; } catch { return undefined; } }
function firstSentence(value: unknown): string { const text = String(value ?? '').trim(); return text.split(/[.!?]\s/)[0] || 'Untitled save'; }
function mapItem(item: Record<string, unknown>): SnagItem {
  const recommendations = String(item.recommendations ?? '').split('\n').map((value) => value.replace(/^[-*•]\s*/, '').trim()).filter(Boolean);
  const keyIdeas = String(item.key_ideas ?? '').split('\n').map((value) => value.replace(/^[-*•]\s*/, '').trim()).filter(Boolean);
  const tags = String(item.tags ?? '').split(/[,\n]/).map((value) => value.trim().replace(/^#/, '')).filter(Boolean);
  const status = item.status === 'in progress' || item.status === 'done' || item.status === 'archived' ? item.status : 'inbox';
  const snoozedUntil = Number(item.snooze_until ?? 0) || undefined;
  const sourceUrl = String(item.source_url ?? '');
  return { id: String(item.id), title: firstSentence(item.summary), summary: String(item.summary ?? ''), sourceType: sourceTypeFromUrl(sourceUrl), sourceUrl, thumbnailUrl: String(item.thumbnail_url ?? '') || youtubeThumbnail(sourceUrl), transcript: String(item.transcript ?? ''), stage: item.stage === 'Worth Acting On' || item.stage === 'Reference' ? item.stage : 'Inbox', status, snoozedUntil, action: recommendations[0] ?? '', actionType: String(item.action_type ?? 'Just reference'), impact: Number(item.impact ?? 3), effort: Number(item.effort ?? 3), savedAt: item.ts ? new Date(Number(item.ts) * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'Recently', keyIdeas, whyItMatters: String(item.why_it_matters ?? ''), recommendations, tags, done: status === 'done' };
}

export function useSnagLibrary() {
  const [items, setItems] = useState<SnagItem[]>(sampleItems); const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentTime] = useState(() => Date.now() / 1000);
  const refresh = useCallback(async () => { setIsRefreshing(true); try { const response = await fetch(`${API_BASE}/api/items`); const payload = (await response.json()) as { items?: Record<string, unknown>[] }; if (payload.items?.length) setItems(payload.items.map(mapItem)); } catch { /* Keep an offline library visible. */ } finally { setIsRefreshing(false); } }, []);
  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));
  useEffect(() => {
    let cancelled = false;
    async function loadInitialItems() {
      try {
        const response = await fetch(`${API_BASE}/api/items`);
        const payload = (await response.json()) as { items?: Record<string, unknown>[] };
        if (!cancelled && payload.items?.length) setItems(payload.items.map(mapItem));
      } catch {
        // The offline library is intentional until the local API is reachable.
      }
    }
    void loadInitialItems();
    return () => { cancelled = true; };
  }, []);
  const updateItem = useCallback(async (id: string, changes: ItemUpdate) => {
    let before: SnagItem | undefined;
    setItems((current) => current.map((item) => {
      if (item.id !== id) return item;
      before = item;
      const status = changes.status ?? item.status;
      const snoozedUntil = changes.snooze_until === undefined ? item.snoozedUntil : changes.snooze_until ?? undefined;
      return { ...item, stage: changes.stage ?? item.stage, status, snoozedUntil, done: status === 'done' };
    }));
    try {
      const response = await fetch(`${API_BASE}/api/items/${id}`, { method: 'PATCH', headers: LOCAL_API_HEADERS, body: JSON.stringify(changes) });
      if (!response.ok) throw new Error('Update failed');
    } catch (error) {
      if (before) setItems((current) => current.map((item) => item.id === id ? before! : item));
      throw error;
    }
  }, []);
  const markDone = useCallback((id: string) => updateItem(id, { status: 'done' }), [updateItem]);
  const snoozeItem = useCallback((id: string, until: number) => updateItem(id, { snooze_until: until }), [updateItem]);
  const updateTags = useCallback(async (id: string, changes: TagUpdate) => {
    const additions = (changes.add_tags ?? []).map((tag) => tag.trim().toLowerCase()).filter(Boolean);
    const removals = new Set((changes.remove_tags ?? []).map((tag) => tag.trim().toLowerCase()).filter(Boolean));
    let before: SnagItem | undefined;
    setItems((current) => current.map((item) => {
      if (item.id !== id) return item;
      before = item;
      const tags = [...item.tags];
      for (const tag of additions) if (!tags.some((currentTag) => currentTag.toLowerCase() === tag) && tags.length < 12) tags.push(tag);
      return { ...item, tags: tags.filter((tag) => !removals.has(tag.toLowerCase())) };
    }));
    try {
      const response = await fetch(`${API_BASE}/api/items/${id}`, { method: 'PATCH', headers: LOCAL_API_HEADERS, body: JSON.stringify(changes) });
      if (!response.ok) throw new Error('Tag update failed');
    } catch (error) {
      if (before) setItems((current) => current.map((item) => item.id === id ? before! : item));
      throw error;
    }
  }, []);
  const addTag = useCallback((id: string, tag: string) => updateTags(id, { add_tags: [tag] }), [updateTags]);
  const removeTag = useCallback((id: string, tag: string) => updateTags(id, { remove_tags: [tag] }), [updateTags]);
  const actionQueue = useMemo(() => items.filter((item) => item.status !== 'archived' && item.stage === 'Worth Acting On' && !item.done && (!item.snoozedUntil || item.snoozedUntil < currentTime)).sort((a, b) => b.impact / b.effort - a.impact / a.effort), [currentTime, items]);
  return { items, actionQueue, isRefreshing, refresh, markDone, snoozeItem, updateItem, addTag, removeTag };
}

export async function captureUrl(url: string) { const response = await fetch(`${API_BASE}/api/capture`, { method: 'POST', headers: LOCAL_API_HEADERS, body: JSON.stringify({ url }) }); if (!response.ok) throw new Error('Capture failed'); return response.json(); }

export async function askItem(id: string, question: string) {
  const response = await fetch(`${API_BASE}/api/items/${id}/ask`, { method: 'POST', headers: LOCAL_API_HEADERS, body: JSON.stringify({ question }) });
  if (!response.ok) throw new Error('Ask failed');
  return (await response.json()) as { answer: string; mode: 'ai' | 'quick_read' };
}

export async function askLibrary(question: string) {
  const response = await fetch(`${API_BASE}/api/ask`, { method: 'POST', headers: LOCAL_API_HEADERS, body: JSON.stringify({ question }) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(payload.error || 'Ask failed');
  }
  return (await response.json()) as { answer: string; sources: { id: string | number; title: string }[]; mode: 'ai' | 'quick_read' };
}

export async function captureAndSave(url: string) {
  const previewResponse = await fetch(`${API_BASE}/api/capture`, {
    method: 'POST', headers: LOCAL_API_HEADERS, body: JSON.stringify({ url }),
  });
  if (!previewResponse.ok) {
    const failure = await previewResponse.json().catch(() => ({})) as { error?: string; kind?: string };
    throw new SnagCaptureError(failure.error || 'Snag could not analyze this link.', failure.kind);
  }
  const capture = await previewResponse.json() as {
    preview?: { note: Record<string, unknown>; triage: Record<string, unknown>; transcript: string; content_type: string; url: string; thumbnail_url?: string };
  };
  const preview = capture.preview;
  if (!preview) throw new SnagCaptureError('Snag received an incomplete capture response.');
  const saveResponse = await fetch(`${API_BASE}/api/items`, {
    method: 'POST', headers: LOCAL_API_HEADERS,
    body: JSON.stringify({ url: preview.url, note: preview.note, triage: preview.triage, transcript: preview.transcript, content_type: preview.content_type, thumbnail_url: preview.thumbnail_url }),
  });
  if (!saveResponse.ok) throw new SnagCaptureError('Snag analyzed the link, but could not save it.');
  return saveResponse.json() as Promise<{ id: string | number; duplicate: boolean }>;
}
