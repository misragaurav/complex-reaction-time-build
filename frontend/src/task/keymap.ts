// Mirrors backend/app/task_defaults.py — keep in sync.

import type { TaskType } from "../api/types";

/** §5.2 number of stimulus positions per task type. */
export const TASK_POSITIONS: Record<TaskType, number> = { CRT2: 2, CRT3: 3, CRT4: 4 };

/** §5.2 default key mappings, left -> right. */
export const DEFAULT_KEY_MAPS: Record<TaskType, string[]> = {
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
];

export function keyLabel(code: string): string {
  return KEY_LABELS[code] ?? code;
}
