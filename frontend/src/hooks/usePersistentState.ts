import { useEffect, useState } from "react";

/**
 * MFR-136: Like useState but backed by localStorage.
 *
 * - Reads the stored value on first mount (guarded with try/catch per MFR-134).
 * - Writes every state change back to localStorage.
 * - If `validate` is provided, the parsed value is passed through it; a `null`
 *   return means "invalid — use the initial default" (MFR-135).
 * - Parse failure or a missing entry falls back to `initial` and (best-effort)
 *   removes the corrupt entry (MFR-134).
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
  options?: {
    validate?: (raw: unknown) => T | null;
  },
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return initial;
      const parsed: unknown = JSON.parse(raw);
      if (options?.validate) {
        const validated = options.validate(parsed);
        return validated !== null ? validated : initial;
      }
      return parsed as T;
    } catch {
      // MFR-134: non-JSON or other error — clear the corrupt entry and use default.
      try {
        localStorage.removeItem(key);
      } catch {
        /* ignore storage errors */
      }
      return initial;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch {
      /* MFR-134: ignore write errors (e.g. storage quota) */
    }
  }, [key, state]);

  return [state, setState];
}
