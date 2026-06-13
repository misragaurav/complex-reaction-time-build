import { useCallback, useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { exportsApi } from "../api/exports";
import { groupsApi } from "../api/groups";
import { participantsApi } from "../api/participants";
import { studiesApi } from "../api/studies";
import type { GroupOut, ParticipantCreate, ParticipantOut, StudyOut, TaskType } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass, SuccessBanner } from "../components/forms";
import { downloadBlob } from "../utils/download";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  SRT: "Simple reaction time",
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

const CUSTOM_CODE_RE = /^[A-Za-z0-9_-]{3,32}$/;

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function AddParticipantsForm({
  studyId,
  onCreated,
}: {
  studyId: string;
  onCreated: (created: ParticipantOut[]) => void;
}): JSX.Element {
  const [mode, setMode] = useState<"bulk" | "manual">("bulk");
  const [count, setCount] = useState(10);
  const [prefix, setPrefix] = useState("");
  const [codesText, setCodesText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createdCodes, setCreatedCodes] = useState<string[] | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setCreatedCodes(null);

    let payload: ParticipantCreate;
    if (mode === "bulk") {
      if (!Number.isInteger(count) || count < 1 || count > 500) {
        setError("Count must be between 1 and 500.");
        return;
      }
      payload = prefix.trim() ? { count, prefix: prefix.trim() } : { count };
    } else {
      const codes = codesText
        .split(/[\s,]+/)
        .map((c) => c.trim())
        .filter((c) => c !== "");
      if (codes.length === 0) {
        setError("Enter at least one code.");
        return;
      }
      const bad = codes.find((c) => !CUSTOM_CODE_RE.test(c));
      if (bad) {
        setError(`Code "${bad}" is invalid: 3–32 characters, letters/digits/underscore/hyphen only.`);
        return;
      }
      payload = { codes };
    }

    setSubmitting(true);
    try {
      const created = await participantsApi.create(studyId, payload);
      onCreated(created);
      setCreatedCodes(created.map((p) => p.code));
      setCodesText("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Add participants</h2>
      <div className="flex gap-4">
        {(["bulk", "manual"] as const).map((m) => (
          <label key={m} className="flex items-center gap-2 text-sm text-gray-700">
            <input type="radio" name="participant-mode" checked={mode === m} onChange={() => setMode(m)} />
            {m === "bulk" ? "Generate codes" : "Enter custom codes"}
          </label>
        ))}
      </div>
      <ErrorBanner message={error} />
      {createdCodes && (
        <div className="space-y-2">
          <SuccessBanner
            message={`Created ${createdCodes.length} participant${createdCodes.length === 1 ? "" : "s"}.`}
          />
          <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-sm text-gray-800">
            {createdCodes.join(", ")}
          </div>
        </div>
      )}
      {mode === "bulk" ? (
        <div className="flex flex-wrap gap-4">
          <Field label="Count" hint="1–500">
            <input
              type="number"
              className={inputClass}
              min={1}
              max={500}
              value={count}
              onChange={(e) => setCount(e.target.valueAsNumber || 0)}
            />
          </Field>
          <Field label="Code prefix" hint="Optional, e.g. PILOT → PILOT-A7F3">
            <input className={inputClass} value={prefix} onChange={(e) => setPrefix(e.target.value)} maxLength={20} />
          </Field>
        </div>
      ) : (
        <Field label="Codes" hint="Separate with spaces, commas, or new lines. 3–32 characters each: letters, digits, _ or -.">
          <textarea className={inputClass} rows={3} value={codesText} onChange={(e) => setCodesText(e.target.value)} />
        </Field>
      )}
      <Button type="submit" loading={submitting}>
        Add participants
      </Button>
    </form>
  );
}

function ParticipantRow({
  participant,
  onUpdated,
  selected,
  onToggleSelect,
}: {
  participant: ParticipantOut;
  onUpdated: (participant: ParticipantOut) => void;
  selected: boolean;
  onToggleSelect: () => void;
}): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggleActive(): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      onUpdated(await participantsApi.update(participant.id, { is_active: !participant.is_active }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      onUpdated(await participantsApi.update(participant.id, { reset_password: true }));
      setSuccess("Password cleared — the participant will set a new one at next login.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv(): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      downloadBlob(await exportsApi.participantCsv(participant.id), `participant_${participant.code}.csv`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr className={participant.is_active ? "" : "opacity-50"}>
        <td className="px-4 py-3">
          <input type="checkbox" checked={selected} onChange={onToggleSelect} />
        </td>
        <td className="px-4 py-3 font-mono text-sm text-gray-900">{participant.code}</td>
        {/* MOD-4: group assignment. */}
        <td className="px-4 py-3 text-sm text-gray-700">{participant.group_name ?? "Unassigned"}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{participant.password_set ? "Set" : "Not set"}</td>
        <td className="px-4 py-3 text-sm text-gray-700">
          {participant.sessions_completed}/{participant.sessions_assigned}
        </td>
        <td className="px-4 py-3 text-sm text-gray-700">{formatTimestamp(participant.last_login_at)}</td>
        <td className="px-4 py-3 text-sm text-gray-700">{participant.is_active ? "Active" : "Deactivated"}</td>
        <td className="px-4 py-3">
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => void exportCsv()} disabled={busy}>
              Export CSV
            </Button>
            {participant.password_set && (
              <Button variant="secondary" onClick={() => void resetPassword()} disabled={busy}>
                Reset password
              </Button>
            )}
            <Button variant={participant.is_active ? "danger" : "secondary"} onClick={() => void toggleActive()} disabled={busy}>
              {participant.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          </div>
        </td>
      </tr>
      {(error || success) && (
        <tr>
          <td colSpan={8} className="px-4 pb-3">
            <ErrorBanner message={error} />
            <SuccessBanner message={success} />
          </td>
        </tr>
      )}
    </>
  );
}

function GenerateProtocolForm({
  study,
  participants,
  onGenerated,
}: {
  study: StudyOut;
  participants: ParticipantOut[];
  onGenerated: () => void;
}): JSX.Element {
  const [num, setNum] = useState(study.num_intervention_sessions);
  const [weekStart, setWeekStart] = useState(1);
  const [ttOnboarding, setTtOnboarding] = useState<TaskType>(study.task_type_onboarding);
  const [ttPre, setTtPre] = useState<TaskType>(study.task_type_pre);
  const [ttPost, setTtPost] = useState<TaskType>(study.task_type_post);
  // Default selection: participants who do not yet have any sessions.
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(participants.filter((p) => p.sessions_assigned === 0).map((p) => p.id)),
  );
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const multipleOfError =
    study.sessions_per_week > 0 && num % study.sessions_per_week !== 0
      ? `Intervention sessions (${num}) must be a multiple of sessions per week (${study.sessions_per_week}).`
      : null;

  function toggle(id: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    if (multipleOfError) {
      setError(multipleOfError);
      return;
    }
    if (selected.size === 0) {
      setError("Select at least one participant.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await studiesApi.generateProtocol(study.id, {
        participant_ids: [...selected],
        num_intervention_sessions: num,
        week_start: weekStart,
        task_type_onboarding: ttOnboarding,
        task_type_pre: ttPre,
        task_type_post: ttPost,
      });
      const createdCount = res.created.length;
      const skippedCount = res.skipped.length;
      setSuccess(
        `Generated protocol for ${createdCount} participant${createdCount === 1 ? "" : "s"}` +
          (skippedCount > 0 ? `; skipped ${skippedCount} (already had sessions).` : "."),
      );
      onGenerated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const selectFor = (value: TaskType, onSet: (t: TaskType) => void): JSX.Element => (
    <select className={selectClass} value={value} onChange={(e) => onSet(e.target.value as TaskType)}>
      {(Object.keys(TASK_TYPE_LABELS) as TaskType[]).map((t) => (
        <option key={t} value={t}>
          {TASK_TYPE_LABELS[t]}
        </option>
      ))}
    </select>
  );

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Generate protocol sessions</h2>
      <p className="text-sm text-gray-500">
        Creates the onboarding session plus a pre/post pair per intervention session for each selected
        participant. Participants who already have sessions are skipped.
      </p>
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Intervention sessions" hint="Must be a multiple of sessions per week.">
          <input
            type="number"
            className={inputClass}
            min={1}
            max={156}
            value={num}
            onChange={(e) => setNum(e.target.valueAsNumber || 0)}
          />
        </Field>
        <Field label="Week start" hint="Week number of the first intervention session.">
          <input
            type="number"
            className={inputClass}
            min={1}
            max={52}
            value={weekStart}
            onChange={(e) => setWeekStart(e.target.valueAsNumber || 0)}
          />
        </Field>
        <Field label="Onboarding task type">{selectFor(ttOnboarding, setTtOnboarding)}</Field>
        <Field label="Pre task type">{selectFor(ttPre, setTtPre)}</Field>
        <Field label="Post task type">{selectFor(ttPost, setTtPost)}</Field>
      </div>
      {multipleOfError && <p className="text-sm text-red-600">{multipleOfError}</p>}
      <Field label="Participants">
        <div className="max-h-48 space-y-1 overflow-y-auto rounded border border-gray-200 p-2">
          <label className="flex items-center gap-2 border-b border-gray-100 pb-1 text-sm font-medium text-gray-700">
            <input
              type="checkbox"
              checked={selected.size === participants.length && participants.length > 0}
              onChange={(e) => setSelected(e.target.checked ? new Set(participants.map((p) => p.id)) : new Set())}
            />
            Select all ({participants.length})
          </label>
          {participants.map((p) => (
            <label key={p.id} className="flex items-center gap-2 font-mono text-sm text-gray-700">
              <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
              {p.code}
              {p.sessions_assigned > 0 && (
                <span className="font-sans text-xs text-gray-400">(has sessions)</span>
              )}
            </label>
          ))}
        </div>
      </Field>
      <Button type="submit" loading={submitting} disabled={multipleOfError !== null}>
        Generate
      </Button>
    </form>
  );
}

export default function StudyParticipantsTab({ study }: { study: StudyOut }): JSX.Element {
  const [participants, setParticipants] = useState<ParticipantOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  // MOD-4: group assignment state.
  const [groups, setGroups] = useState<GroupOut[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [assignGroupId, setAssignGroupId] = useState("");
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assignSuccess, setAssignSuccess] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  const refresh = useCallback(() => {
    participantsApi
      .list(study.id)
      .then(setParticipants)
      .catch((err: unknown) => setError(errorMessage(err)));
    groupsApi
      .list(study.id)
      .then(setGroups)
      .catch(() => {});
  }, [study.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function toggleSelect(id: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function assignToGroup(): Promise<void> {
    setAssignError(null);
    setAssignSuccess(null);
    if (assignGroupId === "") {
      setAssignError("Select a group.");
      return;
    }
    if (selected.size === 0) {
      setAssignError("Select at least one participant.");
      return;
    }
    setAssigning(true);
    try {
      const res = await groupsApi.assign(assignGroupId, { participant_ids: [...selected] });
      const parts: string[] = [];
      if (res.assigned.length) parts.push(`assigned ${res.assigned.length}`);
      if (res.conflicts.length)
        parts.push(`${res.conflicts.length} already in a group (unchanged)`);
      setAssignSuccess(parts.join("; ") || "No changes.");
      setSelected(new Set());
      refresh();
    } catch (err) {
      setAssignError(errorMessage(err));
    } finally {
      setAssigning(false);
    }
  }

  async function downloadCsv(): Promise<void> {
    setError(null);
    setDownloading(true);
    try {
      downloadBlob(await participantsApi.exportCodesCsv(study.id), "participants.csv");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />
      {!participants ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : participants.length === 0 ? (
        <p className="text-sm text-gray-500">No participants yet.</p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            {/* MOD-4 / MFR-24: assign selected participants to a group. */}
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Assign selected to group">
                <select
                  className={selectClass}
                  value={assignGroupId}
                  onChange={(e) => setAssignGroupId(e.target.value)}
                >
                  <option value="">Choose group…</option>
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Button
                variant="secondary"
                onClick={() => void assignToGroup()}
                loading={assigning}
                disabled={selected.size === 0 || assignGroupId === ""}
              >
                Assign to group ({selected.size})
              </Button>
            </div>
            <Button variant="secondary" onClick={() => void downloadCsv()} loading={downloading}>
              Download codes CSV
            </Button>
          </div>
          <ErrorBanner message={assignError} />
          <SuccessBanner message={assignSuccess} />
          {groups.length === 0 && (
            <p className="text-sm text-gray-500">Create a group on the Groups tab to enable assignment.</p>
          )}
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr className="text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.size === participants.length && participants.length > 0}
                      onChange={(e) =>
                        setSelected(e.target.checked ? new Set(participants.map((p) => p.id)) : new Set())
                      }
                    />
                  </th>
                  <th className="px-4 py-3">Code</th>
                  <th className="px-4 py-3">Group</th>
                  <th className="px-4 py-3">Password</th>
                  <th className="px-4 py-3">Sessions done</th>
                  <th className="px-4 py-3">Last activity</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {participants.map((p) => (
                  <ParticipantRow
                    key={p.id}
                    participant={p}
                    selected={selected.has(p.id)}
                    onToggleSelect={() => toggleSelect(p.id)}
                    onUpdated={(updated) =>
                      setParticipants((prev) => prev?.map((x) => (x.id === updated.id ? updated : x)) ?? prev)
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {participants && participants.length > 0 && (
        <GenerateProtocolForm study={study} participants={participants} onGenerated={refresh} />
      )}
      <AddParticipantsForm
        studyId={study.id}
        onCreated={(created) => setParticipants((prev) => [...(prev ?? []), ...created])}
      />
    </div>
  );
}
