import { useCallback, useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { groupsApi } from "../api/groups";
import type { GroupDeactivateResponse, GroupDetailOut, GroupOut, StudyOut } from "../api/types";
import { Button, ErrorBanner, Field, inputClass, SuccessBanner } from "../components/forms";

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

  // MOD-5: group-level session open/close (MFR-31/32).
  async function openSession(): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res = await groupsApi.activate(groupId);
      setSuccess(`Activated ${res.activated.length} session(s) for IS ${detail?.current_intervention_session ?? "?"}.`);
      load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function closeSession(force = false): Promise<void> {
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res: GroupDeactivateResponse = await groupsApi.deactivate(groupId, force);
      const msg = `Expired ${res.expired.length} session(s).${res.in_progress_count > 0 ? ` ${res.in_progress_count} in-progress session(s) were left running.` : ""}`;
      setSuccess(msg);
      load();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (!detail) {
    return <ErrorBanner message={error} />;
  }

  const cis = detail.current_intervention_session;

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

      {/* MOD-4 / MFR-23: intervention-stage counter (display-only). */}
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Current intervention session" hint="Display-only counter (1–52).">
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

      {/* MOD-5 / MFR-31/32: open/close current session slot for all members. */}
      {cis != null && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => void openSession()}>
            Open session (IS {cis})
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void closeSession(false)}>
            Close session
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => void closeSession(true)}>
            Force close
          </Button>
        </div>
      )}

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

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <ErrorBanner message={error} />
        {!groups ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-gray-500">No groups yet.</p>
        ) : (
          <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
            {groups.map((g) => (
              <li key={g.id}>
                <button
                  type="button"
                  onClick={() => setSelected(g.id)}
                  className={`flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm hover:bg-gray-50 ${
                    selected === g.id ? "bg-gray-50" : ""
                  }`}
                >
                  <span className="font-medium text-gray-900">{g.name}</span>
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
        <CreateGroupForm studyId={study.id} onCreated={reload} />
      </div>

      <div>
        {selected ? (
          <GroupDetailPanel
            key={selected}
            groupId={selected}
            onChanged={() => {
              reload();
            }}
          />
        ) : (
          <p className="text-sm text-gray-500">Select a group to see members and details.</p>
        )}
      </div>
    </div>
  );
}
