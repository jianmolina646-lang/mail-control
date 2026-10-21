// Prefer missing an ambiguous candidate to turning prose into a credential.
export function extractCodes(text: string): string[] {
  const candidates: string[] = [];
  const labeled = /\b(?:c[oó]digo|code|pin)(?:\s+(?:de\s+(?:verificaci[oó]n|acceso|inicio de sesi[oó]n)|verification))?(?:\s+(?:es|is))?\s*[:：=–-]?\s*([A-Z0-9]{4,10})(?![A-Z0-9])/gi;
  for (const match of text.matchAll(labeled)) {
    const value = match[1]!;
    if (!/\d/.test(value) || /^(?:19|20)\d{2}$/.test(value)) continue;
    if (/[a-z]/.test(value) && /[a-z]/i.test(value)) continue;
    const after = text.slice((match.index ?? 0) + match[0].length);
    if (/^\s*(?:minutos?|minutes?|horas?|hours?|segundos?|seconds?)\b/i.test(after)) continue;
    candidates.push(value);
  }
  // Numeric codes isolated on their own line are common in transactional email.
  if (/\b(?:c[oó]digo|code|pin)\b/i.test(text)) {
    for (const match of text.matchAll(/^\s*(\d{4,8})\s*$/gm)) {
      if (!/^(?:19|20)\d{2}$/.test(match[1]!)) candidates.push(match[1]!);
    }
  }
  return [...new Set(candidates)].slice(0, 4);
}
