import { router } from 'expo-router';
import { useIncomingShare } from 'expo-sharing';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { captureAndSave, SnagCaptureError } from '@/lib/snag';
import { sharedLinkFrom } from '@/lib/shared-link';

export default function HandleShareScreen() {
  const { sharedPayloads, clearSharedPayloads } = useIncomingShare();
  const [status, setStatus] = useState<'saving' | 'saved' | 'duplicate' | 'failed'>('saving');
  const [failureMessage, setFailureMessage] = useState('');
  const [savedItemId, setSavedItemId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const sharedUrl = useMemo(() => sharedLinkFrom(sharedPayloads), [sharedPayloads]);

  useEffect(() => {
    let active = true;
    async function saveSharedLink() {
      if (!sharedUrl) { if (active) setStatus('failed'); return; }
      if (active) setFailureMessage('');
      try {
        const result = await captureAndSave(sharedUrl);
        clearSharedPayloads();
        if (active) {
          setSavedItemId(String(result.id));
          setStatus(result.duplicate ? 'duplicate' : 'saved');
        }
      } catch (error) {
        if (active) {
          setFailureMessage(error instanceof SnagCaptureError ? error.message : 'Snag could not save this link.');
          setStatus('failed');
        }
      }
    }
    void saveSharedLink();
    return () => { active = false; };
  }, [attempt, clearSharedPayloads, sharedUrl]);

  return (
    <View style={styles.screen}>
      <View style={styles.card}>
        {status === 'saving' ? <ActivityIndicator color={Colors.light.accent} size="large" /> : null}
        <Text style={styles.title}>{status === 'saving' ? 'Saving to Snag' : status === 'saved' ? 'Saved to your library' : status === 'duplicate' ? 'Already saved' : sharedUrl ? 'Snag could not save this link' : 'Snag needs a link'}</Text>
        <Text style={styles.copy}>{status === 'saving' ? 'Snag is turning this into an idea you can use.' : status === 'saved' ? 'Your note is being organized now.' : status === 'duplicate' ? 'This link is already in your library.' : sharedUrl ? failureMessage || 'Snag could not save this link.' : 'Share a webpage, video link, or text that includes a link.'}</Text>
        {status === 'saved' ? <Pressable onPress={() => router.replace('/')} style={styles.button}><Text style={styles.buttonText}>View library</Text></Pressable> : null}
        {status === 'duplicate' && savedItemId ? <Pressable onPress={() => router.replace(`/item/${savedItemId}`)} style={styles.button}><Text style={styles.buttonText}>Open saved item</Text></Pressable> : null}
        {status === 'failed' && sharedUrl ? <Pressable onPress={() => { setStatus('saving'); setAttempt((value) => value + 1); }} style={styles.button}><Text style={styles.buttonText}>Try again</Text></Pressable> : null}
        {status === 'failed' ? <Pressable onPress={() => router.replace('/save')} style={styles.secondaryButton}><Text style={styles.secondaryButtonText}>Open Save</Text></Pressable> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { alignItems: 'center', backgroundColor: Colors.light.background, flex: 1, justifyContent: 'center', padding: Spacing.four },
  card: { alignItems: 'center', backgroundColor: Colors.light.surface, borderColor: Colors.light.border, borderCurve: 'continuous', borderRadius: Radius.extraLarge, borderWidth: 1, gap: 13, maxWidth: 360, padding: 28 },
  title: { color: Colors.light.text, fontSize: 23, fontWeight: '700', letterSpacing: -0.5, textAlign: 'center' },
  copy: { color: Colors.light.muted, fontSize: 15, lineHeight: 22, textAlign: 'center' },
  button: { backgroundColor: Colors.light.text, borderCurve: 'continuous', borderRadius: Radius.medium, marginTop: 6, paddingHorizontal: 18, paddingVertical: 12 },
  buttonText: { color: '#FFFFFF', fontSize: 14, fontWeight: '700' },
  secondaryButton: { paddingHorizontal: 18, paddingVertical: 8 },
  secondaryButtonText: { color: Colors.light.muted, fontSize: 14, fontWeight: '700' },
});
