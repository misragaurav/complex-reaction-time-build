import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { exportsApi } from "../api/exports";
import { studiesApi } from "../api/studies";
import type { StudyOut } from "../api/types";
import { Button, ErrorBanner } from "../components/forms";
import { downloadBlob } from "../utils/download";
import StudyDashboardTab from "./StudyDashboardTab";
import StudyDemographicsTab from "./StudyDemographicsTab";
import StudyParticipantsTab from "./StudyParticipantsTab";
import StudySessionsTab from "./StudySessionsTab";
import StudySettingsTab from "./StudySettingsTab";

const TABS = ["settings", "demographics", "participants", "sessions", "dashboard"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  settings: "Settings",
  demographics: "Demographics",
  participants: "Participants",
  sessions: "Sessions",
  dashboard: "Dashboard",
};

function isTab(value: string | null): value is Tab {
  return TABS.includes(value as Tab);
}

function StudyDetail({ studyId }: { studyId: string }): JSX.Element {
  const [study, setStudy] = useState<StudyOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const tabParam = searchParams.get("tab");
  const tab: Tab = isTab(tabParam) ? tabParam : "settings";

  useEffect(() => {
    studiesApi
      .get(studyId)
      .then(setStudy)
      .catch((err: unknown) => setError(errorMessage(err)));
  }, [studyId]);

  async function exportZip(): Promise<void> {
    setError(null);
    setExporting(true);
    try {
      downloadBlob(await exportsApi.studyZip(studyId), "study_export.zip");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  if (error && !study) {
    return <ErrorBanner message={error} />;
  }

  if (!study) {
    return <p className="text-sm text-gray-500">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {study.name}
            {study.is_archived && (
              <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                Archived
              </span>
            )}
          </h1>
          {study.description && <p className="text-sm text-gray-500">{study.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => navigate(`/studies/${studyId}/preview`)}>
            Preview task
          </Button>
          <Button variant="secondary" onClick={() => void exportZip()} loading={exporting}>
            Export study data (ZIP)
          </Button>
        </div>
      </div>

      <ErrorBanner message={error} />

      <nav className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setSearchParams({ tab: t })}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              t === tab
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </nav>

      {tab === "settings" && <StudySettingsTab study={study} onChange={setStudy} />}
      {tab === "demographics" && <StudyDemographicsTab study={study} />}
      {tab === "participants" && <StudyParticipantsTab study={study} />}
      {tab === "sessions" && <StudySessionsTab study={study} />}
      {tab === "dashboard" && <StudyDashboardTab study={study} />}
    </div>
  );
}

export default function StudyDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  if (!id) return <Navigate to="/studies" replace />;
  return <StudyDetail key={id} studyId={id} />;
}
