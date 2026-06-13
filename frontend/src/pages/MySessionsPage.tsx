import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { sessionsApi } from "../api/sessions";
import type { MySessionOut, SessionStatus, TaskType } from "../api/types";
import { Button, ErrorBanner } from "../components/forms";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

const STATUS_LABELS: Record<SessionStatus, string> = {
  created: "Not started",
  in_progress: "In progress",
  abandoned: "In progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

const STATUS_BADGE_CLASSES: Record<SessionStatus, string> = {
  created: "bg-gray-100 text-gray-600",
  in_progress: "bg-blue-100 text-blue-700",
  abandoned: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-gray-100 text-gray-400",
};

export default function MySessionsPage(): JSX.Element {
  const [sessions, setSessions] = useState<MySessionOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    sessionsApi
      .listMine()
      .then(setSessions)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, []);

  if (error) {
    return <ErrorBanner message={error} />;
  }

  if (!sessions) {
    return <p className="text-sm text-gray-500">Loading…</p>;
  }

  // The earliest non-completed session in order_index order is the only one
  // that can be started/resumed; it also names the session that later rows
  // are waiting on (mirrors the `locked` flag computed by GET /me/sessions).
  const blocking = sessions.find((s) => s.status !== "completed");

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">My sessions</h1>
      {sessions.length === 0 ? (
        <p className="text-sm text-gray-500">No sessions assigned yet. Contact your researcher.</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {sessions.map((session) => (
            <li key={session.id} className="flex items-center justify-between gap-4 px-4 py-4">
              <div>
                <p className="font-medium text-gray-900">Session {session.order_index}</p>
                <p className="text-sm text-gray-500">{TASK_TYPE_LABELS[session.task_type]}</p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[session.status]}`}
                >
                  {STATUS_LABELS[session.status]}
                </span>
                {session.status !== "completed" && !session.locked && (
                  <Button onClick={() => navigate(`/run/${session.id}`)}>
                    {session.status === "created" ? "Start" : "Resume"}
                  </Button>
                )}
                {session.status !== "completed" && session.locked && blocking && (
                  <span className="text-sm text-gray-400">Complete session {blocking.order_index} first</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
