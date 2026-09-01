import { router } from 'expo-router';
import { SymbolView } from 'expo-symbols';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors } from '@/constants/theme';

export function PersistentNav() {
  const insets = useSafeAreaInsets();
  return <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 10) }]}>
    <NavButton icon="bookmark.fill" label="Library" onPress={() => router.replace('/')} />
    <NavButton icon="sparkles" label="Today" onPress={() => router.replace('/actions')} />
    <NavButton icon="bubble.left.and.bubble.right.fill" label="Ask" onPress={() => router.replace('/ask')} />
    <NavButton icon="plus.circle.fill" label="Save" onPress={() => router.replace('/save')} />
  </View>;
}

function NavButton({ icon, label, onPress }: { icon: 'bookmark.fill' | 'sparkles' | 'bubble.left.and.bubble.right.fill' | 'plus.circle.fill'; label: string; onPress: () => void }) {
  return <Pressable accessibilityLabel={label} onPress={onPress} style={({ pressed }) => [styles.button, pressed && styles.pressed]}><SymbolView name={icon} size={20} tintColor={Colors.light.muted} /><Text style={styles.label}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({
  bar: { alignItems: 'flex-end', backgroundColor: Colors.light.surface, borderTopColor: Colors.light.border, borderTopWidth: 1, flexDirection: 'row', justifyContent: 'space-around', paddingTop: 10 },
  button: { alignItems: 'center', gap: 3, minWidth: 70 }, label: { color: Colors.light.muted, fontSize: 11, fontWeight: '700' }, pressed: { opacity: 0.65 },
});
