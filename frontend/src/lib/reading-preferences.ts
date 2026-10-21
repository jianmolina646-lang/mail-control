import { useState } from "react";

export function readPreference<T extends string | number | boolean>(key: string, fallback: T, allowed: readonly T[]): T {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(`mail-reading:${key}`) ?? "null");
    return allowed.includes(value as T) ? value as T : fallback;
  } catch { return fallback; }
}

// Store appearance only: never messages, email addresses or search queries.
export function useReadingPreference<T extends string | number | boolean>(key: string, fallback: T, allowed: readonly T[]) {
  const [value, setValue] = useState<T>(() => readPreference(key, fallback, allowed));
  const update = (next: T) => {
    if (!allowed.includes(next)) return;
    setValue(next);
    try { localStorage.setItem(`mail-reading:${key}`, JSON.stringify(next)); } catch { /* Private browsing can disable storage. */ }
  };
  return [value, update] as const;
}
