import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useMemo } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { PersistentNav } from '@/components/persistent-nav';
import { useSnagLibrary } from '@/lib/snag';

type Topic = { name: string; count: number };

export default function TopicsScreen() {
  const { items } = useSnagLibrary();
  const topics = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of items.filter((item) => item.status !== 'archived')) for (const rawTag of item.tags) {
      const tag = rawTag.trim();
      if (tag) counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    return [...counts.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  }, [items]);

  return <View style={styles.screen}><FlatList contentContainerStyle={styles.content} data={topics} keyExtractor={(topic) => topic.name.toLowerCase()} ListEmptyComponent={<EmptyTopics />} ListHeaderComponent={<View style={styles.header}><Text style={styles.eyebrow}>TOPICS</Text><Text style={styles.title}>Find a thread.</Text><Text style={styles.subtitle}>Topics come from the tags attached to your saved ideas. Tap one to see everything connected to it.</Text></View>} renderItem={({ item }) => <TopicRow topic={item} />} showsVerticalScrollIndicator /><PersistentNav /></View>;
}

function TopicRow({ topic }: { topic: Topic }) { return <Pressable accessibilityLabel={`Browse topic ${topic.name}`} onPress={() => router.push({ pathname: '/search', params: { query: topic.name } })} style={({ pressed }) => [styles.row, pressed && styles.pressed]}><View style={styles.topicMark}><Text style={styles.hash}>#</Text></View><View style={styles.copy}><Text style={styles.topicName}>{topic.name}</Text><Text style={styles.count}>{topic.count} saved idea{topic.count === 1 ? '' : 's'}</Text></View><SymbolView name="chevron.right" size={14} tintColor={Colors.light.placeholder} /></Pressable>; }
function EmptyTopics() { return <View style={styles.empty}><SymbolView name="number" size={27} tintColor={Colors.light.placeholder} /><Text style={styles.emptyTitle}>Topics will appear here.</Text><Text style={styles.emptyText}>Add a tag on any saved idea to start shaping your library.</Text></View>; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { padding: Spacing.four, paddingBottom: 42 }, header: { gap: 7, paddingBottom: 22, paddingTop: 6 }, eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.7 }, title: { color: Colors.light.text, fontSize: 31, fontWeight: '700', letterSpacing: -1.1 }, subtitle: { color: Colors.light.muted, fontSize: 15, lineHeight: 22, maxWidth: 350 }, row: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, flexDirection: 'row', gap: 12, marginBottom: 10, padding: 14 }, topicMark: { alignItems: 'center', backgroundColor: Colors.light.accentSoft, borderRadius: 14, height: 42, justifyContent: 'center', width: 42 }, hash: { color: Colors.light.accent, fontSize: 18, fontWeight: '800' }, copy: { flex: 1, gap: 3 }, topicName: { color: Colors.light.text, fontSize: 16, fontWeight: '700' }, count: { color: Colors.light.muted, fontSize: 12 }, empty: { alignItems: 'center', gap: 8, paddingTop: 72 }, emptyTitle: { color: Colors.light.text, fontSize: 17, fontWeight: '700' }, emptyText: { color: Colors.light.muted, fontSize: 14, lineHeight: 20, maxWidth: 270, textAlign: 'center' }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
