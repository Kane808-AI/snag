import { router, Stack, useLocalSearchParams } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { ActionSheetIOS, ActivityIndicator, Alert, KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { PersistentNav } from '@/components/persistent-nav';
import { SourcePreview } from '@/components/source-preview';
import { askItem, useSnagLibrary } from '@/lib/snag';

type Message = { id: string; question: string; answer: string; mode: 'ai' | 'quick_read' };

const ASK_STARTERS = ['What should I take from this?', 'What is the next action?', 'Give me the short version'];

export default function SavedItemScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { items, addTag, removeTag, reanalyzeItem, updateItem } = useSnagLibrary();
  const item = items.find((candidate) => candidate.id === id);
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [error, setError] = useState('');

  async function ask() {
    const value = question.trim();
    if (!value || !item || isAsking) return;
    setError('');
    setIsAsking(true);
    try {
      const result = await askItem(item.id, value);
      setMessages((current) => [...current, { id: `${Date.now()}`, question: value, answer: result.answer, mode: result.mode }]);
      setQuestion('');
    } catch {
      setError('Snag could not answer right now. Try again in a moment.');
    } finally {
      setIsAsking(false);
    }
  }

  async function openOriginal() {
    if (!item?.sourceUrl) return;
    await Linking.openURL(item.sourceUrl);
  }

  async function retryAnalysis() {
    if (!item || isReanalyzing) return;
    setError('');
    setIsReanalyzing(true);
    try {
      await reanalyzeItem(item.id);
    } catch {
      setError('AI analysis is still unavailable. Try again in a moment.');
    } finally {
      setIsReanalyzing(false);
    }
  }

  function manageItem() {
    if (!item) return;
    if (item.status === 'archived') {
      ActionSheetIOS.showActionSheetWithOptions({ options: ['Restore to Library', 'Cancel'], cancelButtonIndex: 1, title: 'In Trash' }, (choice) => {
        if (choice === 0) void updateItem(item.id, { status: 'inbox' }).catch(() => setError('That change did not save. Try again.'));
      });
      return;
    }
    const action = item.done ? 'Move back to Today' : item.stage === 'Reference' ? 'Move to Today' : 'Mark done';
    const secondaryAction = item.done || item.stage === 'Reference' ? undefined : 'Save for later';
    const options = [action, ...(secondaryAction ? [secondaryAction] : []), 'Move to Trash', 'Cancel'];
    const trashIndex = options.indexOf('Move to Trash');
    ActionSheetIOS.showActionSheetWithOptions({ cancelButtonIndex: options.length - 1, destructiveButtonIndex: trashIndex, options, title: 'Manage saved idea' }, (choice) => {
      if (choice >= options.length - 1) return;
      if (choice === trashIndex) { void updateItem(item.id, { status: 'archived' }).catch(() => setError('That change did not save. Try again.')); return; }
      const changes = choice === 0 && item.done ? { status: 'in progress' as const, stage: 'Worth Acting On' as const } : choice === 0 && item.stage === 'Reference' ? { stage: 'Worth Acting On' as const } : choice === 0 ? { status: 'done' as const } : { stage: 'Reference' as const };
      void updateItem(item.id, changes).catch(() => setError('That change did not save. Try again.'));
    });
  }

  function promptToAddTag() {
    if (!item) return;
    Alert.prompt('Add a tag', 'Use a short word or phrase.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Add', onPress: (tag?: string) => { if (tag?.trim()) void addTag(item.id, tag).catch(() => setError('That tag did not save. Try again.')); } },
    ], 'plain-text');
  }

  function confirmRemoveTag(tag: string) {
    if (!item) return;
    Alert.alert(`Remove #${tag}?`, undefined, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: () => void removeTag(item.id, tag).catch(() => setError('That tag did not save. Try again.')) },
    ]);
  }

  if (!item) return <View style={styles.missing}><Text style={styles.missingText}>This saved idea is not available.</Text></View>;

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.screen}>
      <Stack.Screen options={{ title: item.sourceType }} />
      <ScrollView alwaysBounceVertical contentInsetAdjustmentBehavior="automatic" contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator>
        <View style={styles.metaRow}><Text style={styles.source}>{item.sourceType}</Text><Text style={styles.date}>{item.savedAt}</Text>{item.status === 'archived' ? <Text style={styles.trashed}>IN TRASH</Text> : null}</View>
        <SourcePreview item={item} />
        <Text style={styles.title}>{item.title}</Text>
        <Text style={styles.summary}>{item.summary}</Text>
        {item.analysisState === 'awaiting_ai' ? <View style={styles.pendingPanel}><Text style={styles.pendingTitle}>Awaiting AI analysis</Text><Text style={styles.pendingBody}>Your source is saved. Snag can retry the analysis when AI is available.</Text><Pressable accessibilityLabel="Retry analysis" disabled={isReanalyzing} onPress={() => void retryAnalysis()} style={({ pressed }) => [styles.retryButton, isReanalyzing && styles.retryDisabled, pressed && styles.pressed]}>{isReanalyzing ? <ActivityIndicator color="#FFFFFF" size="small" /> : <Text style={styles.retryText}>Retry analysis</Text>}</Pressable></View> : null}
        <View style={styles.sourceActions}>
          {item.sourceUrl ? <Pressable accessibilityLabel="Open original source" onPress={() => void openOriginal()} style={({ pressed }) => [styles.sourceAction, pressed && styles.pressed]}><SymbolView name="arrow.up.right.square" size={15} tintColor={Colors.light.text} /><Text style={styles.sourceActionText}>Original</Text></Pressable> : null}
          <Pressable accessibilityLabel="Read transcript" onPress={() => router.push({ pathname: '/item/[id]/transcript', params: { id: item.id } })} style={({ pressed }) => [styles.sourceAction, pressed && styles.pressed]}><SymbolView name="text.alignleft" size={15} tintColor={Colors.light.text} /><Text style={styles.sourceActionText}>Transcript</Text></Pressable>
          <Pressable accessibilityLabel="Manage saved idea" onPress={manageItem} style={({ pressed }) => [styles.sourceAction, pressed && styles.pressed]}><SymbolView name="ellipsis" size={16} tintColor={Colors.light.text} weight="bold" /><Text style={styles.sourceActionText}>Manage</Text></Pressable>
        </View>

        <Section title="Ask Snag"><Text style={styles.askIntro}>Ask about this save. Snag only uses this item’s note and source material.</Text><View style={styles.askStarters}>{ASK_STARTERS.map((starter) => <Pressable accessibilityLabel={`Ask Snag: ${starter}`} key={starter} onPress={() => setQuestion(starter)} style={({ pressed }) => [styles.askStarter, question === starter && styles.askStarterActive, pressed && styles.pressed]}><Text style={[styles.askStarterText, question === starter && styles.askStarterTextActive]}>{starter}</Text></Pressable>)}</View><View style={styles.composer}><TextInput multiline onChangeText={setQuestion} placeholder="Ask your own question" placeholderTextColor={Colors.light.placeholder} style={styles.input} value={question} /><Pressable accessibilityLabel="Ask Snag" disabled={!question.trim() || isAsking} onPress={() => void ask()} style={({ pressed }) => [styles.askButton, (!question.trim() || isAsking) && styles.askDisabled, pressed && styles.pressed]}>{isAsking ? <ActivityIndicator color="#FFFFFF" size="small" /> : <SymbolView name="arrow.up" size={17} tintColor="#FFFFFF" weight="bold" />}</Pressable></View>{error ? <Text style={styles.error}>{error}</Text> : null}{messages.map((message) => <View key={message.id} style={styles.message}><Text style={styles.question}>{message.question}</Text>{message.mode === 'quick_read' ? <Text style={styles.quickRead}>QUICK ITEM READ</Text> : null}<Text style={styles.answer}>{message.answer}</Text></View>)}</Section>

        <Section title="Key ideas">{item.keyIdeas.map((idea, index) => <View key={`${idea}-${index}`} style={styles.bulletRow}><Text style={styles.bullet}>{index + 1}</Text><Text style={styles.body}>{idea}</Text></View>)}</Section>
        <Section title="Why it matters"><Text style={styles.body}>{item.whyItMatters || 'This is saved as useful reference.'}</Text></Section>
        {item.recommendations.length ? <Section title="Try this"><View style={styles.recommendation}><SymbolView name="arrow.right" size={15} tintColor={Colors.light.accent} /><Text style={styles.recommendationText}>{item.recommendations[0]}</Text></View></Section> : null}

        <Section title="Tags"><View style={styles.tags}>{item.tags.map((tag) => <Pressable accessibilityLabel={`Remove tag ${tag}`} key={tag} onPress={() => confirmRemoveTag(tag)} style={({ pressed }) => [styles.tag, pressed && styles.pressed]}><Text style={styles.tagText}>#{tag}</Text></Pressable>)}<Pressable accessibilityLabel="Add a tag" onPress={promptToAddTag} style={({ pressed }) => [styles.addTag, pressed && styles.pressed]}><SymbolView name="plus" size={12} tintColor={Colors.light.accent} weight="bold" /><Text style={styles.addTagText}>Tag</Text></Pressable></View></Section>
      </ScrollView>
      <PersistentNav />
    </KeyboardAvoidingView>
  );
}

