import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import { groupsApi } from "../api/groups";
import type {
  GroupDetailOut,
  GroupOut,
  GroupSessionsOverviewResponse,
  StageOverview,
  StageStatusCounts,
  StudyOut,
} from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass, SuccessBanner } from "../components/forms";

const SIZE_WARNING = "Groups are recommended to have 4–6 participants.";

function sizeWarn(count: number): boolean {
  return count < 4 || count > 6;
}

function CreateGroupForm({
  studyId,
  onCreated,
}: {
  studyId: string;
  onCreated: () => void;
}): JSX.Element {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await groupsApi.create(studyId, {
        name: name.trim(),
        description: description.trim() ? description.trim() : null,
      });
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="text-base font-semibold text-gray-900">Create group</h2>
      <ErrorBanner message={error} />
      <Field label="Name">
        <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required />
      </Field>
      <Field label="Description" hint="Optional, up to 200 characters.">
        <input
          className={inputClass}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={200}
        />
      </Field>
      <Button type="submit" loading={submitting}>
        Create group
      </Button>
    </form>
  );
}

// ---- Stage selector helpers (MOD-12) -----------------------------------------

function stageKey(stage: StageOverview): string {
  return `${stage.session_type}:${stage.intervention_session_number ?? "null"}`;
}

function parseStageKey(key: string): {
  session_type: "onboarding" | "pre" | "post";
  intervention_session_number: number | null;
} {
  const colonIdx = key.indexOf(":");
  const st = key.slice(0, colonIdx) as "onboarding" | "pre" | "post";
  const isnStr = key.slice(colonIdx + 1);
  return {
    session_type: st,
    intervention_session_number: isnStr === "null" ? null : Number(isnStr),
  };
}

function buildActivateHint(counts: StageStatusCounts): string {
  const parts: string[] = [];
  if (counts.completed > 0) parts.push(`${counts.completed} completed`);
  const open = counts.activated + counts.in_progress;
  if (open > 0) parts.push(`${open} already open`);
  const other = counts.abandoned + counts.cancelled;
  if (other > 0) parts.push(`${other} other`);
  return parts.length > 0 ? `Cannot activate: ${parts.join(", ")}.` : "No activatable sessions.";
}

function buildDiagnostic(stage: StageOverview | undefined): string {
  if (!stage) return "0 sessions activated: no protocol generated for this stage.";
  const counts = stage.counts;
  const parts: string[] = [];
  if (counts.completed > 0) parts.push(`${counts.completed} completed`);
  const open = counts.activated + counts.in_progress;
  if (open > 0) parts.push(`${open} already open`);
  const other = counts.abandoned + counts.cancelled;
  if (other > 0) parts.push(`${other} other`);
  return parts.length > 0 ? `0 sessions activated: ${parts.join(", ")}.` : "0 sessions activated.";
}

// ---- Group detail panel -------------------------------------------------------

