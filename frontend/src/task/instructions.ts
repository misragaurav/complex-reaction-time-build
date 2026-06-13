import type { TaskParams } from "../api/types";
import { keyLabel, TASK_POSITIONS } from "./keymap";

/**
 * Substitutes the `{N}`, `{KEYS}`, `{P}`, `{T}` placeholders per §5.3.
 * Mirrors `backend/app/task_defaults.py::render_instructions`.
 */
export function renderInstructions(template: string, params: TaskParams): string {
  const n = TASK_POSITIONS[params.task_type];
  const keys = params.key_map.map(keyLabel).join(" ");
  return template
    .replaceAll("{N}", String(n))
    .replaceAll("{KEYS}", keys)
    .replaceAll("{P}", String(params.practice_trials))
    .replaceAll("{T}", String(params.test_trials));
}
