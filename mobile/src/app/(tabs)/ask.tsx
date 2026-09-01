import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { askLibrary } from '@/lib/snag';

type Message = { id: string; question: string; answer: string; mode: 'ai' | 'quick_read'; sources: { id: string | number; title: string }[] };

const STARTERS = [
  'What should I work on next?',
  'What patterns keep showing up?',
  'What is worth testing first?',
];

export default function AskScreen() {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAsking, setIsAsking] = useState(false);
  const [error, setError] = useState('');

  async function ask(nextQuestion = question) {
    const trimmed = nextQuestion.trim();
    if (!trimmed || isAsking) return;
    setQuestion('');
    setError('');
    setIsAsking(true);
    try {
      const result = await askLibrary(trimmed);
      setMessages((current) => [{ id: `${Date.now()}`, question: trimmed, answer: result.answer, mode: result.mode, sources: result.sources }, ...current]);
    } catch (reason) {
      setQuestion(trimmed);
      setError(reason instanceof Error && reason.message === 'save something before asking Snag' ? 'Save an idea first, then Snag can answer from your library.' : 'Snag could not answer right now. Your saved ideas are safe.');
    } finally {
      setIsAsking(false);
    }
  }

  return <KeyboardAvoidingView behavior={Platform.select({ ios: 'padding', default: undefined })} style={styles.screen}>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
      <View style={styles.heading}><Text style={styles.eyebrow}>ASK SNAG</Text><Text style={styles.title}>Think with your saves.</Text><Text style={styles.subtitle}>Ask a question and Snag will answer from the ideas you already saved, with the sources it used.</Text></View>
      {!messages.length ? <View style={styles.empty}><View style={styles.emptyIcon}><SymbolView name="sparkles" size={25} tintColor={Colors.light.accent} /></View><Text style={styles.emptyTitle}>Your library has a point of view.</Text><Text style={styles.emptyText}>Start with a question about what to do, test, or revisit.</Text><View style={styles.starters}>{STARTERS.map((starter) => <Pressable accessibilityLabel={`Ask Snag: ${starter}`} key={starter} onPress={() => void ask(starter)} style={({ pressed }) => [styles.starter, pressed && styles.pressed]}><Text style={styles.starterText}>{starter}</Text><SymbolView name="arrow.up.right" size={13} tintColor={Colors.light.accent} /></Pressable>)}</View></View> : <View style={styles.messages}>{messages.map((message) => <View key={message.id} style={styles.message}><Text style={styles.question}>{message.question}</Text>{message.mode === 'quick_read' ? <Text style={styles.quickRead}>QUICK LIBRARY READ</Text> : null}<Text style={styles.answer}>{message.answer}</Text>{message.sources.length ? <View style={styles.sources}><Text style={styles.sourcesLabel}>SOURCES USED</Text>{message.sources.map((source) => <Pressable accessibilityLabel={`Open ${source.title}`} key={`${message.id}-${source.id}`} onPress={() => router.push({ pathname: '/item/[id]', params: { id: String(source.id) } })} style={({ pressed }) => [styles.source, pressed && styles.pressed]}><SymbolView name="bookmark.fill" size={12} tintColor={Colors.light.accent} /><Text numberOfLines={1} style={styles.sourceText}>{source.title}</Text><SymbolView name="chevron.right" size={11} tintColor={Colors.light.placeholder} /></Pressable>)}</View> : null}</View>)}</View>}
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </ScrollView>
    <View style={styles.composerWrap}><View style={styles.composer}><TextInput accessibilityLabel="Ask your library" multiline onChangeText={setQuestion} onSubmitEditing={() => void ask()} placeholder="Ask your saved ideas" placeholderTextColor={Colors.light.placeholder} returnKeyType="send" style={styles.input} value={question} /><Pressable accessibilityLabel="Send question to Snag" disabled={!question.trim() || isAsking} onPress={() => void ask()} style={({ pressed }) => [styles.send, (!question.trim() || isAsking) && styles.sendDisabled, pressed && styles.pressed]}>{isAsking ? <ActivityIndicator color="#FFFFFF" size="small" /> : <SymbolView name="arrow.up" size={17} tintColor="#FFFFFF" weight="bold" />}</Pressable></View></View>
  </KeyboardAvoidingView>;
}

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 }, content: { gap: 24, padding: Spacing.four, paddingBottom: 24 }, heading: { gap: 7, paddingTop: 8 }, eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.7 }, title: { color: Colors.light.text, fontSize: 32, fontWeight: '700', letterSpacing: -1.2 }, subtitle: { color: Colors.light.muted, fontSize: 16, lineHeight: 23, maxWidth: 340 }, empty: { alignItems: 'center', backgroundColor: Colors.light.wash, borderCurve: 'continuous', borderRadius: Radius.extraLarge, gap: 10, padding: 24 }, emptyIcon: { alignItems: 'center', backgroundColor: Colors.light.accentSoft, borderRadius: 999, height: 52, justifyContent: 'center', marginBottom: 2, width: 52 }, emptyTitle: { color: Colors.light.text, fontSize: 19, fontWeight: '700', letterSpacing: -0.35, textAlign: 'center' }, emptyText: { color: Colors.light.muted, fontSize: 14, lineHeight: 20, textAlign: 'center' }, starters: { alignSelf: 'stretch', gap: 8, marginTop: 10 }, starter: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.medium, borderWidth: 1, flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 13 }, starterText: { color: Colors.light.text, fontSize: 14, fontWeight: '700' }, messages: { gap: 14 }, message: { backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, gap: 12, padding: 17 }, question: { color: Colors.light.accent, fontSize: 13, fontWeight: '800' }, quickRead: { color: Colors.light.muted, fontSize: 10, fontWeight: '800', letterSpacing: 1.1, marginTop: -5 }, answer: { color: Colors.light.text, fontSize: 16, lineHeight: 23 }, sources: { borderTopColor: Colors.light.border, borderTopWidth: 1, gap: 7, paddingTop: 12 }, sourcesLabel: { color: Colors.light.muted, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 }, source: { alignItems: 'center', flexDirection: 'row', gap: 7, paddingVertical: 3 }, sourceText: { color: Colors.light.accent, flex: 1, fontSize: 13, fontWeight: '700' }, error: { color: '#B34B43', fontSize: 13, lineHeight: 19 }, composerWrap: { backgroundColor: Colors.light.surface, borderTopColor: Colors.light.border, borderTopWidth: 1, padding: 12 }, composer: { alignItems: 'flex-end', backgroundColor: Colors.light.background, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.large, borderWidth: 1, flexDirection: 'row', gap: 8, padding: 9 }, input: { color: Colors.light.text, flex: 1, fontSize: 15, lineHeight: 21, maxHeight: 96, minHeight: 40, paddingHorizontal: 5, paddingTop: 9 }, send: { alignItems: 'center', backgroundColor: Colors.light.accent, borderRadius: 999, height: 40, justifyContent: 'center', width: 40 }, sendDisabled: { backgroundColor: Colors.light.placeholder }, pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
