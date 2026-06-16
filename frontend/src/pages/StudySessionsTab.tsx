import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { errorMessage } from "../api/client";
import { exportsApi } from "../api/exports";
import { participantsApi } from "../api/participants";
import { sessionsApi } from "../api/sessions";
import type {
  ParticipantOut,
  SessionOut,
  SessionStatus,
  StudyOut,
} from "../api/types";
import { Button, ErrorBanner, Field, inputClass, selectClass } from "../components/forms";
import { usePersistentState } from "../hooks/usePersistentState";
import { downloadBlob } from "../utils/download";

const STATUS_LABELS: Record<SessionStatus, string> = {
  created: "Not started",
  activated: "Ready",
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
  expired: "Deactivated",
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

type SortField =
  | "participant_code"
  | "order_index"
  | "display_label"
  | "session_type"
  | "code"
  | "task_type"
  | "status"
  | "attempt"
  | "activated_at"
  | "completed_at"
  | "trimmed_mean_rt_ms"
  | "accuracy_pct";

const SESSION_TYPE_ORDER: Record<string, number> = {
  onboarding: 0,
  pre: 1,
  post: 2,
};

// MFR-130..135: persisted Sessions-tab preferences (one object per study).
const VALID_SORT_FIELDS: SortField[] = [
  "participant_code", "order_index", "display_label", "session_type",
  "code", "task_type", "status", "attempt",
  "activated_at", "completed_at", "trimmed_mean_rt_ms", "accuracy_pct",
];
const VALID_GROUP_MODES = ["none", "participant", "group"] as const;
const VALID_SORT_DIRS = ["asc", "desc"] as const;
const VALID_STATUS_FILTERS = [
  "", "created", "activated", "in_progress", "completed", "abandoned", "expired", "cancelled",
] as const;

interface StoredPrefs {
  groupMode: "none" | "participant" | "group";
  sortField: SortField;
  sortDir: "asc" | "desc";
  statusFilter: string;
  participantFilter: string;
  collapsed: string[];
}

const DEFAULT_PREFS: StoredPrefs = {
  groupMode: "none",
  sortField: "participant_code",
  sortDir: "asc",
  statusFilter: "",
  participantFilter: "",
  collapsed: [],
};

function validatePrefs(raw: unknown): StoredPrefs | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;

  const groupMode = VALID_GROUP_MODES.includes(r.groupMode as "none") ? (r.groupMode as StoredPrefs["groupMode"]) : "none";
  const sortField = VALID_SORT_FIELDS.includes(r.sortField as SortField) ? (r.sortField as SortField) : "participant_code";
  const sortDir = VALID_SORT_DIRS.includes(r.sortDir as "asc") ? (r.sortDir as "asc" | "desc") : "asc";
  const statusFilter = VALID_STATUS_FILTERS.includes(r.statusFilter as "") ? (r.statusFilter as string) : "";
  const participantFilter = typeof r.participantFilter === "string" ? r.participantFilter : "";
  const rawCollapsed = r.collapsed;
  const collapsed = Array.isArray(rawCollapsed) ? (rawCollapsed.filter((v): v is string => typeof v === "string")) : [];

  return { groupMode, sortField, sortDir, statusFilter, participantFilter, collapsed };
}

function getFieldValue(session: SessionOut, field: SortField): string | number | null {
  switch (field) {
    case "participant_code":
      return session.participant_code.toLowerCase();
    case "order_index":
      return session.order_index;
    case "display_label":
      return session.display_label.toLowerCase();
    case "session_type":
      return SESSION_TYPE_ORDER[session.session_type] ?? 0;
    case "code":
      return session.code;
    case "task_type":
      return session.task_type;
    case "status":
      return session.status;
    case "attempt":
      return session.attempt;
    case "activated_at":
      return session.activated_at;
    case "completed_at":
      return session.completed_at;
    case "trimmed_mean_rt_ms":
      return session.stats.trimmed_mean_rt_ms;
    case "accuracy_pct":
      return session.stats.accuracy_pct;
  }
}

function sortSessions(
  sessions: SessionOut[],
  field: SortField,
  dir: "asc" | "desc",
): SessionOut[] {
  return [...sessions].sort((a, b) => {
    const av = getFieldValue(a, field);
    const bv = getFieldValue(b, field);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    let cmp = 0;
    if (typeof av === "string" && typeof bv === "string") {
      cmp = av < bv ? -1 : av > bv ? 1 : 0;
    } else if (typeof av === "number" && typeof bv === "number") {
      cmp = av - bv;
    }
    return dir === "asc" ? cmp : -cmp;
  });
}

