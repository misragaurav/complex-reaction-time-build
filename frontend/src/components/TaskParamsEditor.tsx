import type { TaskParams, TaskType } from "../api/types";
import { ALLOWED_KEY_CODES, keyLabel, TASK_POSITIONS } from "../task/keymap";
import { Field, inputClass, selectClass } from "./forms";

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max?: number;
  onChange: (value: number) => void;
}): JSX.Element {
  return (
    <Field label={label} hint={max !== undefined ? `${min}–${max}` : `≥ ${min}`}>
      <input
        type="number"
        className={inputClass}
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.valueAsNumber || 0)}
      />
    </Field>
  );
}

function BoolField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}): JSX.Element {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-700">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

function KeyMapEditor({ keyMap, onChange }: { keyMap: string[]; onChange: (keyMap: string[]) => void }): JSX.Element {
  return (
    <Field label="Key mapping" hint="One physical key per stimulus position, left to right. Each key must be unique.">
      <div className="flex flex-wrap gap-2">
        {keyMap.map((code, i) => (
          <select
            key={i}
            className={selectClass}
            value={code}
            onChange={(e) => {
              const next = [...keyMap];
              next[i] = e.target.value;
              onChange(next);
            }}
          >
            {ALLOWED_KEY_CODES.map((c) => (
              <option key={c} value={c}>
                {keyLabel(c)} ({c})
              </option>
            ))}
          </select>
        ))}
      </div>
    </Field>
  );
}

/** Catches the cross-field/array constraints from §5.4 with a friendlier
 * message than the raw 422 response; per-field min/max are still enforced
 * server-side and surfaced via `errorMessage` if missed here. */
export function validateParams(params: TaskParams, taskType: TaskType): string | null {
  if (params.foreperiod_min_ms > params.foreperiod_max_ms) {
    return "Foreperiod minimum must be less than or equal to the foreperiod maximum.";
  }
  if (params.outlier_high_ms <= params.outlier_low_ms) {
    return "Outlier high threshold must be greater than the outlier low threshold.";
  }
  const expected = TASK_POSITIONS[taskType];
  if (params.key_map.length !== expected) {
    return `Key mapping must have exactly ${expected} keys for this task type.`;
  }
  if (new Set(params.key_map).size !== params.key_map.length) {
    return "Key mapping entries must be unique.";
  }
  return null;
}

/** Controlled grid of all §5.4 task-parameter inputs (everything except
 * `task_type`, which each caller renders per its own mutability rules). */
export default function TaskParamsEditor({
  params,
  onChange,
  disabled = false,
}: {
  params: TaskParams;
  onChange: (params: TaskParams) => void;
  disabled?: boolean;
}): JSX.Element {
  const set = <K extends keyof TaskParams>(key: K, value: TaskParams[K]): void =>
    onChange({ ...params, [key]: value });

  return (
    <fieldset disabled={disabled} className="grid grid-cols-1 gap-4 disabled:opacity-60 sm:grid-cols-2">
      <NumberField
        label="Practice trials"
        value={params.practice_trials}
        min={0}
        max={50}
        onChange={(v) => set("practice_trials", v)}
      />
      <NumberField
        label="Test trials"
        value={params.test_trials}
        min={1}
        max={500}
        onChange={(v) => set("test_trials", v)}
      />
      <NumberField
        label="Foreperiod minimum (ms)"
        value={params.foreperiod_min_ms}
        min={200}
        max={10000}
        onChange={(v) => set("foreperiod_min_ms", v)}
      />
      <NumberField
        label="Foreperiod maximum (ms)"
        value={params.foreperiod_max_ms}
        min={200}
        max={10000}
        onChange={(v) => set("foreperiod_max_ms", v)}
      />
      <NumberField
        label="Response timeout (ms)"
        value={params.response_timeout_ms}
        min={500}
        max={10000}
        onChange={(v) => set("response_timeout_ms", v)}
      />
      <NumberField
        label="Inter-trial interval (ms)"
        value={params.iti_ms}
        min={0}
        max={5000}
        onChange={(v) => set("iti_ms", v)}
      />
      <NumberField
        label="Feedback duration (ms)"
        value={params.feedback_duration_ms}
        min={100}
        max={3000}
        onChange={(v) => set("feedback_duration_ms", v)}
      />
      <NumberField
        label="Max consecutive position repeats"
        value={params.max_consecutive_repeats}
        min={1}
        max={10}
        onChange={(v) => set("max_consecutive_repeats", v)}
      />
      <NumberField
        label="Outlier low (ms)"
        value={params.outlier_low_ms}
        min={0}
        onChange={(v) => set("outlier_low_ms", v)}
      />
      <NumberField
        label="Outlier high (ms)"
        value={params.outlier_high_ms}
        min={params.outlier_low_ms + 1}
        onChange={(v) => set("outlier_high_ms", v)}
      />
      <BoolField label="Show progress bar during trials" checked={params.show_progress} onChange={(v) => set("show_progress", v)} />
      <BoolField
        label="Show feedback during practice"
        checked={params.practice_feedback}
        onChange={(v) => set("practice_feedback", v)}
      />
      <div className="sm:col-span-2">
        <KeyMapEditor keyMap={params.key_map} onChange={(km) => set("key_map", km)} />
      </div>
      <div className="sm:col-span-2">
        <Field
          label="Instructions text"
          hint="Placeholders: {N} positions, {KEYS} key labels, {P} practice trials, {T} test trials. Up to 2000 characters."
        >
          <textarea
            className={inputClass}
            rows={4}
            maxLength={2000}
            value={params.instructions_text}
            onChange={(e) => set("instructions_text", e.target.value)}
          />
        </Field>
      </div>
    </fieldset>
  );
}
