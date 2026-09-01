type SharedPayload = { shareType: string; value?: string };

function usableHttpUrl(value: string): string {
  // The native runtime does not guarantee the browser URL constructor. The
  // OS already provides URL-typed shares, so a compact protocol + host check
  // is both sufficient and portable here.
  return /^https?:\/\/[^\s/?#]+(?:[/?#][^\s]*)?$/i.test(value) ? value : '';
}

/** Extract a usable web link from either a native URL share or copied text. */
export function sharedLinkFrom(payloads: SharedPayload[]): string {
  for (const payload of payloads) {
    if (payload.shareType === 'url') {
      const direct = usableHttpUrl(payload.value?.trim() ?? '');
      if (direct) return direct;
    }
  }
  for (const payload of payloads) {
    const candidate = (payload.value ?? '').match(/https?:\/\/[^\s<>()]+/i)?.[0] ?? '';
    const fromText = usableHttpUrl(candidate.replace(/[.,!?;:]+$/, ''));
    if (fromText) return fromText;
  }
  return '';
}
