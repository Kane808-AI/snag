import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useCallback, useMemo, useState } from 'react';
import { ActionSheetIOS, FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { SourcePreview } from '@/components/source-preview';
import { type SnagItem, useSnagLibrary } from '@/lib/snag';

type SourceFilter = 'All' | SnagItem['sourceType'];

export default function LibraryScreen() {
  const { actionQueue, items, isRefreshing, refresh } = useSnagLibrary();
  const [filter, setFilter] = useState<SourceFilter>('All');
  const libraryItems = useMemo(() => items.filter((item) => item.status !== 'archived'), [items]);
  const visibleItems = useMemo(() => filter === 'All' ? libraryItems : libraryItems.filter((item) => item.sourceType === filter), [filter, libraryItems]);
  const focusItem = actionQueue[0];
  const renderItem = useCallback(({ index, item }: { index: number; item: SnagItem }) => <View style={styles.gridItem}><VisualCard index={index} item={item} /></View>, []);
  const itemKey = useCallback((item: SnagItem) => item.id, []);

  return (
    <FlatList
      alwaysBounceVertical
      contentContainerStyle={styles.content}
      data={visibleItems}
      keyExtractor={itemKey}
      ListEmptyComponent={<Text style={styles.empty}>No saved ideas in this view yet.</Text>}
      ListHeaderComponent={<LibraryHeader filter={filter} focusItem={focusItem} itemCount={libraryItems.length} onFilterChange={setFilter} onRefresh={refresh} />}
      numColumns={2}
      onRefresh={refresh}
      renderItem={renderItem}
      refreshing={isRefreshing}
      removeClippedSubviews={false}
      scrollEnabled
      showsVerticalScrollIndicator
      style={styles.screen}
    />
  );
}

function LibraryHeader({ filter, focusItem, itemCount, onFilterChange, onRefresh }: { filter: SourceFilter; focusItem?: SnagItem; itemCount: number; onFilterChange: (filter: SourceFilter) => void; onRefresh: () => Promise<void> }) {
  return (
    <View style={styles.header}>
      <View style={styles.topRow}>
        <View><Text style={styles.eyebrow}>SNAG</Text><Text style={styles.title}>Your saves</Text></View>
        <View style={styles.topActions}><Pressable accessibilityLabel="Search saves" onPress={openSearch} style={({ pressed }) => [styles.searchButton, pressed && styles.pressed]}><SymbolView name="magnifyingglass" size={17} tintColor={Colors.light.text} weight="semibold" /></Pressable><Pressable accessibilityLabel="Save a link" onPress={openSave} style={({ pressed }) => [styles.addButton, pressed && styles.pressed]}><SymbolView name="plus" size={17} tintColor="#FFFFFF" weight="bold" /><Text style={styles.addText}>Save</Text></Pressable></View>
      </View>
      {focusItem ? <Pressable onPress={() => openItem(focusItem.id)} style={({ pressed }) => [styles.focusCard, sourceBackground(focusItem.sourceType), pressed && styles.pressed]}>
        <View style={styles.focusTop}><Text style={styles.focusLabel}>MOVE THIS FORWARD</Text><SymbolView name="arrow.up.right" size={16} tintColor="#FFFFFF" /></View>
        <Text numberOfLines={3} style={styles.focusTitle}>{focusItem.action || focusItem.title}</Text>
        <View style={styles.focusBottom}><Text style={styles.focusMeta}>{focusItem.sourceType} · Impact {focusItem.impact}/5</Text><Text style={styles.focusCta}>Open</Text></View>
      </Pressable> : null}
      <View style={styles.sectionHeading}><Text style={styles.sectionTitle}>Your brain</Text><View style={styles.libraryTools}><Text style={styles.count}>{itemCount} saved</Text><Pressable accessibilityLabel="Library menu" onPress={() => openLibraryMenu(onRefresh)} style={({ pressed }) => [styles.moreButton, pressed && styles.pressed]}><SymbolView name="ellipsis" size={17} tintColor={Colors.light.text} weight="bold" /><Text style={styles.moreText}>More</Text></Pressable></View></View>
      <View style={styles.filters}>{(['All', 'TikTok', 'YouTube', 'Web'] as SourceFilter[]).map((source) => <FilterChip active={filter === source} key={source} label={source} onPress={() => onFilterChange(source)} />)}</View>
    </View>
  );
}

function FilterChip({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  return <Pressable onPress={onPress} style={({ pressed }) => [styles.filter, active && styles.filterActive, pressed && styles.pressed]}><Text style={[styles.filterText, active && styles.filterTextActive]}>{label}</Text></Pressable>;
}

function VisualCard({ index, item }: { index: number; item: SnagItem }) {
  return <Pressable onPress={() => openItem(item.id)} style={({ pressed }) => [styles.visualCard, cardTone(index), pressed && styles.pressed]}><SourcePreview item={item} size="card" /><View style={styles.cardContent}><View style={styles.cardTop}><View style={[styles.sourceDot, sourceDot(item.sourceType)]}><Text style={styles.sourceDotText}>{item.sourceType.slice(0, 1)}</Text></View><Text style={styles.cardSource}>{item.sourceType}</Text></View><Text numberOfLines={3} style={styles.cardTitle}>{item.title}</Text><View style={styles.cardBottom}><Text style={styles.cardDate}>{item.savedAt}</Text>{item.stage === 'Worth Acting On' ? <SymbolView name="sparkles" size={13} tintColor={Colors.light.accent} /> : null}</View></View></Pressable>;
}

function openSave() { router.push('/save'); }
function openSearch() { router.push('/search'); }
function openLibraryMenu(onRefresh: () => Promise<void>) { ActionSheetIOS.showActionSheetWithOptions({ options: ['Search saves', 'Browse topics', 'Trash', 'Refresh library', 'Cancel'], cancelButtonIndex: 4, title: 'Library' }, (index) => { if (index === 0) openSearch(); if (index === 1) router.push('/topics'); if (index === 2) router.push('/trash'); if (index === 3) void onRefresh(); }); }
function openItem(id: string) { router.push({ pathname: '/item/[id]', params: { id } }); }
function sourceBackground(source: SnagItem['sourceType']) { return source === 'TikTok' ? styles.focusTikTok : source === 'YouTube' ? styles.focusYouTube : styles.focusWeb; }
function sourceDot(source: SnagItem['sourceType']) { return source === 'TikTok' ? styles.tiktok : source === 'YouTube' ? styles.youtube : styles.web; }
function cardTone(index: number) { return [styles.cardSage, styles.cardSand, styles.cardSky, styles.cardRose][index % 4]; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { backgroundColor: Colors.light.background, padding: Spacing.four, paddingBottom: 42 }, header: { gap: 18, paddingBottom: 18 }, topRow: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', paddingTop: 8 }, eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.7 }, title: { color: Colors.light.text, fontSize: 32, fontWeight: '700', letterSpacing: -1.2, marginTop: 1 },
  topActions: { alignItems: 'center', flexDirection: 'row', gap: 8 }, searchButton: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderRadius: 999, borderWidth: 1, height: 36, justifyContent: 'center', width: 36 }, addButton: { alignItems: 'center', backgroundColor: Colors.light.text, borderCurve: 'continuous', borderRadius: 999, flexDirection: 'row', gap: 6, paddingHorizontal: 13, paddingVertical: 9 }, addText: { color: '#FFFFFF', fontSize: 13, fontWeight: '700' },
  focusCard: { borderCurve: 'continuous', borderRadius: Radius.extraLarge, gap: 20, minHeight: 205, padding: 20 }, focusTikTok: { backgroundColor: '#303233' }, focusYouTube: { backgroundColor: '#B8463B' }, focusWeb: { backgroundColor: '#486F63' }, focusTop: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' }, focusLabel: { color: 'rgba(255,255,255,0.76)', fontSize: 10, fontWeight: '800', letterSpacing: 1.2 }, focusTitle: { color: '#FFFFFF', fontSize: 23, fontWeight: '700', letterSpacing: -0.55, lineHeight: 29 }, focusBottom: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' }, focusMeta: { color: 'rgba(255,255,255,0.72)', fontSize: 12, fontWeight: '600' }, focusCta: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
  sectionHeading: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 }, sectionTitle: { color: Colors.light.text, fontSize: 20, fontWeight: '700', letterSpacing: -0.4 }, libraryTools: { alignItems: 'center', flexDirection: 'row', gap: 9 }, count: { color: Colors.light.muted, fontSize: 13 }, moreButton: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderRadius: 999, borderWidth: 1, flexDirection: 'row', gap: 3, paddingHorizontal: 9, paddingVertical: 6 }, moreText: { color: Colors.light.text, fontSize: 12, fontWeight: '700' }, filters: { flexDirection: 'row', gap: 8 }, filter: { backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 8 }, filterActive: { backgroundColor: Colors.light.text, borderColor: Colors.light.text }, filterText: { color: Colors.light.muted, fontSize: 12, fontWeight: '700' }, filterTextActive: { color: '#FFFFFF' },
  gridItem: { flex: 1, marginBottom: 12 }, visualCard: { borderCurve: 'continuous', borderRadius: Radius.large, flex: 1, minHeight: 222, overflow: 'hidden' }, cardContent: { flex: 1, gap: 11, justifyContent: 'space-between', padding: 14 }, cardSage: { backgroundColor: '#E0EBE5', marginRight: 6 }, cardSand: { backgroundColor: '#F0E7D8', marginLeft: 6 }, cardSky: { backgroundColor: '#DFEAF0', marginRight: 6 }, cardRose: { backgroundColor: '#F1E2E1', marginLeft: 6 }, cardTop: { alignItems: 'center', flexDirection: 'row', gap: 7 }, sourceDot: { alignItems: 'center', borderRadius: 999, height: 22, justifyContent: 'center', width: 22 }, sourceDotText: { color: '#FFFFFF', fontSize: 10, fontWeight: '800' }, tiktok: { backgroundColor: '#1A1A1A' }, youtube: { backgroundColor: '#E7382B' }, web: { backgroundColor: '#9C7C55' }, cardSource: { color: Colors.light.muted, fontSize: 11, fontWeight: '800', textTransform: 'uppercase' }, cardTitle: { color: Colors.light.text, fontSize: 15, fontWeight: '700', letterSpacing: -0.28, lineHeight: 20 }, cardBottom: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' }, cardDate: { color: Colors.light.muted, fontSize: 11, fontWeight: '600' },
  empty: { color: Colors.light.muted, fontSize: 14, paddingVertical: 30, textAlign: 'center' }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
