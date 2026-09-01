import { Image } from 'expo-image';
import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { Radius } from '@/constants/theme';
import { type SnagItem } from '@/lib/snag';

export function SourcePreview({ item, size = 'hero' }: { item: SnagItem; size?: 'card' | 'hero' | 'reader' }) {
  return <View style={[styles.frame, size === 'card' ? styles.card : size === 'reader' ? styles.reader : styles.hero, fallback(item.sourceType)]}>
    {item.thumbnailUrl ? <Image cachePolicy="memory-disk" contentFit="cover" recyclingKey={item.thumbnailUrl} source={{ uri: item.thumbnailUrl }} style={styles.image} transition={180} /> : <View style={styles.fallback}><SymbolView name={item.sourceType === 'YouTube' ? 'play.rectangle.fill' : item.sourceType === 'TikTok' ? 'play.fill' : 'doc.text.fill'} size={size === 'card' ? 22 : 34} tintColor="#FFFFFF" /><Text style={styles.fallbackText}>{item.sourceType}</Text></View>}
  </View>;
}

function fallback(source: SnagItem['sourceType']) { return source === 'YouTube' ? styles.youtube : source === 'TikTok' ? styles.tiktok : styles.web; }

const styles = StyleSheet.create({
  frame: { overflow: 'hidden' }, card: { height: 92 }, hero: { borderCurve: 'continuous', borderRadius: Radius.large, height: 200 }, reader: { borderCurve: 'continuous', borderRadius: Radius.large, height: 142 }, image: { height: '100%', width: '100%' }, fallback: { alignItems: 'center', flex: 1, gap: 8, justifyContent: 'center' }, fallbackText: { color: 'rgba(255,255,255,0.82)', fontSize: 12, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' }, youtube: { backgroundColor: '#B8463B' }, tiktok: { backgroundColor: '#303233' }, web: { backgroundColor: '#486F63' },
});
