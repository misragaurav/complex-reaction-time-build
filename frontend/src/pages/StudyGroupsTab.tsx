import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import { groupsApi } from "../api/groups";
import type { GroupDetailOut, GroupOut, StudyOut } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, SuccessBanner } from "../components/forms";

const SIZE_WARNING = "Groups are recommended to have 4–6 participants.";

function sizeWarn(count: number): boolean {
  return count < 4 || count > 6;
}

const FORCE_DEACTIVATE_HELPER =
  "Deactivate closes the slot for everyone who hasn't started; it is blocked if any member is mid-session (it won't interrupt them). Force deactivate closes the slot now even if some members are mid-session — those in-progress runs finish, but no one else can start.";

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

type SessionStageType = "onboarding" | "pre" | "post";

interface StageRowProps {
  label: string;
  sessionType: SessionStageType;
  disabled: boolean;
  hint?: string;
  busy: boolean;
  onActivate: (sessionType: SessionStageType) => void;
  onDeactivate: (sessionType: SessionStageType, force: boolean) => void;
}

function StageRow({ label, sessionType, disabled, hint, busy, onActivate, onDeactivate }: StageRowProps): JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded border border-gray-100 bg-gray-50 px-3 py-2">
      <span className="w-36 shrink-0 text-sm font-medium text-gray-700">{label}</span>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          disabled={disabled || busy}
          onClick={() => onActivate(sessionType)}
        >
          Activate
        </Button>
        <Button
          variant="secondary"
          disabled={disabled || busy}
          onClick={() => onDeactivate(sessionType, false)}
        >
          Deactivate
        </Button>
        <Button
          variant="secondary"
          disabled={disabled || busy}
          onClick={() => onDeactivate(sessionType, true)}
        >
          Force deactivate
        </Button>
      </div>
      {disabled && hint && <p className="w-full text-xs text-amber-700">{hint}</p>}
    </div>
  );
}

function GroupDetailPanel({
  groupId,
  onChanged,
}: {
  groupId: string;
  onChanged: () => void;
}): JSX.Element {
  const [detail, setDetail] = useState<GroupDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cisDraft, setCisDraft] = useState<string>("");

  const load = useCallback(() => {
    groupsApi
      .get(groupId)
      .then((d) => {
        setDetail(d);
        setCisDraft(d.current_intervention_session?.toString() ?? "");
      })
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [groupId]);

  useEffect(() => {
    load();
  }, [load]);

  // MOD-11: refetch member list when window regains focus.
  useEffect(() => {
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  async function setCis(value: number | null): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      await groupsApi.update(groupId, { current_intervention_session: value });
      load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // MOD-8: stage-aware activate (MFR-110..115).
  async function activateStage(sessionType: SessionStageType): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res = await groupsApi.activate(groupId, sessionType);
      const cis = detail?.current_intervention_session;
      if (sessionType === "onboarding") {
        setSuccess(`Activated ${res.activated.length} onboarding session(s).`);
      } else if (res.activated.length === 0) {
        setSuccess(`0 ${sessionType}-session(s) activated for IS ${cis ?? "?"} — none were in an activatable state.`);
      } else {
        setSuccess(`Activated ${res.activated.length} ${sessionType}-session(s) for IS ${cis ?? "?"}.`);
      }
      load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  // MOD-8: stage-aware deactivate with in-progress confirmation (MFR-114/128).
  async function deactivateStage(sessionType: SessionStageType, force: boolean): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res = await groupsApi.deactivate(groupId, sessionType, force);
      const cis = detail?.current_intervention_session;
      if (sessionType === "onboarding") {
        setSuccess(`Deactivated ${res.expired.length} onboarding session(s).`);
      } else {
        setSuccess(`Deactivated ${res.expired.length} ${sessionType}-session(s) for IS ${cis ?? "?"}.`);
      }
      load();
      onChanged();
    } catch (err) {
      // MFR-128: soft deactivate returned 409 due to in-progress sessions → confirm dialog.
      if (!force && err instanceof ApiError && err.status === 409) {
        const detail409 = err.detail as { in_progress_count?: number } | null;
        const count = detail409?.in_progress_count ?? 1;
        const confirmed = window.confirm(
          `${count} participant(s) are mid-session. Force deactivate will close the slot for everyone else; in-progress runs will finish but no one new can start. Continue?`,
        );
        if (confirmed) {
          setBusy(false);
          await deactivateStage(sessionType, true);
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

  const cis = detail.current_intervention_session;
  const noIs = cis == null;

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

      {/* MFR-23: IS editor with caption (MFR-119). */}
      <div className="space-y-1">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Current intervention session (IS)" hint="IS = Intervention Session. Display-only counter (1–52).">
            <input
              type="number"
              className={`${inputClass} w-32`}
              min={1}
              max={52}
              value={cisDraft}
              onChange={(e) => setCisDraft(e.target.value)}
            />
          </Field>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => void setCis(cisDraft.trim() === "" ? null : Number(cisDraft))}
          >
            Save
          </Button>
          <Button
            variant="secondary"
            disabled={busy || (cis ?? 0) >= 52}
            onClick={() => void setCis((cis ?? 0) + 1)}
          >
            +1
          </Button>
        </div>
      </div>

      {/* MFR-124: unified stage panel (Onboarding / Pre / Post). */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Session activation</h4>
        {/* MFR-120: soft-vs-force helper text (verbatim). */}
        <p className="text-xs text-gray-500">{FORCE_DEACTIVATE_HELPER}</p>
        <div className="space-y-2">
          <StageRow
            label="Onboarding"
            sessionType="onboarding"
            disabled={false}
            busy={busy}
            onActivate={(st) => void activateStage(st)}
            onDeactivate={(st, f) => void deactivateStage(st, f)}
          />
          <StageRow
            label={`Pre${cis != null ? ` (IS ${cis})` : ""}`}
            sessionType="pre"
            disabled={noIs}
            hint="Set an Intervention Session number to activate pre/post sessions."
            busy={busy}
            onActivate={(st) => void activateStage(st)}
            onDeactivate={(st, f) => void deactivateStage(st, f)}
          />
          <StageRow
            label={`Post${cis != null ? ` (IS ${cis})` : ""}`}
            sessionType="post"
            disabled={noIs}
            hint="Set an Intervention Session number to activate pre/post sessions."
            busy={busy}
            onActivate={(st) => void activateStage(st)}
            onDeactivate={(st, f) => void deactivateStage(st, f)}
          />
        </div>
      </div>

      {/* MFR-25: per-group completion counts. */}
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
