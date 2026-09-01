import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { ActionSheetIOS, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useState } from 'react';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { type SnagItem, useSnagLibrary } from '@/lib/snag';

export default function TodayScreen() {
  const { actionQueue, markDone, snoozeItem } = useSnagLibrary();
  const lead = actionQueue[0];
  const remaining = actionQueue.slice(1, 4);
  const [completedTitle, setCompletedTitle] = useState('');

  async function complete(id: string, title: string) {
    try {
      await markDone(id);
      setCompletedTitle(title);
    } catch {
      setCompletedTitle('That did not save. Try marking it done again.');
    }
  }

  return (
    <ScrollView contentInsetAdjustmentBehavior="automatic" contentContainerStyle={styles.content} showsVerticalScrollIndicator={false} style={styles.screen}>
      <View style={styles.heading}><Text style={styles.eyebrow}>TODAY</Text><Text style={styles.title}>Make one move.</Text><Text style={styles.subtitle}>Snag picked the saved idea with the best upside for the effort.</Text></View>
      {completedTitle ? <View style={styles.completion}><SymbolView name="checkmark.circle.fill" size={18} tintColor={Colors.light.accent} /><Text style={styles.completionText}>{completedTitle.includes('did not save') ? completedTitle : 'Done. Snag moved that idea out of your queue.'}</Text></View> : null}
      {lead ? <FocusCard item={lead} onDone={complete} snoozeItem={snoozeItem} /> : <EmptyToday />}
      {remaining.length ? <View style={styles.next}><Text style={styles.nextTitle}>Then, if you have time</Text>{remaining.map((item) => <Pressable key={item.id} onPress={() => router.push({ pathname: '/item/[id]', params: { id: item.id } })} style={({ pressed }) => [styles.nextRow, pressed && styles.pressed]}><View><Text numberOfLines={1} style={styles.nextItemTitle}>{item.title}</Text><Text style={styles.nextMeta}>{item.actionType} · Impact {item.impact}/5</Text></View><SymbolView name="chevron.right" size={13} tintColor={Colors.light.placeholder} /></Pressable>)}</View> : null}
    </ScrollView>
  );
}

function FocusCard({ item, onDone, snoozeItem }: { item: SnagItem; onDone: (id: string, title: string) => Promise<void>; snoozeItem: (id: string, until: number) => Promise<void> }) {
  function showSnoozeOptions() { ActionSheetIOS.showActionSheetWithOptions({ cancelButtonIndex: 2, options: ['Tomorrow', 'Next week', 'Cancel'], title: 'Snooze until' }, (choice) => { if (choice > 1) return; const date = new Date(); date.setDate(date.getDate() + (choice === 0 ? 1 : 7)); date.setHours(9, 0, 0, 0); void snoozeItem(item.id, Math.floor(date.getTime() / 1000)); }); }
  return <View style={styles.focusCard}><View style={styles.focusKicker}><View style={styles.number}><Text style={styles.numberText}>01</Text></View><Text style={styles.source}>{item.sourceType}</Text></View><Text style={styles.focusTitle}>{item.action || item.title}</Text><Text style={styles.focusBody}>{item.whyItMatters || item.summary}</Text><View style={styles.focusFooter}><View><Text style={styles.score}>Impact {item.impact}/5</Text><Text style={styles.effort}>Low effort · {item.actionType}</Text></View><View style={styles.focusButtons}><Pressable onPress={showSnoozeOptions} style={({ pressed }) => [styles.snoozeButton, pressed && styles.pressed]}><Text style={styles.snoozeText}>Later</Text></Pressable><Pressable onPress={() => void onDone(item.id, item.title)} style={({ pressed }) => [styles.doneButton, pressed && styles.pressed]}><SymbolView name="checkmark" size={15} tintColor="#FFFFFF" weight="bold" /><Text style={styles.doneText}>Done</Text></Pressable></View></View></View>;
}

function EmptyToday() { return <View style={styles.empty}><SymbolView name="checkmark.circle.fill" size={30} tintColor={Colors.light.accent} /><Text style={styles.emptyTitle}>You’re clear for today.</Text><Text style={styles.emptyText}>Save something new when inspiration shows up. Snag will surface it when it matters.</Text></View>; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { backgroundColor: Colors.light.background, gap: 24, padding: Spacing.four, paddingBottom: 42 },
  heading: { gap: 7, paddingTop: 8 }, eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.7 }, title: { color: Colors.light.text, fontSize: 32, fontWeight: '700', letterSpacing: -1.2 }, subtitle: { color: Colors.light.muted, fontSize: 16, lineHeight: 23, maxWidth: 330 },
  focusCard: { backgroundColor: Colors.light.text, borderCurve: 'continuous', borderRadius: Radius.extraLarge, gap: 18, padding: 22 }, focusKicker: { alignItems: 'center', flexDirection: 'row', gap: 9 }, number: { alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.14)', borderRadius: 999, height: 27, justifyContent: 'center', width: 27 }, numberText: { color: '#FFFFFF', fontSize: 10, fontWeight: '800' }, source: { color: 'rgba(255,255,255,0.66)', fontSize: 11, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' }, focusTitle: { color: '#FFFFFF', fontSize: 24, fontWeight: '700', letterSpacing: -0.6, lineHeight: 30 }, focusBody: { color: 'rgba(255,255,255,0.72)', fontSize: 15, lineHeight: 22 }, focusFooter: { alignItems: 'center', borderTopColor: 'rgba(255,255,255,0.14)', borderTopWidth: 1, flexDirection: 'row', justifyContent: 'space-between', paddingTop: 16 }, score: { color: '#FFFFFF', fontSize: 13, fontWeight: '700' }, effort: { color: 'rgba(255,255,255,0.63)', fontSize: 11, marginTop: 2 }, focusButtons: { alignItems: 'center', flexDirection: 'row', gap: 8 }, snoozeButton: { borderColor: 'rgba(255,255,255,0.36)', borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 10 }, snoozeText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' }, doneButton: { alignItems: 'center', backgroundColor: Colors.light.accent, borderRadius: 999, flexDirection: 'row', gap: 6, paddingHorizontal: 14, paddingVertical: 10 }, doneText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
  completion: { alignItems: 'center', backgroundColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: Radius.medium, flexDirection: 'row', gap: 8, padding: 13 }, completionText: { color: Colors.light.accent, flex: 1, fontSize: 13, fontWeight: '700', lineHeight: 19 }, next: { gap: 9 }, nextTitle: { color: Colors.light.text, fontSize: 16, fontWeight: '800' }, nextRow: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.medium, borderWidth: 1, flexDirection: 'row', justifyContent: 'space-between', padding: 14 }, nextItemTitle: { color: Colors.light.text, fontSize: 14, fontWeight: '700', maxWidth: 280 }, nextMeta: { color: Colors.light.muted, fontSize: 12, marginTop: 4 },
  empty: { alignItems: 'center', backgroundColor: Colors.light.wash, borderCurve: 'continuous', borderRadius: Radius.extraLarge, gap: 8, padding: 30 }, emptyTitle: { color: Colors.light.text, fontSize: 17, fontWeight: '700' }, emptyText: { color: Colors.light.muted, fontSize: 14, lineHeight: 20, textAlign: 'center' }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