function Section({ children, title }: { children: React.ReactNode; title: string }) { return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>; }

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { backgroundColor: Colors.light.background, gap: 24, padding: Spacing.four, paddingBottom: 44 },
  metaRow: { flexDirection: 'row', gap: 8 }, source: { color: Colors.light.accent, fontSize: 12, fontWeight: '800', textTransform: 'uppercase' }, date: { color: Colors.light.muted, fontSize: 12 }, trashed: { color: '#B34B43', fontSize: 11, fontWeight: '800', letterSpacing: 0.8 }, title: { color: Colors.light.text, fontSize: 27, fontWeight: '700', letterSpacing: -0.8, lineHeight: 34 }, summary: { color: Colors.light.muted, fontSize: 17, lineHeight: 25, marginTop: -14 },
  sourceActions: { flexDirection: 'row', gap: 8, marginTop: -8 }, sourceAction: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: 999, borderWidth: 1, flexDirection: 'row', gap: 6, paddingHorizontal: 12, paddingVertical: 9 }, sourceActionText: { color: Colors.light.text, fontSize: 13, fontWeight: '700' },
  section: { gap: 11 }, sectionTitle: { color: Colors.light.text, fontSize: 16, fontWeight: '800' }, body: { color: Colors.light.text, flex: 1, fontSize: 16, lineHeight: 24 }, bulletRow: { alignItems: 'flex-start', flexDirection: 'row', gap: 10 }, bullet: { backgroundColor: Colors.light.accentSoft, borderRadius: 999, color: Colors.light.accent, fontSize: 11, fontWeight: '800', height: 21, overflow: 'hidden', paddingTop: 3, textAlign: 'center', width: 21 }, recommendation: { alignItems: 'flex-start', backgroundColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: Radius.large, flexDirection: 'row', gap: 10, padding: 15 }, recommendationText: { color: Colors.light.text, flex: 1, fontSize: 15, fontWeight: '600', lineHeight: 22 },
  askIntro: { color: Colors.light.muted, fontSize: 14, lineHeight: 20 }, askStarters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, askStarter: { backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: 999, borderWidth: 1, paddingHorizontal: 11, paddingVertical: 8 }, askStarterActive: { backgroundColor: Colors.light.accentSoft, borderColor: Colors.light.accent }, askStarterText: { color: Colors.light.muted, fontSize: 12, fontWeight: '700' }, askStarterTextActive: { color: Colors.light.accent }, composer: { alignItems: 'flex-end', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, flexDirection: 'row', gap: 8, padding: 10 }, input: { color: Colors.light.text, flex: 1, fontSize: 15, lineHeight: 21, maxHeight: 100, minHeight: 41, paddingHorizontal: 4, paddingTop: 10 }, askButton: { alignItems: 'center', backgroundColor: Colors.light.accent, borderRadius: 999, height: 40, justifyContent: 'center', width: 40 }, askDisabled: { backgroundColor: Colors.light.placeholder }, error: { color: '#B34B43', fontSize: 13, lineHeight: 19 }, message: { backgroundColor: Colors.light.wash, borderCurve: 'continuous', borderRadius: Radius.large, gap: 8, padding: 15 }, question: { color: Colors.light.accent, fontSize: 13, fontWeight: '800' }, quickRead: { color: Colors.light.muted, fontSize: 10, fontWeight: '800', letterSpacing: 1.1, marginTop: -4 }, answer: { color: Colors.light.text, fontSize: 15, lineHeight: 22 },
  pendingPanel: { backgroundColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: Radius.large, gap: 9, padding: 16 }, pendingTitle: { color: Colors.light.accent, fontSize: 15, fontWeight: '800' }, pendingBody: { color: Colors.light.text, fontSize: 14, lineHeight: 20 }, retryButton: { alignItems: 'center', alignSelf: 'flex-start', backgroundColor: Colors.light.accent, borderRadius: 999, minHeight: 38, paddingHorizontal: 14, justifyContent: 'center' }, retryDisabled: { opacity: 0.65 }, retryText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 }, tag: { backgroundColor: Colors.light.wash, borderCurve: 'continuous', borderRadius: 999, overflow: 'hidden', paddingHorizontal: 10, paddingVertical: 6 }, tagText: { color: Colors.light.muted, fontSize: 12, fontWeight: '700' }, addTag: { alignItems: 'center', borderColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: 999, borderWidth: 1, flexDirection: 'row', gap: 4, paddingHorizontal: 10, paddingVertical: 6 }, addTagText: { color: Colors.light.accent, fontSize: 12, fontWeight: '800' }, missing: { alignItems: 'center', backgroundColor: Colors.light.background, flex: 1, justifyContent: 'center', padding: Spacing.four }, missingText: { color: Colors.light.muted, fontSize: 16 }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
