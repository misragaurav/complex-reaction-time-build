import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { studiesApi } from "../api/studies";
import type { StudyCreate, StudyOut, TaskType } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass } from "../components/forms";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  SRT: "Simple reaction time", // MOD-2
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

function CreateStudyForm({ onCreated }: { onCreated: (study: StudyOut) => void }): JSX.Element {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("CRT2");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const payload: StudyCreate = { name: name.trim(), task_type: taskType };
      if (description.trim()) payload.description = description.trim();
      const study = await studiesApi.create(payload);
      onCreated(study);
      setName("");
      setDescription("");
      setTaskType("CRT2");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="space-y-4 rounded-lg border border-gray-200 bg-white p-4"
    >
      <h2 className="text-base font-semibold text-gray-900">Create study</h2>
      <ErrorBanner message={error} />
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
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
        />
      </Field>
      <Field
        label="Task type"
        hint="Determines the number of stimulus positions and default key mapping. Cannot be changed after creation. Parameters can be customized afterwards."
      >
        <select className={selectClass} value={taskType} onChange={(e) => setTaskType(e.target.value as TaskType)}>
          {(Object.keys(TASK_TYPE_LABELS) as TaskType[]).map((t) => (
            <option key={t} value={t}>
              {TASK_TYPE_LABELS[t]}
            </option>
          ))}
        </select>
      </Field>
      <Button type="submit" loading={submitting}>
        Create study
      </Button>
    </form>
  );
}

export default function StudiesListPage(): JSX.Element {
  const [studies, setStudies] = useState<StudyOut[] | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStudies(null);
    setError(null);
    studiesApi
      .list(showArchived)
      .then(setStudies)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [showArchived]);

  function handleCreated(study: StudyOut): void {
    setError(null);
    if (!showArchived) {
      setStudies((prev) => (prev ? [study, ...prev] : [study]));
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Studies</h1>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Show archived
        </label>
      </div>

      <ErrorBanner message={error} />

      {!studies ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : studies.length === 0 ? (
        <p className="text-sm text-gray-500">{showArchived ? "No archived studies." : "No studies yet."}</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {studies.map((study) => (
            <li key={study.id} className="flex items-center justify-between gap-4 px-4 py-4">
              <div>
                <p className="font-medium text-gray-900">
                  <Link to={`/studies/${study.id}`} className="hover:underline">
                    {study.name}
                  </Link>
                  {study.is_archived && (
                    <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                      Archived
                    </span>
                  )}
                </p>
                <p className="text-sm text-gray-500">{TASK_TYPE_LABELS[study.task_type]}</p>
              </div>
              <div className="text-right text-sm text-gray-500">
                <p>{study.counts.participants} participants</p>
                <p>
                  {study.counts.sessions_completed}/{study.counts.sessions_total} sessions complete (
                  {study.counts.completion_pct.toFixed(0)}%)
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <CreateStudyForm onCreated={handleCreated} />
    </div>
  );
}
