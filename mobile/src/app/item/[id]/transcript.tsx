import { Stack, useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { PersistentNav } from '@/components/persistent-nav';
import { SourcePreview } from '@/components/source-preview';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { useSnagLibrary } from '@/lib/snag';

export default function TranscriptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { items } = useSnagLibrary();
  const item = items.find((candidate) => candidate.id === id);

  if (!item) return <View style={styles.missing}><Text style={styles.missingText}>This transcript is not available.</Text></View>;

  return <View style={styles.screen}>
    <ScrollView alwaysBounceVertical contentInsetAdjustmentBehavior="automatic" contentContainerStyle={styles.content} scrollEnabled showsVerticalScrollIndicator>
      <Stack.Screen options={{ title: item.sourceType === 'Web' ? 'Article text' : 'Transcript' }} />
      <Text style={styles.source}>{item.sourceType} · {item.savedAt}</Text>
      <SourcePreview item={item} size="reader" />
      <Text style={styles.title}>{item.title}</Text>
      <View style={styles.note}><Text style={styles.noteText}>Source material saved with this idea</Text></View>
      <Text style={styles.transcript}>{item.transcript || 'No transcript was available for this save.'}</Text>
    </ScrollView>
    <PersistentNav />
  </View>;
}

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { backgroundColor: Colors.light.background, gap: 18, padding: Spacing.four, paddingBottom: 48 }, source: { color: Colors.light.accent, fontSize: 12, fontWeight: '800', textTransform: 'uppercase' }, title: { color: Colors.light.text, fontSize: 25, fontWeight: '700', letterSpacing: -0.7, lineHeight: 32 }, note: { alignSelf: 'flex-start', backgroundColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: Radius.medium, paddingHorizontal: 11, paddingVertical: 7 }, noteText: { color: Colors.light.accent, fontSize: 12, fontWeight: '700' }, transcript: { color: Colors.light.text, fontSize: 17, lineHeight: 28 }, missing: { alignItems: 'center', backgroundColor: Colors.light.background, flex: 1, justifyContent: 'center', padding: Spacing.four }, missingText: { color: Colors.light.muted, fontSize: 16 },
});
