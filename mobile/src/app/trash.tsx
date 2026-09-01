import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useMemo } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { PersistentNav } from '@/components/persistent-nav';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { type SnagItem, useSnagLibrary } from '@/lib/snag';

export default function TrashScreen() {
  const { items, updateItem } = useSnagLibrary();
  const trashed = useMemo(() => items.filter((item) => item.status === 'archived'), [items]);
  const renderItem = useCallback(({ item }: { item: SnagItem }) => <TrashRow item={item} onRestore={updateItem} />, [updateItem]);
  return <View style={styles.screen}><FlatList contentContainerStyle={styles.content} data={trashed} keyExtractor={(item) => item.id} ListEmptyComponent={<EmptyTrash />} ListHeaderComponent={<View style={styles.header}><Text style={styles.eyebrow}>TRASH</Text><Text style={styles.title}>Nothing is gone yet.</Text><Text style={styles.subtitle}>Saves in Trash stay here until you restore them. Snag does not permanently delete anything from this screen.</Text></View>} renderItem={renderItem} showsVerticalScrollIndicator /><PersistentNav /></View>;
}

function TrashRow({ item, onRestore }: { item: SnagItem; onRestore: (id: string, changes: { status: 'inbox' }) => Promise<void> }) { return <View style={styles.row}><Pressable accessibilityLabel={`Open ${item.title}`} onPress={() => router.push({ pathname: '/item/[id]', params: { id: item.id } })} style={({ pressed }) => [styles.rowCopy, pressed && styles.pressed]}><Text numberOfLines={2} style={styles.rowTitle}>{item.title}</Text><Text style={styles.meta}>{item.sourceType} · Saved {item.savedAt}</Text></Pressable><Pressable accessibilityLabel={`Restore ${item.title}`} onPress={() => void onRestore(item.id, { status: 'inbox' })} style={({ pressed }) => [styles.restore, pressed && styles.pressed]}><SymbolView name="arrow.uturn.backward" size={13} tintColor={Colors.light.accent} /><Text style={styles.restoreText}>Restore</Text></Pressable></View>; }
function EmptyTrash() { return <View style={styles.empty}><SymbolView name="trash" size={27} tintColor={Colors.light.placeholder} /><Text style={styles.emptyTitle}>Trash is empty.</Text><Text style={styles.emptyText}>If you move a save out of your Library, you can restore it here.</Text></View>; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { padding: Spacing.four, paddingBottom: 42 }, header: { gap: 7, paddingBottom: 22, paddingTop: 6 }, eyebrow: { color: '#B34B43', fontSize: 11, fontWeight: '800', letterSpacing: 1.7 }, title: { color: Colors.light.text, fontSize: 31, fontWeight: '700', letterSpacing: -1.1 }, subtitle: { color: Colors.light.muted, fontSize: 15, lineHeight: 22, maxWidth: 350 }, row: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, flexDirection: 'row', gap: 12, marginBottom: 10, padding: 14 }, rowCopy: { flex: 1, gap: 4 }, rowTitle: { color: Colors.light.text, fontSize: 15, fontWeight: '700', lineHeight: 21 }, meta: { color: Colors.light.muted, fontSize: 12 }, restore: { alignItems: 'center', backgroundColor: Colors.light.accentSoft, borderRadius: 999, flexDirection: 'row', gap: 5, paddingHorizontal: 10, paddingVertical: 8 }, restoreText: { color: Colors.light.accent, fontSize: 12, fontWeight: '800' }, empty: { alignItems: 'center', gap: 8, paddingTop: 72 }, emptyTitle: { color: Colors.light.text, fontSize: 17, fontWeight: '700' }, emptyText: { color: Colors.light.muted, fontSize: 14, lineHeight: 20, maxWidth: 270, textAlign: 'center' }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
