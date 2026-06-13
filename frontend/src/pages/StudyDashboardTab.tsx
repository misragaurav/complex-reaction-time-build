import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { errorMessage } from "../api/client";
import { sessionsApi } from "../api/sessions";
import { statisticsApi } from "../api/statistics";
import type {
  ParticipantSummaryOut,
  SessionOut,
  SessionSort,
  SessionStatus,
  SessionSummaryDetailOut,
  StudyOut,
  StudySummaryOut,
} from "../api/types";
import { Button, ErrorBanner, Field, selectClass } from "../components/forms";
import { downloadCsv } from "../utils/csv";

const HISTOGRAM_BIN_MS = 50;

const PALETTE = [
  "#2563EB",
  "#DC2626",
  "#16A34A",
  "#9333EA",
  "#EA580C",
  "#0891B2",
  "#CA8A04",
  "#DB2777",
  "#4B5563",
  "#65A30D",
];

const STATUS_LABELS: Record<SessionStatus, string> = {
  created: "Not started",
  activated: "Ready",
  in_progress: "In progress",
  completed: "Completed",
  abandoned: "Abandoned",
  expired: "Missed",
  cancelled: "Cancelled",
};

const SORT_OPTIONS: { value: SessionSort; label: string }[] = [
  { value: "participant_code", label: "Participant code" },
  { value: "order_index", label: "Session number" },
  { value: "status", label: "Status" },
  { value: "attempt", label: "Attempt" },
  { value: "-created_at", label: "Newest first" },
  { value: "-started_at", label: "Recently started" },
  { value: "-completed_at", label: "Recently completed" },
];

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "study";
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function ChartCard({
  title,
  onDownload,
  children,
}: {
  title: string;
  onDownload: () => void;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        <Button variant="secondary" onClick={onDownload}>
          Download CSV
        </Button>
      </div>
      {children}
    </section>
  );
}

function EmptyChart({ message }: { message: string }): JSX.Element {
  return <p className="py-12 text-center text-sm text-gray-500">{message}</p>;
}

// ---- (a) RT histogram for a selected session -------------------------------

function RtHistogram({
  studySlug,
  completedSessions,
}: {
  studySlug: string;
  completedSessions: SessionOut[];
}): JSX.Element {
  const [sessionId, setSessionId] = useState<string>("");
  const [detail, setDetail] = useState<SessionSummaryDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (completedSessions.length > 0 && sessionId === "") {
      const first = completedSessions[0];
      if (first) setSessionId(first.id);
    }
  }, [completedSessions, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    setDetail(null);
    setError(null);
    statisticsApi
      .sessionSummary(sessionId)
      .then(setDetail)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [sessionId]);

  const bins = useMemo(() => {
    if (!detail) return [];
    const rts = detail.trials.filter((t) => t.rt_ms !== null);
    if (rts.length === 0) return [];
    const byBin = new Map<number, { ok: number; outliers: number }>();
    for (const t of rts) {
      const start = Math.floor((t.rt_ms as number) / HISTOGRAM_BIN_MS) * HISTOGRAM_BIN_MS;
      const entry = byBin.get(start) ?? { ok: 0, outliers: 0 };
      if (t.outlier_flag) {
        entry.outliers += 1;
      } else {
        entry.ok += 1;
      }
      byBin.set(start, entry);
    }
    const starts = [...byBin.keys()];
    const min = Math.min(...starts);
    const max = Math.max(...starts);
    const result: { bin: string; bin_start: number; ok: number; outliers: number }[] = [];
    for (let b = min; b <= max; b += HISTOGRAM_BIN_MS) {
      const entry = byBin.get(b) ?? { ok: 0, outliers: 0 };
      result.push({ bin: `${b}`, bin_start: b, ok: entry.ok, outliers: entry.outliers });
    }
    return result;
  }, [detail]);

  function download(): void {
    downloadCsv(
      `${studySlug}_rt-histogram.csv`,
      ["bin_start_ms", "bin_end_ms", "n_trials", "n_outliers_flagged"],
      bins.map((b) => [b.bin_start, b.bin_start + HISTOGRAM_BIN_MS, b.ok, b.outliers]),
    );
  }

  const selected = completedSessions.find((s) => s.id === sessionId);

  return (
    <ChartCard title="RT histogram (selected session, 50 ms bins, outliers highlighted)" onDownload={download}>
      {completedSessions.length === 0 ? (
        <EmptyChart message="No completed sessions yet." />
      ) : (
        <>
          <Field label="Session">
            <select className={selectClass} value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
              {completedSessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.participant_code} — session {s.order_index} (attempt {s.attempt})
                </option>
              ))}
            </select>
          </Field>
          <ErrorBanner message={error} />
          {!detail ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : bins.length === 0 ? (
            <EmptyChart message="No reaction times recorded for this session." />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={bins}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="bin" label={{ value: "RT (ms)", position: "insideBottom", offset: -2 }} />
                <YAxis allowDecimals={false} label={{ value: "Trials", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="ok" stackId="rt" name="Trials" fill="#2563EB" />
                <Bar dataKey="outliers" stackId="rt" name="Outliers flagged" fill="#DC2626" />
              </BarChart>
            </ResponsiveContainer>
          )}
          {selected && detail && (
            <p className="text-xs text-gray-500">
              {detail.n_trials} test trials, attempt {detail.attempt}; trimmed mean{" "}
              {detail.trimmed.mean_rt_ms !== null ? `${detail.trimmed.mean_rt_ms.toFixed(1)} ms` : "—"}.
            </p>
          )}
        </>
      )}
    </ChartCard>
  );
}