function GroupDetailPanel({
  groupId,
  onChanged,
}: {
  groupId: string;
  onChanged: () => void;
}): JSX.Element {
  const [detail, setDetail] = useState<GroupDetailOut | null>(null);
  const [overview, setOverview] = useState<GroupSessionsOverviewResponse | null>(null);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [diagnostic, setDiagnostic] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback((): void => {
    groupsApi
      .get(groupId)
      .then(setDetail)
      .catch((err: unknown) => setError(errorMessage(err)));
    groupsApi
      .sessionsOverview(groupId)
      .then((ov) => {
        setOverview(ov);
        setSelectedKey((prev) => {
          const first = ov.stages[0];
          return !prev && first ? stageKey(first) : prev;
        });
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [groupId]);

  useEffect(() => {
    load();
  }, [load]);

  // MOD-11: refetch on window focus.
  useEffect(() => {
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  // MOD-12: activate the selected stage.
  async function activateStage(): Promise<void> {
    if (!selectedKey) return;
    const { session_type, intervention_session_number } = parseStageKey(selectedKey);
    setError(null);
    setDiagnostic(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res = await groupsApi.activate(groupId, { session_type, intervention_session_number });
      // Always refresh overview for fresh counts.
      const ov = await groupsApi.sessionsOverview(groupId);
      setOverview(ov);
      groupsApi.get(groupId).then(setDetail).catch(() => null);
      onChanged();
      if (res.activated.length === 0) {
        // MFR-207: zero-result → diagnostic, never a success banner.
        const stage = ov.stages.find(
          (s) => s.session_type === session_type && s.intervention_session_number === intervention_session_number,
        );
        setDiagnostic(buildDiagnostic(stage));
      } else {
        setSuccess(
          session_type === "onboarding"
            ? `Activated ${res.activated.length} onboarding session(s).`
            : `Activated ${res.activated.length} ${session_type} session(s) for IS ${intervention_session_number ?? "?"}.`,
        );
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // MOD-12: deactivate the selected stage, with MFR-208 force-confirm dialog.
  async function deactivateStage(force: boolean): Promise<void> {
    if (!selectedKey) return;
    const { session_type, intervention_session_number } = parseStageKey(selectedKey);
    setError(null);
    setDiagnostic(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res = await groupsApi.deactivate(groupId, { session_type, intervention_session_number, force });
      load();
      onChanged();
      setSuccess(
        session_type === "onboarding"
          ? `Deactivated ${res.expired.length} onboarding session(s).`
          : `Deactivated ${res.expired.length} ${session_type} session(s) for IS ${intervention_session_number ?? "?"}.`,
      );
    } catch (err) {
      // MFR-208: soft deactivate returned 409 → confirm before force.
      if (!force && err instanceof ApiError && err.status === 409) {
        const detail409 = err.detail as { in_progress_count?: number } | null;
        const count = detail409?.in_progress_count ?? 1;
        const confirmed = window.confirm(
          `${count} participant(s) are mid-session. Force deactivate will close the slot for everyone else; in-progress runs will finish but no one new can start. Continue?`,
        );
        if (confirmed) {
          setBusy(false);
          await deactivateStage(true);
          return;
        }
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return <ErrorBanner message={error} />;
  }

  // Derived state for activation section (MFR-205).
  const hasStages = overview !== null && overview.stages.length > 0;
  const selectedStage = overview?.stages.find((s) => stageKey(s) === selectedKey) ?? null;
  const nActivatable = selectedStage ? selectedStage.counts.created + selectedStage.counts.expired : 0;
  const activateHint = selectedStage && nActivatable === 0 ? buildActivateHint(selectedStage.counts) : null;

  return (
    <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-gray-900">{detail.name}</h3>
        <span className="text-sm text-gray-500">{detail.member_count} members</span>
      </div>
      {detail.description && <p className="text-sm text-gray-600">{detail.description}</p>}
      {sizeWarn(detail.member_count) && (
        <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{SIZE_WARNING}</p>
      )}
      <ErrorBanner message={error} />
      <SuccessBanner message={success} />

      {/* MFR-201/MFR-204/MFR-206: named session selector + action buttons. */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Session activation</h4>
        <div className="flex flex-wrap items-center gap-2">
          {/* MFR-202/MFR-203: selector populated from sessions-overview. */}
          <select
            className={selectClass}
            value={selectedKey}
            onChange={(e) => { setSelectedKey(e.target.value); setDiagnostic(null); }}
            disabled={!hasStages || busy}
          >
            {!hasStages && (
              <option value="" disabled>
                No sessions found — generate protocol sessions for group members first
              </option>
            )}
            {(overview?.stages ?? []).map((s) => (
              <option key={stageKey(s)} value={stageKey(s)}>
                {s.display_label}
              </option>
            ))}
          </select>
          {/* MFR-204: three action buttons. */}
          <Button
            variant="secondary"
            disabled={busy || !selectedKey || !hasStages || nActivatable === 0}
            onClick={() => void activateStage()}
          >
            Activate
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !selectedKey || !hasStages}
            onClick={() => void deactivateStage(false)}
          >
            Deactivate
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !selectedKey || !hasStages}
            onClick={() => void deactivateStage(true)}
          >
            Force deactivate
          </Button>
        </div>
        {/* MFR-205: hint when no activatable sessions. */}
        {activateHint && <p className="text-xs text-amber-700">{activateHint}</p>}
        {/* MFR-207: diagnostic instead of success banner on zero-activation. */}
        {diagnostic && (
          <p className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {diagnostic}
          </p>
        )}
      </div>

      {/* MFR-25 / MFR-126: per-group completion counts. */}
      <div className="grid grid-cols-2 gap-2 text-sm text-gray-700 sm:grid-cols-3">
        <div>Completed pre (overall): {detail.completion.completed_pre_overall}</div>
        <div>Completed post (overall): {detail.completion.completed_post_overall}</div>
        <div>Assigned: {detail.completion.total_assigned}</div>
        <div>Completed pre (current): {detail.completion.completed_pre_current}</div>
        <div>Completed post (current): {detail.completion.completed_post_current}</div>
      </div>

      <div>
        <h4 className="mb-1 text-sm font-medium text-gray-700">Members</h4>
        {detail.members.length === 0 ? (
          <p className="text-sm text-gray-500">No participants assigned yet.</p>
        ) : (
          <ul className="divide-y divide-gray-100 rounded border border-gray-200">
            {detail.members.map((m) => (
              <li key={m.participant_id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="font-mono text-gray-800">{m.code}</span>
                <span className="text-gray-500">
                  {m.sessions_completed}/{m.sessions_assigned} done
                  {!m.is_active && <span className="ml-2 text-gray-400">(deactivated)</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* MFR-27: delete-group (only when empty). */}
      {detail.member_count === 0 && (
        <Button
          variant="danger"
          disabled={busy}
          onClick={() => {
            setError(null);
            setBusy(true);
            groupsApi
              .remove(groupId)
              .then(() => onChanged())
              .catch((err: unknown) => {
                setError(errorMessage(err));
                setBusy(false);
              });
          }}
        >
          Delete group
        </Button>
      )}
    </div>
  );
}

export default function StudyGroupsTab({ study }: { study: StudyOut }): JSX.Element {
  const [groups, setGroups] = useState<GroupOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const reload = useCallback(() => {
    groupsApi
      .list(study.id)
      .then(setGroups)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  // MOD-11: refetch on window focus so that reassignment changes are visible immediately.
  useEffect(() => {
    function handleFocus(): void {
      reload();
    }
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [reload]);

  return (
    <div className="space-y-6">
      {/* MFR-121: Create-group left, groups list right at md+ width. */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <CreateGroupForm studyId={study.id} onCreated={reload} />

        <div className="space-y-3">
          <h2 className="text-base font-semibold text-gray-900">Groups</h2>
          <ErrorBanner message={error} />
          {!groups ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : groups.length === 0 ? (
            <p className="text-sm text-gray-500">No groups yet.</p>
          ) : (
            <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
              {groups.map((g) => (
                <li key={g.id}>
                  {/* MFR-123: selected row uses bg-blue-50 + ring-2 ring-blue-500 + font-semibold. */}
                  <button
                    type="button"
                    onClick={() => setSelected(g.id)}
                    className={`flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm hover:bg-blue-50 ${
                      selected === g.id
                        ? "bg-blue-50 font-semibold ring-2 ring-inset ring-blue-500"
                        : ""
                    }`}
                  >
                    <span className="text-gray-900">{g.name}</span>
                    <span className="flex items-center gap-2 text-gray-500">
                      {sizeWarn(g.member_count) && <span title={SIZE_WARNING}>⚠️</span>}
                      {g.member_count} members
                      {g.current_intervention_session != null && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                          IS {g.current_intervention_session}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* MFR-122: full-width detail panel below, only when a group is selected. */}
      {selected && (
        <GroupDetailPanel
          key={selected}
          groupId={selected}
          onChanged={() => {
            reload();
            // If the selected group was deleted, deselect.
            if (groups && !groups.find((g) => g.id === selected)) {
              setSelected(null);
            }
          }}
        />
      )}
    </div>
  );
}
