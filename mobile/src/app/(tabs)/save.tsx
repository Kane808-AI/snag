import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { captureAndSave, SnagCaptureError } from '@/lib/snag';

export default function SaveScreen() {
  const [url, setUrl] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  async function save() {
    const value = url.trim();
    if (!/^https?:\/\//i.test(value)) {
      Alert.alert('Paste a link', 'Snag needs the full link, starting with https://.');
      return;
    }
    setIsSaving(true);
    try {
      await captureAndSave(value);
      Alert.alert('Saved to Snag', 'Your new save is ready in the Library.', [{ text: 'View library', onPress: () => router.replace('/') }]);
      setUrl('');
    } catch (error) {
      if (error instanceof SnagCaptureError) {
        const copy = error.kind === 'loginwall'
          ? `${error.message} needs a signed-in source connection before Snag can capture it. No save was created.`
          : error.kind === 'duration'
            ? 'This video is longer than the current capture limit. No save was created.'
            : error.kind === 'analyze'
              ? 'Snag’s analysis service could not complete this one. No save was created.'
              : `${error.message} No save was created.`;
        Alert.alert('Could not save this link', copy);
      } else {
        Alert.alert('Snag is not connected', 'The local Snag service is unavailable. Try again in a moment.');
      }
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.screen}>
      <ScrollView contentContainerStyle={styles.content} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        <View style={styles.heading}>
          <View style={styles.icon}><SymbolView name="arrow.down.to.line.compact" size={23} tintColor={Colors.light.accent} weight="bold" /></View>
          <Text style={styles.eyebrow}>NEW SAVE</Text>
          <Text style={styles.title}>Don’t lose{`\n`}the good stuff.</Text>
          <Text style={styles.subtitle}>Drop in a link. Snag pulls out the idea and gives you one useful next move.</Text>
        </View>

        <View style={styles.formCard}>
          <Text style={styles.label}>Paste a link</Text>
          <View style={styles.inputWrap}>
            <SymbolView name="link" size={17} tintColor={Colors.light.placeholder} />
            <TextInput autoCapitalize="none" autoCorrect={false} keyboardType="url" onChangeText={setUrl} onSubmitEditing={() => void save()} placeholder="youtube.com, tiktok.com, any page" placeholderTextColor={Colors.light.placeholder} returnKeyType="done" style={styles.input} value={url} />
          </View>
          <Pressable disabled={isSaving} onPress={() => void save()} style={({ pressed }) => [styles.saveButton, (pressed || isSaving) && styles.pressed]}>
            <Text style={styles.saveText}>{isSaving ? 'Saving…' : 'Save to Snag'}</Text><SymbolView name="arrow.up.right" size={15} tintColor="#FFFFFF" weight="bold" />
          </Pressable>
        </View>

        <View style={styles.shareNote}>
          <View style={styles.shareIcon}><SymbolView name="square.and.arrow.up" size={17} tintColor={Colors.light.accent} /></View>
          <View style={styles.shareCopy}><Text style={styles.shareTitle}>The fast way is the Share Sheet</Text><Text style={styles.shareText}>From TikTok, Safari, Instagram, or YouTube, tap Share, then choose Snag.</Text></View>
        </View>
        <Text style={styles.footnote}>Manual paste is here whenever you need it.</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: { backgroundColor: Colors.light.background, flex: 1 },
  content: { backgroundColor: Colors.light.background, flexGrow: 1, gap: 26, justifyContent: 'center', padding: Spacing.four, paddingBottom: 42 },
  heading: { gap: 8 },
  icon: { alignItems: 'center', backgroundColor: Colors.light.accentSoft, borderCurve: 'continuous', borderRadius: 18, height: 46, justifyContent: 'center', marginBottom: 8, width: 46 },
  eyebrow: { color: Colors.light.accent, fontSize: 11, fontWeight: '800', letterSpacing: 1.7 },
  title: { color: Colors.light.text, fontSize: 34, fontWeight: '700', letterSpacing: -1.35, lineHeight: 38 },
  subtitle: { color: Colors.light.muted, fontSize: 16, lineHeight: 23, maxWidth: 335 },
  formCard: { backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.extraLarge, borderWidth: 1, gap: 12, padding: 18 },
  label: { color: Colors.light.text, fontSize: 13, fontWeight: '800' },
  inputWrap: { alignItems: 'center', backgroundColor: Colors.light.background, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.medium, borderWidth: 1, flexDirection: 'row', gap: 9, paddingHorizontal: 13 },
  input: { color: Colors.light.text, flex: 1, fontSize: 15, paddingVertical: 14 },
  saveButton: { alignItems: 'center', backgroundColor: Colors.light.text, borderCurve: 'continuous', borderRadius: Radius.medium, flexDirection: 'row', gap: 8, justifyContent: 'center', marginTop: 2, paddingVertical: 15 },
  saveText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  shareNote: { alignItems: 'flex-start', backgroundColor: Colors.light.wash, borderCurve: 'continuous', borderRadius: Radius.large, flexDirection: 'row', gap: 12, padding: 15 },
  shareIcon: { alignItems: 'center', backgroundColor: Colors.light.surface, borderRadius: 999, height: 32, justifyContent: 'center', width: 32 },
  shareCopy: { flex: 1, gap: 3 }, shareTitle: { color: Colors.light.text, fontSize: 14, fontWeight: '800' }, shareText: { color: Colors.light.muted, fontSize: 13, lineHeight: 19 },
  footnote: { color: Colors.light.placeholder, fontSize: 12, textAlign: 'center' },
  pressed: { opacity: 0.72, transform: [{ scale: 0.985 }] },
});
