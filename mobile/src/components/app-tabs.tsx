import { Tabs } from 'expo-router';
import { SymbolView } from 'expo-symbols';

import { Colors } from '@/constants/theme';

export default function AppTabs() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: Colors.light.background },
        tabBarActiveTintColor: Colors.light.accent,
        tabBarInactiveTintColor: Colors.light.muted,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '700' },
        tabBarStyle: { backgroundColor: Colors.light.surface, borderTopColor: Colors.light.border },
      }}>
      <Tabs.Screen name="index" options={{ tabBarIcon: ({ color, size }) => <SymbolView name="bookmark.fill" size={size} tintColor={color} />, title: 'Library' }} />
      <Tabs.Screen name="actions" options={{ tabBarIcon: ({ color, size }) => <SymbolView name="sparkles" size={size} tintColor={color} />, title: 'Today' }} />
      <Tabs.Screen name="ask" options={{ tabBarIcon: ({ color, size }) => <SymbolView name="bubble.left.and.bubble.right.fill" size={size} tintColor={color} />, title: 'Ask' }} />
      <Tabs.Screen name="save" options={{ tabBarIcon: ({ color, size }) => <SymbolView name="plus.circle.fill" size={size} tintColor={color} />, title: 'Save' }} />
    </Tabs>
  );
}
