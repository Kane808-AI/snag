import { getSharedPayloads } from 'expo-sharing';

export async function redirectSystemPath({ path }: { path: string; initial: boolean }) {
  try {
    // React Native does not guarantee the browser URL constructor. Keep this
    // native share route dependency-free so a cold app launch is reliable.
    if (/^snag:\/\/expo-sharing(?:[/?#]|$)/i.test(path) && getSharedPayloads().length > 0) {
      return '/handle-share';
    }
    return path;
  } catch {
    return '/';
  }
}
