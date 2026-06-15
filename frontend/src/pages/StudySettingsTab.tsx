import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { studiesApi } from "../api/studies";
import type { StudyOut, TaskParams, TaskType } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass, SuccessBanner } from "../components/forms";
import TaskParamsEditor, { validateParams } from "../components/TaskParamsEditor";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  SRT: "Simple reaction time", // MOD-2
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

function StudyDetailsForm({ study, onChange }: { study: StudyOut; onChange: (study: StudyOut) => void }): JSX.Element {
  const [name, setName] = useState(study.name);
  const [description, setDescription] = useState(study.description ?? "");
  const [archived, setArchived] = useState(study.is_archived);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const updated = await studiesApi.update(study.id, {
        name: name.trim(),
        description: description.trim() ? description.trim() : null,
        is_archived: archived,
      });
      onChange(updated);
      setSuccess("Saved.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Study details</h2>
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      <Field label="Name">
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          required
        />
      </Field>
      <Field label="Description" hint="Optional, up to 2000 characters.">
        <textarea
          className={inputClass}
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
        />
      </Field>
      <Field label="Task type">
        <input
          className={`${inputClass} bg-gray-100 text-gray-500`}
          value={TASK_TYPE_LABELS[study.task_type]}
          disabled
          readOnly
        />
      </Field>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
        Archived (hidden from the default studies list and blocks new sessions; existing data is retained and
        remains exportable)
      </label>
      <Button type="submit" loading={saving}>
        Save
      </Button>
    </form>
  );
}

function TaskParamsForm({ study, onChange }: { study: StudyOut; onChange: (study: StudyOut) => void }): JSX.Element {
  const [params, setParams] = useState<TaskParams>(study.params);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const locked = study.params_locked;

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    const validationError = validateParams(params, study.task_type);
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    try {
      const updated = await studiesApi.update(study.id, { params });
      setParams(updated.params);
      onChange(updated);
      setSuccess("Saved.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Task parameters</h2>
      {locked && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          At least one session has started for this study, so parameters are now read-only. Each session
          stores its own snapshot of the parameters in effect when it was created, so historical data is
          unaffected.
        </div>
      )}
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      <TaskParamsEditor params={params} onChange={setParams} disabled={locked} />
      {!locked && (
        <Button type="submit" loading={saving}>
          Save parameters
        </Button>
      )}
    </form>
  );
}

function ProtocolConfigForm({
  study,
  onChange,
}: {
  study: StudyOut;
  onChange: (study: StudyOut) => void;
}): JSX.Element {
  const [num, setNum] = useState(study.num_intervention_sessions);
  const [perWeek, setPerWeek] = useState(study.sessions_per_week);
  const [taskType, setTaskType] = useState<TaskType>(study.task_type_pre);
  const [warnDismissed, setWarnDismissed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const locked = study.protocol_locked;
  const hasInconsistentTypes =
    study.task_type_onboarding !== study.task_type_pre ||
    study.task_type_pre !== study.task_type_post;

  const multipleOfError =
    perWeek > 0 && num % perWeek !== 0
      ? `Intervention sessions (${num}) must be a multiple of sessions per week (${perWeek}).`
      : null;

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (multipleOfError) {
      setError(multipleOfError);
      return;
    }
    setSaving(true);
    try {
      const updated = await studiesApi.update(study.id, {
        num_intervention_sessions: num,
        sessions_per_week: perWeek,
        task_type_onboarding: taskType,
        task_type_pre: taskType,
        task_type_post: taskType,
      });
      onChange(updated);
      setSuccess("Saved.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Protocol</h2>
      {locked && (
        <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Protocol sessions have been generated for this study, so the protocol configuration is now
          read-only.
        </div>
      )}
      {hasInconsistentTypes && !locked && !warnDismissed && (
        <div className="flex items-start justify-between gap-2 rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          <span>
            This study's task types were previously configured differently across session phases.
            The value shown below will be applied to all phases when you save.
          </span>
          <button
            type="button"
            className="shrink-0 text-blue-600 hover:text-blue-800"
            onClick={() => setWarnDismissed(true)}
          >
            ×
          </button>
        </div>
      )}
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Intervention sessions" hint="1–156. Must be a multiple of sessions per week.">
          <input
            type="number"
            className={`${inputClass}${locked ? " bg-gray-100 text-gray-500" : ""}`}
            min={1}
            max={156}
            value={num}
            disabled={locked}
            onChange={(e) => setNum(e.target.valueAsNumber || 0)}
          />
        </Field>
        <Field label="Sessions per week" hint="1–7. Determines the week/day mapping.">
          <input
            type="number"
            className={`${inputClass}${locked ? " bg-gray-100 text-gray-500" : ""}`}
            min={1}
            max={7}
            value={perWeek}
            disabled={locked}
            onChange={(e) => setPerWeek(e.target.valueAsNumber || 0)}
          />
        </Field>
        <Field label="Task type">
          <select
            className={`${selectClass}${locked ? " bg-gray-100 text-gray-500" : ""}`}
            value={taskType}
            disabled={locked}
            onChange={(e) => setTaskType(e.target.value as TaskType)}
          >
            {(Object.keys(TASK_TYPE_LABELS) as TaskType[]).map((t) => (
              <option key={t} value={t}>
                {TASK_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </Field>
      </div>
      {multipleOfError && <p className="text-sm text-red-600">{multipleOfError}</p>}
      {!locked && (
        <Button type="submit" loading={saving} disabled={multipleOfError !== null}>
          Save protocol
        </Button>
      )}
    </form>
  );
}

export default function StudySettingsTab({
  study,
  onChange,
}: {
  study: StudyOut;
  onChange: (study: StudyOut) => void;
}): JSX.Element {
  return (
    <div className="max-w-3xl space-y-6">
      <StudyDetailsForm study={study} onChange={onChange} />
      <ProtocolConfigForm study={study} onChange={onChange} />
      <TaskParamsForm study={study} onChange={onChange} />
    </div>
  );
}
