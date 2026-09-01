import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="item/[id]" options={{ headerBackTitle: 'Library', headerShown: true, headerShadowVisible: false, title: 'Saved idea' }} />
        <Stack.Screen name="item/[id]/transcript" options={{ headerBackTitle: 'Idea', headerShown: true, headerShadowVisible: false, title: 'Transcript' }} />
        <Stack.Screen name="search" options={{ headerBackTitle: 'Library', headerShown: true, headerShadowVisible: false, title: 'Search' }} />
        <Stack.Screen name="topics" options={{ headerBackTitle: 'Library', headerShown: true, headerShadowVisible: false, title: 'Topics' }} />
        <Stack.Screen name="trash" options={{ headerBackTitle: 'Library', headerShown: true, headerShadowVisible: false, title: 'Trash' }} />
      </Stack>
    </>
  );
}