type SessionGroup = {
  key: string;
  label: string;
  total: number;
  completed: number;
  members: number;
  sessions: SessionOut[];
};

function groupSessions(
  sessions: SessionOut[],
  mode: "participant" | "group",
): SessionGroup[] {
  const buckets = new Map<string, SessionOut[]>();
  for (const s of sessions) {
    // MOD-11: group_name comes directly from the session (populated via server-side join).
    const key =
      mode === "participant"
        ? s.participant_code
        : (s.group_name ?? "__unassigned__");
    const bucket = buckets.get(key);
    if (bucket) bucket.push(s);
    else buckets.set(key, [s]);
  }

  const result: SessionGroup[] = [];
  for (const [key, slist] of buckets) {
    const completed = slist.filter((s) => s.status === "completed").length;
    const members = new Set(slist.map((s) => s.participant_id)).size;
    result.push({
      key,
      label: key === "__unassigned__" ? "Unassigned" : key,
      total: slist.length,
      completed,
      members,
      sessions: slist,
    });
  }

  result.sort((a, b) => {
    if (a.key === "__unassigned__") return 1;
    if (b.key === "__unassigned__") return -1;
    return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
  });

  return result;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
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

function SortableTh({
  field,
  sortField,
  sortDir,
  onSort,
  children,
}: {
  field: SortField;
  sortField: SortField;
  sortDir: "asc" | "desc";
  onSort: (field: SortField) => void;
  children: ReactNode;
}): JSX.Element {
  const active = field === sortField;
  return (
    <th
      className="cursor-pointer select-none px-4 py-3 hover:bg-gray-50"
      onClick={() => onSort(field)}
    >
      {children}
      {active && <span className="ml-1">{sortDir === "asc" ? "▲" : "▼"}</span>}
    </th>
  );
}

export default function StudySessionsTab({ study }: { study: StudyOut }): JSX.Element {
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [participants, setParticipants] = useState<ParticipantOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  // MFR-130: persist table preferences per study (MFR-132: single key per study).
  const [prefs, setPrefs] = usePersistentState<StoredPrefs>(
    `crt.sessionsTab.prefs.${study.id}`,
    DEFAULT_PREFS,
    { validate: validatePrefs },
  );

  // Convenience aliases that mirror the old useState shapes.
  const groupMode = prefs.groupMode;
  const sortField = prefs.sortField;
  const sortDir = prefs.sortDir;
  const statusFilter = prefs.statusFilter;
  const participantFilter = prefs.participantFilter;
  const collapsed = new Set(prefs.collapsed);

  function setGroupMode(gm: StoredPrefs["groupMode"]): void {
    // MFR-133: reset collapsed when switching group mode.
    setPrefs((p) => ({ ...p, groupMode: gm, collapsed: [] }));
  }
  function setSortField(field: SortField): void {
    setPrefs((p) => ({ ...p, sortField: field }));
  }
  function setSortDir(updater: "asc" | "desc" | ((prev: "asc" | "desc") => "asc" | "desc")): void {
    setPrefs((p) => ({
      ...p,
      sortDir: typeof updater === "function" ? updater(p.sortDir) : updater,
    }));
  }
  function setStatusFilter(sf: string): void {
    setPrefs((p) => ({ ...p, statusFilter: sf }));
  }
  function setParticipantFilter(pf: string): void {
    setPrefs((p) => ({ ...p, participantFilter: pf }));
  }
  function setCollapsed(updater: Set<string> | ((prev: Set<string>) => Set<string>)): void {
    setPrefs((p) => {
      const prevSet = new Set(p.collapsed);
      const nextSet = typeof updater === "function" ? updater(prevSet) : updater;
      return { ...p, collapsed: [...nextSet] };
    });
  }

  const reload = useCallback((): void => {
    sessionsApi
      .list(study.id, {
        status: statusFilter === "" ? undefined : (statusFilter as SessionStatus),
        participantId: participantFilter === "" ? undefined : participantFilter,
      })
      .then(setSessions)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id, statusFilter, participantFilter]);

  useEffect(() => {
    setError(null);
    reload();
  }, [reload]);

  useEffect(() => {
    participantsApi
      .list(study.id)
      .then((parts) => {
        setParticipants(parts);
        // MFR-131: if stored participantFilter id is no longer in the loaded list, clear it.
        setPrefs((p) => {
          if (p.participantFilter && !parts.find((pt) => pt.id === p.participantFilter)) {
            return { ...p, participantFilter: "" };
          }
          return p;
        });
      })
      .catch((err: unknown) => setError(errorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.id]);

  // MOD-11: refetch sessions when the window regains focus so that a reassignment
  // made on another tab is reflected immediately without a hard page reload.
  useEffect(() => {
    function handleFocus(): void {
      reload();
    }
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, [reload]);

  const sorted = useMemo(
    () => (sessions ? sortSessions(sessions, sortField, sortDir) : []),
    [sessions, sortField, sortDir],
  );

  const groups = useMemo(
    () => (groupMode !== "none" ? groupSessions(sorted, groupMode) : []),
    [sorted, groupMode],
  );

  function handleSort(field: SortField): void {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  function toggleSection(key: string): void {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const thProps = { sortField, sortDir, onSort: handleSort };

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
          <select
            className={selectClass}
            value={participantFilter}
            onChange={(e) => setParticipantFilter(e.target.value)}
          >
            <option value="">All</option>
            {participants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code}
              </option>
            ))}
          </select>
        </Field>
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-gray-500">Group by</span>
          <div className="flex gap-3">
            {(["none", "participant", "group"] as const).map((m) => (
              <label key={m} className="flex items-center gap-1.5 text-sm text-gray-700">
                <input
                  type="radio"
                  name="sessions-group-by"
                  checked={groupMode === m}
                  onChange={() => setGroupMode(m)}
                />
                {m === "none" ? "None" : m === "participant" ? "Participant" : "Group"}
              </label>
            ))}
          </div>
        </div>
        {groupMode !== "none" && (
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setCollapsed(new Set(groups.map((g) => g.key)))}
            >
              Collapse all
            </Button>
            <Button variant="secondary" onClick={() => setCollapsed(new Set())}>
              Expand all
            </Button>
          </div>
        )}
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
                <SortableTh field="participant_code" {...thProps}>Participant</SortableTh>
                <SortableTh field="order_index" {...thProps}>#</SortableTh>
                <SortableTh field="display_label" {...thProps}>Label</SortableTh>
                <SortableTh field="session_type" {...thProps}>Type</SortableTh>
                <SortableTh field="code" {...thProps}>Session code</SortableTh>
                <SortableTh field="task_type" {...thProps}>Task</SortableTh>
                <SortableTh field="status" {...thProps}>Status</SortableTh>
                <SortableTh field="attempt" {...thProps}>Attempt</SortableTh>
                <SortableTh field="activated_at" {...thProps}>Activated</SortableTh>
                <SortableTh field="completed_at" {...thProps}>Completed</SortableTh>
                <SortableTh field="trimmed_mean_rt_ms" {...thProps}>Trimmed mean RT</SortableTh>
                <SortableTh field="accuracy_pct" {...thProps}>Accuracy</SortableTh>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            {groupMode === "none" ? (
              <tbody className="divide-y divide-gray-200">
                {sorted.map((s) => (
                  <SessionRow key={s.id} session={s} onChanged={reload} />
                ))}
              </tbody>
            ) : (
              groups.map((g) => (
                <tbody key={g.key} className="divide-y divide-gray-200">
                  <tr
                    className="cursor-pointer bg-gray-50 hover:bg-gray-100"
                    onClick={() => toggleSection(g.key)}
                  >
                    <td colSpan={13} className="px-4 py-2 text-sm font-semibold text-gray-700">
                      <span className="mr-1 inline-block w-4 text-center text-gray-400">
                        {collapsed.has(g.key) ? "▶" : "▼"}
                      </span>
                      {g.label}
                      {groupMode === "participant"
                        ? ` — ${g.total} session${g.total === 1 ? "" : "s"}, ${g.completed} completed`
                        : ` — ${g.members} member${g.members === 1 ? "" : "s"}, ${g.completed} completed`}
                    </td>
                  </tr>
                  {!collapsed.has(g.key) &&
                    g.sessions.map((s) => (
                      <SessionRow key={s.id} session={s} onChanged={reload} />
                    ))}
                </tbody>
              ))
            )}
          </table>
        </div>
      )}
    </div>
  );
}
