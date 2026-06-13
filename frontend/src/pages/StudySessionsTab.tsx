import { useCallback, useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { exportsApi } from "../api/exports";
import { participantsApi } from "../api/participants";
import { sessionsApi } from "../api/sessions";
// MOD-5: per-session activate/deactivate helpers imported via sessionsApi.
import type {
  ParticipantOut,
  SessionCreateRequest,
  SessionOut,
  SessionSort,
  SessionStatus,
  StudyOut,
  TaskParams,
  TaskType,
} from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass, SuccessBanner } from "../components/forms";
import TaskParamsEditor, { validateParams } from "../components/TaskParamsEditor";
import { DEFAULT_KEY_MAPS } from "../task/keymap";
import { downloadBlob } from "../utils/download";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  SRT: "Simple reaction time", // MOD-2
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

const STATUS_LABELS: Record<SessionStatus, string> = {
  created: "Not started",
  activated: "Ready",
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
  expired: "Missed",
  cancelled: "Cancelled",
};

const STATUS_BADGE_CLASSES: Record<SessionStatus, string> = {
  created: "bg-gray-100 text-gray-600",
  activated: "bg-green-100 text-green-700",
  in_progress: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  abandoned: "bg-amber-100 text-amber-700",
  expired: "bg-red-100 text-red-600",
  cancelled: "bg-gray-100 text-gray-400",
};

