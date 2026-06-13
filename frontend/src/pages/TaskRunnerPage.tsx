import type { FormEvent, ReactNode } from "react";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import type { DemographicAnswerIn, DemographicFieldPublic } from "../api/types";
import { DEVICE_BLOCKED_MESSAGE } from "../task/deviceGate";
import { renderInstructions } from "../task/instructions";
import TaskCanvas, { KeyMappingDiagram } from "../task/TaskCanvas";
import { useTaskRunner } from "../task/useTaskRunner";
import { Button, ErrorBanner, Field, inputClass } from "../components/forms";

function CenteredScreen({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-6 py-12 text-center">
      <div className="w-full max-w-xl space-y-6">{children}</div>
    </div>
  );
}

function DemographicsForm({
  fields,
  onSubmit,
}: {
  fields: DemographicFieldPublic[];
  onSubmit: (answers: DemographicAnswerIn[]) => Promise<void>;
}): JSX.Element {
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function setValue(id: string, value: string): void {
    setValues((prev) => ({ ...prev, [id]: value }));
  }

  async function handleSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    for (const field of fields) {
      const value = values[field.id]?.trim() ?? "";
      if (field.required && value === "") {
        setError(`Please answer "${field.label}".`);
        return;
      }
      if (field.field_type === "number" && value !== "" && !Number.isFinite(Number(value))) {
        setError(`"${field.label}" must be a number.`);
        return;
      }
    }
    setError(null);
    setSubmitting(true);
    try {
      const answers: DemographicAnswerIn[] = fields
        .filter((f) => (values[f.id]?.trim() ?? "") !== "")
        .map((f) => ({ field_id: f.id, value: (values[f.id] ?? "").trim() }));
      await onSubmit(answers);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 text-left">
      {fields.map((field) => (
        <Field key={field.id} label={field.required ? `${field.label} *` : field.label}>
          {field.field_type === "text" && (
            <input
              type="text"
              className={inputClass}
              value={values[field.id] ?? ""}
              onChange={(e) => setValue(field.id, e.target.value)}
            />
          )}
          {field.field_type === "number" && (
            <input
              type="number"
              className={inputClass}
              value={values[field.id] ?? ""}
              onChange={(e) => setValue(field.id, e.target.value)}
            />
          )}
          {field.field_type === "single_choice" && (
            <div className="space-y-1">
              {(field.options ?? []).map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name={field.id}
                    value={opt}
                    checked={values[field.id] === opt}
                    onChange={() => setValue(field.id, opt)}
                  />
                  {opt}
                </label>
              ))}
            </div>
          )}
          {field.field_type === "boolean" && (
            <div className="flex gap-4">
              {(["true", "false"] as const).map((opt) => (
                <label key={opt} className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="radio"
                    name={field.id}
                    value={opt}
                    checked={values[field.id] === opt}
                    onChange={() => setValue(field.id, opt)}
                  />
                  {opt === "true" ? "Yes" : "No"}
                </label>
              ))}
            </div>
          )}
        </Field>
      ))}
      <ErrorBanner message={error} />
      <Button type="submit" loading={submitting}>
        Continue
      </Button>
    </form>
  );
}

function TaskRunner({ sessionId }: { sessionId: string }): JSX.Element {
  const { state, actions } = useTaskRunner(sessionId);
  const navigate = useNavigate();

  switch (state.phase) {
    case "loading":
      return (
        <CenteredScreen>
          <p className="text-sm text-gray-500">Loading…</p>
        </CenteredScreen>
      );

    case "blocked-device":
      return (
        <CenteredScreen>
          <p className="text-base text-gray-800">{DEVICE_BLOCKED_MESSAGE}</p>
          <Button variant="secondary" onClick={() => navigate("/login")}>
            Back to login
          </Button>
        </CenteredScreen>
      );

    case "error":
      return (
        <CenteredScreen>
          <ErrorBanner message={state.error} />
          <Button variant="secondary" onClick={() => navigate("/me")}>
            Back to my sessions
          </Button>
        </CenteredScreen>
      );

    case "demographics":
      return (
        <CenteredScreen>
          <h1 className="text-xl font-semibold text-gray-900">A few questions before you begin</h1>
          <DemographicsForm fields={state.demographicsDue} onSubmit={actions.submitDemographics} />
        </CenteredScreen>
      );

    case "instructions": {
      const params = state.params;
      if (!params) return <CenteredScreen>{null}</CenteredScreen>;
      return (
        <CenteredScreen>
          <h1 className="text-xl font-semibold text-gray-900">Instructions</h1>
          <p className="text-base leading-relaxed text-gray-800">{renderInstructions(params.instructions_text, params)}</p>
          <KeyMappingDiagram keyMap={params.key_map} />
          <Button onClick={actions.startPractice}>Start practice</Button>
        </CenteredScreen>
      );
    }

    case "practice":
    case "test": {
      const params = state.params;
      if (!params) return <CenteredScreen>{null}</CenteredScreen>;
      return (
        <>
          <TaskCanvas
            nPositions={params.key_map.length}
            snapshot={state.snapshot}
            showProgress={params.show_progress}
            progress={state.progress}
          />
          {state.bufferWarning && (
            <div className="fixed left-2 top-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700 shadow">
              Connection is slow — your responses are being saved and will sync automatically.
            </div>
          )}
          {state.pendingReentry && (
            <div className="fixed inset-0 z-10 flex items-center justify-center bg-white/90">
              <div className="space-y-4 text-center">
                <p className="text-lg text-gray-900">Press Continue to re-enter fullscreen</p>
                <Button onClick={actions.reenterFullscreen}>Continue</Button>
              </div>
            </div>
          )}
        </>
      );
    }

    case "interstitial":
      return (
        <CenteredScreen>
          <p className="text-lg text-gray-900">
            Practice complete. The real test starts now. Respond as quickly and as accurately as you can.
          </p>
          <Button onClick={actions.startTest}>Start test</Button>
        </CenteredScreen>
      );

    case "completing":
      return (
        <CenteredScreen>
          <p className="text-lg text-gray-900">Submitting your results…</p>
        </CenteredScreen>
      );

    case "completed":
      return (
        <CenteredScreen>
          <p className="text-lg text-gray-900">Session complete. Thank you!</p>
          <Button onClick={() => navigate("/me")}>Back to my sessions</Button>
        </CenteredScreen>
      );

    default:
      return <CenteredScreen>{null}</CenteredScreen>;
  }
}

export default function TaskRunnerPage(): JSX.Element {
  const { sessionId } = useParams<{ sessionId: string }>();
  if (!sessionId) return <Navigate to="/me" replace />;
  return <TaskRunner key={sessionId} sessionId={sessionId} />;
}
