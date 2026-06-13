// Mirrors backend/app/task_defaults.py — keep in sync.

import type { TaskType } from "../api/types";

/** §5.2 number of stimulus positions per task type (MOD-2: SRT has 1). */
export const TASK_POSITIONS: Record<TaskType, number> = { SRT: 1, CRT2: 2, CRT3: 3, CRT4: 4 };

/** §5.2 default key mappings, left -> right (MOD-2: SRT uses Space). */
export const DEFAULT_KEY_MAPS: Record<TaskType, string[]> = {
  SRT: ["Space"],
  CRT2: ["ArrowLeft", "ArrowRight"],
  CRT3: ["KeyZ", "KeyX", "KeyC"],
  CRT4: ["KeyZ", "KeyX", "KeyN", "KeyM"],
};

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

/** §5.2 displayed key cap labels. */
export const KEY_LABELS: Record<string, string> = {
  ArrowLeft: "←",
  ArrowRight: "→",
  ArrowUp: "↑",
  ArrowDown: "↓",
  Space: "Space", // MOD-2
  ...Object.fromEntries([...LETTERS].map((c) => [`Key${c}`, c])),
  ...Object.fromEntries(Array.from({ length: 10 }, (_, d) => [`Digit${d}`, String(d)])),
};

/** FR-39: allowed `KeyboardEvent.code` values for `key_map` (letters, digits, arrows). */
export const ALLOWED_KEY_CODES: string[] = [
  ...[...LETTERS].map((c) => `Key${c}`),
  ...Array.from({ length: 10 }, (_, d) => `Digit${d}`),
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Space", // MOD-2
];

export function keyLabel(code: string): string {
  return KEY_LABELS[code] ?? code;
}
