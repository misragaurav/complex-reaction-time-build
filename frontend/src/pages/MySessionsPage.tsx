import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { sessionsApi } from "../api/sessions";
import type { MySessionOut, SessionStatus, SessionType, TaskType } from "../api/types";
import { Button, ErrorBanner } from "../components/forms";

const TASK_TYPE_LABELS: Record<TaskType, string> = {
  SRT: "Simple reaction time", // MOD-2
  CRT2: "2-choice reaction time",
  CRT3: "3-choice reaction time",
  CRT4: "4-choice reaction time",
};

// MOD-3 / MFR-19: session-type chip colours.
const SESSION_TYPE_LABELS: Record<SessionType, string> = {
  onboarding: "Onboarding",
  pre: "Pre",
  post: "Post",
};

const SESSION_TYPE_CHIP_CLASSES: Record<SessionType, string> = {
  onboarding: "bg-gray-100 text-gray-600",
  pre: "bg-blue-100 text-blue-700",
  post: "bg-green-100 text-green-700",
};

// MOD-5: six-state participant view driven by status.
const STATUS_LABELS: Record<SessionStatus, string> = {
  created: "Locked",
  activated: "Ready",
  in_progress: "In progress",
  abandoned: "In progress",
  completed: "Done",
  expired: "Missed",
  cancelled: "Cancelled",
};

const STATUS_BADGE_CLASSES: Record<SessionStatus, string> = {
  created: "bg-gray-100 text-gray-400",
  activated: "bg-green-100 text-green-700",
  in_progress: "bg-blue-100 text-blue-700",
  abandoned: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  expired: "bg-red-100 text-red-600",
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

  // MOD-5: hide cancelled; button shown only for activated/in_progress/abandoned.
  const visible = sessions.filter((s) => s.status !== "cancelled");

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold text-gray-900">My sessions</h1>
      {visible.length === 0 ? (
        <p className="text-sm text-gray-500">No sessions assigned yet. Contact your researcher.</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
          {visible.map((session) => {
            const canStart = session.status === "activated";
            const canResume = session.status === "in_progress" || session.status === "abandoned";
            const rowHighlight = session.status === "activated" ? "bg-green-50" : "";
            return (
              <li
                key={session.id}
                className={`flex items-center justify-between gap-4 px-4 py-4 ${rowHighlight}`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-gray-900">{session.display_label}</p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${SESSION_TYPE_CHIP_CLASSES[session.session_type]}`}
                    >
                      {SESSION_TYPE_LABELS[session.session_type]}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500">{TASK_TYPE_LABELS[session.task_type]}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[session.status]}`}
                  >
                    {STATUS_LABELS[session.status]}
                  </span>
                  {canStart && (
                    <Button onClick={() => navigate(`/run/${session.id}`)}>Start</Button>
                  )}
                  {canResume && (
                    <Button onClick={() => navigate(`/run/${session.id}`)}>Resume</Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