const SORT_OPTIONS: { value: SessionSort; label: string }[] = [
  { value: "participant_code", label: "Participant code" },
  { value: "order_index", label: "Session number" },
  { value: "status", label: "Status" },
  { value: "-created_at", label: "Newest first" },
  { value: "-started_at", label: "Recently started" },
  { value: "-completed_at", label: "Recently completed" },
];

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function AssignSessionsForm({
  study,
  participants,
  onCreated,
}: {
  study: StudyOut;
  participants: ParticipantOut[];
  onCreated: () => void;
}): JSX.Element {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [count, setCount] = useState(1);
  const [overrideEnabled, setOverrideEnabled] = useState(false);
  const [taskType, setTaskType] = useState<TaskType>(study.task_type);
  const [params, setParams] = useState<TaskParams>(study.params);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleParticipant(id: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function changeTaskType(next: TaskType): void {
    setTaskType(next);
    // A different task type means a different number of positions; swap in
    // that type's default key_map so the edited params stay consistent.
    setParams((p) => ({ ...p, task_type: next, key_map: [...DEFAULT_KEY_MAPS[next]] }));
  }

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (selected.size === 0) {
      setError("Select at least one participant.");
      return;
    }
    if (!Number.isInteger(count) || count < 1 || count > 50) {
      setError("Sessions per participant must be between 1 and 50.");
      return;
    }
    if (overrideEnabled) {
      const validationError = validateParams(params, taskType);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    const payload: SessionCreateRequest = { participant_ids: [...selected], count };
    if (overrideEnabled) {
      payload.overrides = { task_type: taskType, params };
    }

    setSubmitting(true);
    try {
      const created = await sessionsApi.create(study.id, payload);
      setSuccess(`Created ${created.length} session${created.length === 1 ? "" : "s"}.`);
      setSelected(new Set());
      setCount(1);
      setOverrideEnabled(false);
      setTaskType(study.task_type);
      setParams(study.params);
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Assign sessions</h2>
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      {participants.length === 0 ? (
        <p className="text-sm text-gray-500">Add participants first (Participants tab).</p>
      ) : (
        <>
          <Field label="Participants">
            <div className="max-h-48 space-y-1 overflow-y-auto rounded border border-gray-200 p-2">
              <label className="flex items-center gap-2 border-b border-gray-100 pb-1 text-sm font-medium text-gray-700">
                <input
                  type="checkbox"
                  checked={selected.size === participants.length && participants.length > 0}
                  onChange={(e) =>
                    setSelected(e.target.checked ? new Set(participants.map((p) => p.id)) : new Set())
                  }
                />
                Select all ({participants.length})
              </label>
              {participants.map((p) => (
                <label key={p.id} className="flex items-center gap-2 font-mono text-sm text-gray-700">
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleParticipant(p.id)} />
                  {p.code}
                  {!p.is_active && <span className="font-sans text-xs text-gray-400">(deactivated)</span>}
                </label>
              ))}
            </div>
          </Field>
          <Field label="Sessions per participant" hint="1–50. Order continues from each participant's last session.">
            <input
              type="number"
              className={inputClass}
              min={1}
              max={50}
              value={count}
              onChange={(e) => setCount(e.target.valueAsNumber || 0)}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={overrideEnabled}
              onChange={(e) => setOverrideEnabled(e.target.checked)}
            />
            Override task type / parameters for these sessions (the study's own settings are unaffected)
          </label>
          {overrideEnabled && (
            <div className="space-y-4 rounded border border-gray-200 p-3">
              <Field label="Task type">
                <select
                  className={selectClass}
                  value={taskType}
                  onChange={(e) => changeTaskType(e.target.value as TaskType)}
                >
                  {(Object.keys(TASK_TYPE_LABELS) as TaskType[]).map((t) => (
                    <option key={t} value={t}>
                      {TASK_TYPE_LABELS[t]}
                    </option>
                  ))}
                </select>
              </Field>
              <TaskParamsEditor params={params} onChange={setParams} />
            </div>
          )}
          <Button type="submit" loading={submitting}>
            Assign sessions
          </Button>
        </>
      )}
    </form>
  );
}

function SessionRow({
  session,
  onChanged,
}: {
  session: SessionOut;
  onChanged: () => void;
}): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState(session.display_label);

  // MOD-3 / MFR-14 / MOD-5: relabel allowed before activation or after expiry.
  const labelEditable = session.status === "created" || session.status === "expired";

  async function saveLabel(): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await sessionsApi.update(session.id, { display_label: labelDraft.trim() });
      setEditingLabel(false);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function act(action: "reset" | "cancel"): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await sessionsApi.update(session.id, { action });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function remove(): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await sessionsApi.remove(session.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function exportCsv(): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      downloadBlob(await exportsApi.sessionCsv(session.id), `session_${session.code}.csv`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // MOD-5: per-session activate/deactivate (MFR-33).
  async function activateSession(): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await sessionsApi.activate(session.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function deactivateSession(): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await sessionsApi.deactivate(session.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  const resettable =
    session.status === "in_progress" || session.status === "completed" || session.status === "abandoned";

  return (
    <>
      <tr className={session.status === "cancelled" ? "opacity-50" : ""}>
        <td className="px-4 py-3 font-mono text-sm text-gray-900">{session.participant_code}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{session.order_index}</td>
        {/* MOD-3: display_label (inline-editable while created/expired) + session type. */}
        <td className="px-4 py-3 text-sm text-gray-700">
          {editingLabel ? (
            <div className="flex items-center gap-1">
              <input
                className={`${inputClass} min-w-[10rem]`}
                value={labelDraft}
                maxLength={80}
                onChange={(e) => setLabelDraft(e.target.value)}
              />
              <Button variant="secondary" onClick={() => void saveLabel()} disabled={busy || labelDraft.trim() === ""}>
                Save
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setEditingLabel(false);
                  setLabelDraft(session.display_label);
                }}
                disabled={busy}
              >
                Cancel
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span>{session.display_label}</span>
              {labelEditable && (
                <button
                  type="button"
                  className="text-xs text-gray-400 underline hover:text-gray-600"
                  onClick={() => {
                    setLabelDraft(session.display_label);
                    setEditingLabel(true);
                  }}
                >
                  Edit
                </button>
              )}
            </div>
          )}
        </td>
        <td className="px-4 py-3 text-sm capitalize text-gray-700">{session.session_type}</td>
        <td className="px-4 py-3 font-mono text-sm text-gray-700">{session.code}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{session.task_type}</td>
        <td className="px-4 py-3">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[session.status]}`}>
            {STATUS_LABELS[session.status]}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-gray-700">{session.attempt}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{formatTimestamp(session.activated_at)}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{formatTimestamp(session.completed_at)}</td>
        <td className="px-4 py-3 text-sm text-gray-700">
          {session.stats.trimmed_mean_rt_ms !== null ? `${session.stats.trimmed_mean_rt_ms.toFixed(1)} ms` : "—"}
        </td>
        <td className="px-4 py-3 text-sm text-gray-700">
          {session.stats.accuracy_pct !== null ? `${session.stats.accuracy_pct.toFixed(1)}%` : "—"}
        </td>
        <td className="px-4 py-3">
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => void exportCsv()} disabled={busy}>
              Export CSV
            </Button>
            {resettable && (
              <Button variant="secondary" onClick={() => void act("reset")} disabled={busy}>
                Reset
              </Button>
            )}
            {/* MOD-5: activate / deactivate per-session. */}
            {(session.status === "created" || session.status === "expired") && (
              <Button variant="secondary" onClick={() => void activateSession()} disabled={busy}>
                Activate
              </Button>
            )}
            {session.status === "activated" && (
              <Button variant="secondary" onClick={() => void deactivateSession()} disabled={busy}>
                Deactivate
              </Button>
            )}
            {/* Cancel allowed for created, activated, and expired (MOD-5). */}
            {(session.status === "created" || session.status === "activated" || session.status === "expired") && (
              <Button variant="secondary" onClick={() => void act("cancel")} disabled={busy}>
                Cancel
              </Button>
            )}
            {session.status === "created" && (
              <Button variant="danger" onClick={() => void remove()} disabled={busy}>
                Delete
              </Button>
            )}
          </div>
        </td>
      </tr>
      {error && (
        <tr>
          <td colSpan={13} className="px-4 pb-3">
            <ErrorBanner message={error} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function StudySessionsTab({ study }: { study: StudyOut }): JSX.Element {
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [participants, setParticipants] = useState<ParticipantOut[]>([]);
  const [statusFilter, setStatusFilter] = useState<SessionStatus | "">("");
  const [participantFilter, setParticipantFilter] = useState("");
  const [sort, setSort] = useState<SessionSort>("participant_code");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback((): void => {
    sessionsApi
      .list(study.id, {
        status: statusFilter === "" ? undefined : statusFilter,
        participantId: participantFilter === "" ? undefined : participantFilter,
        sort,
      })
      .then(setSessions)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id, statusFilter, participantFilter, sort]);

  useEffect(() => {
    setError(null);
    reload();
  }, [reload]);

  useEffect(() => {
    participantsApi
      .list(study.id)
      .then(setParticipants)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id]);

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      <div className="flex flex-wrap items-end gap-4">
        <Field label="Status">
          <select
            className={selectClass}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as SessionStatus | "")}
          >
            <option value="">All</option>
            {(Object.keys(STATUS_LABELS) as SessionStatus[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Participant">
          <select className={selectClass} value={participantFilter} onChange={(e) => setParticipantFilter(e.target.value)}>
            <option value="">All</option>
            {participants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Sort by">
          <select className={selectClass} value={sort} onChange={(e) => setSort(e.target.value as SessionSort)}>
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      {!sessions ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-gray-500">No sessions match.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">Participant</th>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Label</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Task</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Attempt</th>
                <th className="px-4 py-3">Activated</th>
                <th className="px-4 py-3">Completed</th>
                <th className="px-4 py-3">Trimmed mean RT</th>
                <th className="px-4 py-3">Accuracy</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {sessions.map((s) => (
                <SessionRow key={s.id} session={s} onChanged={reload} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {study.is_archived ? (
        <p className="text-sm text-gray-500">This study is archived; new sessions cannot be created.</p>
      ) : (
        <AssignSessionsForm study={study} participants={participants} onCreated={reload} />
      )}
    </div>
  );
}
