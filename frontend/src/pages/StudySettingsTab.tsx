import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { studiesApi } from "../api/studies";
import type { StudyOut, TaskParams, TaskType } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, SuccessBanner } from "../components/forms";
import TaskParamsEditor, { validateParams } from "../components/TaskParamsEditor";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
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
      <TaskParamsForm study={study} onChange={onChange} />
    </div>
  );
}