// ---- (b) strip plot of trimmed mean RT per participant ----------------------

function MeanRtStripPlot({
  studySlug,
  participants,
  orderBySessionId,
}: {
  studySlug: string;
  participants: ParticipantSummaryOut[];
  orderBySessionId: Map<string, number>;
}): JSX.Element {
  const points = useMemo(() => {
    const result: { participant_code: string; session_order: number | null; mean_rt: number }[] = [];
    for (const p of participants) {
      for (const s of p.sessions) {
        if (s.trimmed.mean_rt_ms !== null) {
          result.push({
            participant_code: p.participant_code,
            session_order: orderBySessionId.get(s.session_id) ?? null,
            mean_rt: s.trimmed.mean_rt_ms,
          });
        }
      }
    }
    return result;
  }, [participants, orderBySessionId]);

  function download(): void {
    downloadCsv(
      `${studySlug}_trimmed-mean-rt-per-participant.csv`,
      ["participant_code", "session_order", "trimmed_mean_rt_ms"],
      points.map((p) => [p.participant_code, p.session_order, p.mean_rt]),
    );
  }

  return (
    <ChartCard title="Trimmed mean RT per participant (one point per completed session)" onDownload={download}>
      {points.length === 0 ? (
        <EmptyChart message="No completed sessions yet." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart margin={{ bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="participant_code" type="category" allowDuplicatedCategory={false} name="Participant" />
            <YAxis dataKey="mean_rt" name="Trimmed mean RT (ms)" unit=" ms" />
            <Tooltip cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={points} fill="#2563EB" />
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---- (c) per-participant SD RT (IIV-within) by session ----------------------

function IivWithinBarChart({
  studySlug,
  participants,
  orderBySessionId,
}: {
  studySlug: string;
  participants: ParticipantSummaryOut[];
  orderBySessionId: Map<string, number>;
}): JSX.Element {
  const withData = participants.filter((p) => p.sessions.length > 0);
  const [participantId, setParticipantId] = useState<string>("");

  useEffect(() => {
    if (withData.length > 0 && !withData.some((p) => p.participant_id === participantId)) {
      const first = withData[0];
      if (first) setParticipantId(first.participant_id);
    }
  }, [withData, participantId]);

  const selected = withData.find((p) => p.participant_id === participantId);

  const bars = useMemo(() => {
    if (!selected) return [];
    return selected.sessions
      .filter((s) => s.trimmed.iiv_within_ms !== null)
      .map((s) => ({
        session: `S${orderBySessionId.get(s.session_id) ?? "?"}`,
        order: orderBySessionId.get(s.session_id) ?? 0,
        iiv: s.trimmed.iiv_within_ms as number,
      }))
      .sort((a, b) => a.order - b.order);
  }, [selected, orderBySessionId]);

  function download(): void {
    downloadCsv(
      `${studySlug}_iiv-within-by-session.csv`,
      ["participant_code", "session_order", "sd_rt_ms_iiv_within"],
      bars.map((b) => [selected?.participant_code ?? "", b.order, b.iiv]),
    );
  }

  return (
    <ChartCard title="SD of RT (IIV-within) by session, per participant" onDownload={download}>
      {withData.length === 0 ? (
        <EmptyChart message="No completed sessions yet." />
      ) : (
        <>
          <Field label="Participant">
            <select className={selectClass} value={participantId} onChange={(e) => setParticipantId(e.target.value)}>
              {withData.map((p) => (
                <option key={p.participant_id} value={p.participant_id}>
                  {p.participant_code}
                </option>
              ))}
            </select>
          </Field>
          {bars.length === 0 ? (
            <EmptyChart message="No RT variability data for this participant." />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={bars}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="session" />
                <YAxis unit=" ms" label={{ value: "SD RT (ms)", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Bar dataKey="iiv" name="SD RT (IIV-within)" fill="#9333EA" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </>
      )}
    </ChartCard>
  );
}

// ---- (d) session-mean RT across session order (IIV-between) -----------------

function MeanRtLineChart({
  studySlug,
  participants,
  orderBySessionId,
}: {
  studySlug: string;
  participants: ParticipantSummaryOut[];
  orderBySessionId: Map<string, number>;
}): JSX.Element {
  const { rows, codes, points } = useMemo(() => {
    const longPoints: { participant_code: string; session_order: number; mean_rt: number }[] = [];
    for (const p of participants) {
      for (const s of p.sessions) {
        const order = orderBySessionId.get(s.session_id);
        if (order !== undefined && s.trimmed.mean_rt_ms !== null) {
          longPoints.push({
            participant_code: p.participant_code,
            session_order: order,
            mean_rt: s.trimmed.mean_rt_ms,
          });
        }
      }
    }
    const orders = [...new Set(longPoints.map((p) => p.session_order))].sort((a, b) => a - b);
    const codeList = [...new Set(longPoints.map((p) => p.participant_code))];
    const pivoted = orders.map((order) => {
      const row: Record<string, number | string> = { order: `S${order}` };
      for (const point of longPoints) {
        if (point.session_order === order) {
          row[point.participant_code] = point.mean_rt;
        }
      }
      return row;
    });
    return { rows: pivoted, codes: codeList, points: longPoints };
  }, [participants, orderBySessionId]);

  function download(): void {
    downloadCsv(
      `${studySlug}_session-mean-rt-by-order.csv`,
      ["participant_code", "session_order", "trimmed_mean_rt_ms"],
      points.map((p) => [p.participant_code, p.session_order, p.mean_rt]),
    );
  }

  return (
    <ChartCard title="Session-mean RT across session order (IIV-between)" onDownload={download}>
      {rows.length === 0 ? (
        <EmptyChart message="No completed sessions yet." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="order" />
            <YAxis unit=" ms" label={{ value: "Mean RT (ms)", angle: -90, position: "insideLeft" }} />
            <Tooltip />
            <Legend />
            {codes.map((code, i) => (
              <Line
                key={code}
                dataKey={code}
                type="monotone"
                stroke={PALETTE[i % PALETTE.length]}
                connectNulls
                dot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---- (e) accuracy % per participant -----------------------------------------

function AccuracyBarChart({
  studySlug,
  participants,
}: {
  studySlug: string;
  participants: ParticipantSummaryOut[];
}): JSX.Element {
  const bars = useMemo(() => {
    const result: { participant_code: string; accuracy: number }[] = [];
    for (const p of participants) {
      const values = p.sessions
        .map((s) => s.accuracy_pct)
        .filter((a): a is number => a !== null);
      if (values.length > 0) {
        const mean = values.reduce((acc, v) => acc + v, 0) / values.length;
        result.push({ participant_code: p.participant_code, accuracy: Math.round(mean * 10) / 10 });
      }
    }
    return result;
  }, [participants]);

  function download(): void {
    downloadCsv(
      `${studySlug}_accuracy-per-participant.csv`,
      ["participant_code", "mean_accuracy_pct"],
      bars.map((b) => [b.participant_code, b.accuracy]),
    );
  }

  return (
    <ChartCard title="Accuracy % per participant (mean across completed sessions)" onDownload={download}>
      {bars.length === 0 ? (
        <EmptyChart message="No completed sessions yet." />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={bars}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="participant_code" />
            <YAxis domain={[0, 100]} unit="%" />
            <Tooltip />
            <Bar dataKey="accuracy" name="Accuracy %" fill="#16A34A" />
          </BarChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---- sessions table (FR-50) --------------------------------------------------

function SessionsTable({
  studySlug,
  sessions,
  participantCodes,
  statusFilter,
  participantFilter,
  sort,
  onStatusFilter,
  onParticipantFilter,
  onSort,
}: {
  studySlug: string;
  sessions: SessionOut[] | null;
  participantCodes: { id: string; code: string }[];
  statusFilter: SessionStatus | "";
  participantFilter: string;
  sort: SessionSort;
  onStatusFilter: (v: SessionStatus | "") => void;
  onParticipantFilter: (v: string) => void;
  onSort: (v: SessionSort) => void;
}): JSX.Element {
  function download(): void {
    downloadCsv(
      `${studySlug}_sessions.csv`,
      [
        "participant_code",
        "session_order",
        "status",
        "started_at",
        "completed_at",
        "attempt",
        "trimmed_mean_rt_ms",
        "accuracy_pct",
        "n_outliers_flagged",
      ],
      (sessions ?? []).map((s) => [
        s.participant_code,
        s.order_index,
        s.status,
        s.started_at,
        s.completed_at,
        s.attempt,
        s.stats.trimmed_mean_rt_ms,
        s.stats.accuracy_pct,
        s.stats.n_outliers_flagged,
      ]),
    );
  }

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Status">
            <select
              className={selectClass}
              value={statusFilter}
              onChange={(e) => onStatusFilter(e.target.value as SessionStatus | "")}
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
            <select className={selectClass} value={participantFilter} onChange={(e) => onParticipantFilter(e.target.value)}>
              <option value="">All</option>
              {participantCodes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Sort by">
            <select className={selectClass} value={sort} onChange={(e) => onSort(e.target.value as SessionSort)}>
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button variant="secondary" onClick={download}>
          Download CSV
        </Button>
      </div>
      {!sessions ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : sessions.length === 0 ? (
        <p className="text-sm text-gray-500">No sessions match.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">Participant</th>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Started</th>
                <th className="px-4 py-3">Completed</th>
                <th className="px-4 py-3">Attempt</th>
                <th className="px-4 py-3">Trimmed mean RT</th>
                <th className="px-4 py-3">Accuracy</th>
                <th className="px-4 py-3">Outliers</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td className="px-4 py-3 font-mono text-sm text-gray-900">{s.participant_code}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{s.order_index}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{STATUS_LABELS[s.status]}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{formatTimestamp(s.started_at)}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{formatTimestamp(s.completed_at)}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">{s.attempt}</td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {s.stats.trimmed_mean_rt_ms !== null ? `${s.stats.trimmed_mean_rt_ms.toFixed(1)} ms` : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {s.stats.accuracy_pct !== null ? `${s.stats.accuracy_pct.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">{s.stats.n_outliers_flagged}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---- the tab -----------------------------------------------------------------

export default function StudyDashboardTab({ study }: { study: StudyOut }): JSX.Element {
  const [summary, setSummary] = useState<StudySummaryOut | null>(null);
  const [allSessions, setAllSessions] = useState<SessionOut[] | null>(null);
  const [tableSessions, setTableSessions] = useState<SessionOut[] | null>(null);
  const [statusFilter, setStatusFilter] = useState<SessionStatus | "">("");
  const [participantFilter, setParticipantFilter] = useState("");
  const [sort, setSort] = useState<SessionSort>("participant_code");
  const [error, setError] = useState<string | null>(null);

  const studySlug = slugify(study.name);

  useEffect(() => {
    statisticsApi
      .studySummary(study.id)
      .then(setSummary)
      .catch((err: unknown) => setError(errorMessage(err)));
    sessionsApi
      .list(study.id)
      .then(setAllSessions)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id]);

  const reloadTable = useCallback((): void => {
    sessionsApi
      .list(study.id, {
        status: statusFilter === "" ? undefined : statusFilter,
        participantId: participantFilter === "" ? undefined : participantFilter,
        sort,
      })
      .then(setTableSessions)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [study.id, statusFilter, participantFilter, sort]);

  useEffect(() => {
    reloadTable();
  }, [reloadTable]);

  const orderBySessionId = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of allSessions ?? []) {
      map.set(s.id, s.order_index);
    }
    return map;
  }, [allSessions]);

  const completedSessions = useMemo(
    () => (allSessions ?? []).filter((s) => s.status === "completed"),
    [allSessions],
  );

  const participantCodes = useMemo(() => {
    const seen = new Map<string, string>();
    for (const s of allSessions ?? []) {
      if (!seen.has(s.participant_id)) seen.set(s.participant_id, s.participant_code);
    }
    return [...seen.entries()].map(([id, code]) => ({ id, code }));
  }, [allSessions]);

  const lastActivity = useMemo(() => {
    let latest: string | null = null;
    for (const s of allSessions ?? []) {
      for (const ts of [s.last_activity_at, s.completed_at, s.started_at]) {
        if (ts && (!latest || ts > latest)) latest = ts;
      }
    }
    return latest;
  }, [allSessions]);

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} />

      {summary && (
        <section className="grid grid-cols-2 gap-4 rounded-lg border border-gray-200 bg-white p-4 text-sm sm:grid-cols-4">
          <div>
            <p className="font-medium text-gray-500">Participants</p>
            <p className="text-xl font-semibold text-gray-900">{summary.n_participants}</p>
          </div>
          <div>
            <p className="font-medium text-gray-500">Sessions completed</p>
            <p className="text-xl font-semibold text-gray-900">
              {summary.n_sessions_completed}/{summary.n_sessions_total}
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-500">Completion</p>
            <p className="text-xl font-semibold text-gray-900">{summary.completion_pct.toFixed(0)}%</p>
          </div>
          <div>
            <p className="font-medium text-gray-500">Last activity</p>
            <p className="text-xl font-semibold text-gray-900">{formatTimestamp(lastActivity)}</p>
          </div>
        </section>
      )}

      <SessionsTable
        studySlug={studySlug}
        sessions={tableSessions}
        participantCodes={participantCodes}
        statusFilter={statusFilter}
        participantFilter={participantFilter}
        sort={sort}
        onStatusFilter={setStatusFilter}
        onParticipantFilter={setParticipantFilter}
        onSort={setSort}
      />

      {summary && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <RtHistogram studySlug={studySlug} completedSessions={completedSessions} />
          <MeanRtStripPlot
            studySlug={studySlug}
            participants={summary.participants}
            orderBySessionId={orderBySessionId}
          />
          <IivWithinBarChart
            studySlug={studySlug}
            participants={summary.participants}
            orderBySessionId={orderBySessionId}
          />
          <MeanRtLineChart
            studySlug={studySlug}
            participants={summary.participants}
            orderBySessionId={orderBySessionId}
          />
          <AccuracyBarChart studySlug={studySlug} participants={summary.participants} />
        </div>
      )}
    </div>
  );
}
