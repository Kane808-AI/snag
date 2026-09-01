import { router, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { PersistentNav } from '@/components/persistent-nav';
import { type SnagItem, useSnagLibrary } from '@/lib/snag';

export default function SearchScreen() {
  const { items } = useSnagLibrary();
  const { query: suppliedQuery } = useLocalSearchParams<{ query?: string }>();
  const [query, setQuery] = useState(suppliedQuery ?? '');
  const results = useMemo(() => search(items.filter((item) => item.status !== 'archived'), query), [items, query]);
  const renderItem = useCallback(({ item }: { item: SnagItem }) => <SearchResult item={item} />, []);
  const itemKey = useCallback((item: SnagItem) => item.id, []);

  return <View style={styles.screen}><FlatList alwaysBounceVertical contentContainerStyle={styles.content} data={results} keyExtractor={itemKey} ListEmptyComponent={<Empty query={query} />} ListHeaderComponent={<View style={styles.header}><Text style={styles.eyebrow}>FIND A SAVE</Text><View style={styles.inputWrap}><SymbolView name="magnifyingglass" size={18} tintColor={Colors.light.placeholder} /><TextInput autoCapitalize="none" autoFocus clearButtonMode="while-editing" onChangeText={setQuery} placeholder="Search ideas, tags, and sources" placeholderTextColor={Colors.light.placeholder} returnKeyType="search" style={styles.input} value={query} /></View><Text style={styles.resultCount}>{query ? `${results.length} result${results.length === 1 ? '' : 's'}` : `${items.length} saved ideas`}</Text></View>} renderItem={renderItem} showsVerticalScrollIndicator /><PersistentNav /></View>;
}

function SearchResult({ item }: { item: SnagItem }) { return <Pressable onPress={() => router.push({ pathname: '/item/[id]', params: { id: item.id } })} style={({ pressed }) => [styles.row, pressed && styles.pressed]}><View style={[styles.sourceIcon, sourceStyle(item.sourceType)]}><Text style={styles.sourceLetter}>{item.sourceType.slice(0, 1)}</Text></View><View style={styles.rowCopy}><Text numberOfLines={2} style={styles.rowTitle}>{item.title}</Text><Text numberOfLines={1} style={styles.rowMeta}>{item.sourceType} · {item.tags.slice(0, 2).join(' · ') || item.savedAt}</Text></View><SymbolView name="chevron.right" size={13} tintColor={Colors.light.placeholder} /></Pressable>; }
function Empty({ query }: { query: string }) { return <View style={styles.empty}><SymbolView name="magnifyingglass" size={26} tintColor={Colors.light.placeholder} /><Text style={styles.emptyTitle}>{query ? 'Nothing found yet.' : 'Your saves will show up here.'}</Text><Text style={styles.emptyText}>{query ? 'Try a different word, tag, or source.' : 'Use search when your library starts to grow.'}</Text></View>; }
function search(items: SnagItem[], query: string) { const needle = query.trim().toLowerCase(); if (!needle) return items; return items.filter((item) => [item.title, item.summary, item.sourceType, item.tags.join(' '), item.keyIdeas.join(' '), item.whyItMatters].join(' ').toLowerCase().includes(needle)); }
function sourceStyle(source: SnagItem['sourceType']) { return source === 'TikTok' ? styles.tiktok : source === 'YouTube' ? styles.youtube : styles.web; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { backgroundColor: Colors.light.background, padding: Spacing.four, paddingBottom: 44 }, header: { gap: 12, paddingBottom: 17 }, eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.6 }, inputWrap: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, flexDirection: 'row', gap: 10, paddingHorizontal: 14 }, input: { color: Colors.light.text, flex: 1, fontSize: 16, paddingVertical: 14 }, resultCount: { color: Colors.light.muted, fontSize: 13 },
  row: { alignItems: 'center', borderBottomColor: Colors.light.border, borderBottomWidth: 1, flexDirection: 'row', gap: 12, paddingVertical: 15 }, sourceIcon: { alignItems: 'center', borderRadius: 13, height: 42, justifyContent: 'center', width: 42 }, sourceLetter: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' }, tiktok: { backgroundColor: '#1A1A1A' }, youtube: { backgroundColor: '#E7382B' }, web: { backgroundColor: '#9C7C55' }, rowCopy: { flex: 1, gap: 4 }, rowTitle: { color: Colors.light.text, fontSize: 15, fontWeight: '700', lineHeight: 21 }, rowMeta: { color: Colors.light.muted, fontSize: 12 },
  empty: { alignItems: 'center', gap: 8, paddingTop: 70 }, emptyTitle: { color: Colors.light.text, fontSize: 17, fontWeight: '700' }, emptyText: { color: Colors.light.muted, fontSize: 14, textAlign: 'center' }, pressed: { opacity: 0.7 },
});
