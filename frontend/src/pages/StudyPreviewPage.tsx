import { useCallback, useEffect, useReducer, useRef } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { exportsApi } from "../api/exports";
import type { Block, TaskParams, TaskType } from "../api/types";
import { Button, ErrorBanner } from "../components/forms";
import { renderInstructions } from "../task/instructions";
import { createRng } from "../task/rng";
import { BlockRunner, type BlockProgress } from "../task/sessionRunner";
import TaskCanvas, { KeyMappingDiagram } from "../task/TaskCanvas";
import { realClock, type EngineSnapshot } from "../task/trialEngine";

type PreviewPhase =
  | "loading"
  | "error"
  | "instructions"
  | "practice"
  | "interstitial"
  | "test"
  | "completed";

interface PreviewState {
  phase: PreviewPhase;
  error: string | null;
  params: TaskParams | null;
  taskType: TaskType | null;
  snapshot: EngineSnapshot | null;
  progress: BlockProgress | null;
  paused: boolean;
}

const initialState: PreviewState = {
  phase: "loading",
  error: null,
  params: null,
  taskType: null,
  snapshot: null,
  progress: null,
  paused: false,
};

type Action =
  | { type: "loaded"; params: TaskParams; taskType: TaskType }
  | { type: "error"; message: string }
  | { type: "block-start"; block: Block }
  | { type: "snapshot"; snapshot: EngineSnapshot }
  | { type: "progress"; progress: BlockProgress }
  | { type: "paused" }
  | { type: "resumed" }
  | { type: "practice-done" }
  | { type: "completed" };

function reducer(state: PreviewState, action: Action): PreviewState {
  switch (action.type) {
    case "loaded":
      return { ...state, phase: "instructions", params: action.params, taskType: action.taskType };
    case "error":
      return { ...state, phase: "error", error: action.message };
    case "block-start":
      return { ...state, phase: action.block, snapshot: null, progress: null, paused: false };
    case "snapshot":
      return { ...state, snapshot: action.snapshot };
    case "progress":
      return { ...state, progress: action.progress };
    case "paused":
      return { ...state, paused: true };
    case "resumed":
      return { ...state, paused: false };
    case "practice-done":
      return { ...state, phase: "interstitial", snapshot: null, progress: null };
    case "completed":
      return { ...state, phase: "completed", snapshot: null, progress: null };
    default:
      return state;
  }
}

function requestFullscreenIfNeeded(): void {
  if (document.fullscreenElement) return;
  document.documentElement.requestFullscreen?.().catch(() => {});
}

function CenteredScreen({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-white px-6 py-12 text-center">
      <div className="w-full max-w-xl space-y-6">{children}</div>
    </div>
  );
}

/**
 * FR-33: the exact task client (same BlockRunner/TaskCanvas as `/run`) with
 * practice and test shortened server-side to <=3 trials each. No session is
 * created and nothing is uploaded -- results are discarded.
 */
function PreviewRunner({ studyId }: { studyId: string }): JSX.Element {
  const [state, dispatch] = useReducer(reducer, initialState);
  const navigate = useNavigate();

  const phaseRef = useRef<PreviewPhase>(state.phase);
  phaseRef.current = state.phase;
  const paramsRef = useRef<TaskParams | null>(null);
  const blockRunnerRef = useRef<BlockRunner | null>(null);
  const lastSnapshotRef = useRef<EngineSnapshot | null>(null);

  useEffect(() => {
    exportsApi
      .preview(studyId)
      .then((res) => {
        paramsRef.current = res.params;
        dispatch({ type: "loaded", params: res.params, taskType: res.task_type });
      })
      .catch((err: unknown) => dispatch({ type: "error", message: errorMessage(err) }));
  }, [studyId]);

  // Same FR-45/46 handling as the real runner so the preview behaves identically.
  useEffect(() => {
    const inActiveBlock = (): boolean => phaseRef.current === "practice" || phaseRef.current === "test";
    const inResponseWindow = (): boolean => {
      const p = lastSnapshotRef.current?.phase;
      return p === "foreperiod" || p === "stimulus";
    };
    const onFullscreenChange = (): void => {
      if (inActiveBlock() && !document.fullscreenElement) {
        blockRunnerRef.current?.invalidate("fullscreen_exit");
      }
    };
    const onFocusLoss = (): void => {
      if (inActiveBlock() && inResponseWindow()) {
        blockRunnerRef.current?.invalidate("focus_loss");
      }
    };
    const onVisibilityChange = (): void => {
      if (document.hidden) onFocusLoss();
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    window.addEventListener("blur", onFocusLoss);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      document.removeEventListener("fullscreenchange", onFullscreenChange);
      window.removeEventListener("blur", onFocusLoss);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  useEffect(() => {
    const onKeydown = (e: KeyboardEvent): void => {
      if (phaseRef.current !== "practice" && phaseRef.current !== "test") return;
      if (paramsRef.current?.key_map.includes(e.code)) e.preventDefault();
      blockRunnerRef.current?.handleKeydown(e.code, e.timeStamp, e.repeat);
    };
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, []);

  useEffect(() => () => blockRunnerRef.current?.dispose(), []);

  const runBlock = useCallback((block: Block): void => {
    const params = paramsRef.current;
    if (!params) return;
    const runner = new BlockRunner(
      {
        block,
        blockSize: block === "practice" ? params.practice_trials : params.test_trials,
        params,
        rng: createRng(),
        clock: realClock,
      },
      {
        onSnapshot: (snapshot) => {
          lastSnapshotRef.current = snapshot;
          dispatch({ type: "snapshot", snapshot });
        },
        onTrialComplete: (result, progress) => {
          dispatch({ type: "progress", progress });
          if (result.outcome === "invalid") {
            dispatch({ type: "paused" });
          }
        },
        onBlockComplete: () => {
          dispatch(block === "practice" ? { type: "practice-done" } : { type: "completed" });
        },
      },
    );
    blockRunnerRef.current = runner;
    runner.start();
  }, []);

  const startBlock = useCallback(
    (block: Block): void => {
      requestFullscreenIfNeeded();
      dispatch({ type: "block-start", block });
      runBlock(block);
    },
    [runBlock],
  );

  const resume = useCallback((): void => {
    requestFullscreenIfNeeded();
    dispatch({ type: "resumed" });
    blockRunnerRef.current?.resume();
  }, []);

  switch (state.phase) {
    case "loading":
      return (
        <CenteredScreen>
          <p className="text-sm text-gray-500">Loading…</p>
        </CenteredScreen>
      );

    case "error":
      return (
        <CenteredScreen>
          <ErrorBanner message={state.error} />
          <Button variant="secondary" onClick={() => navigate(`/studies/${studyId}`)}>
            Back to study
          </Button>
        </CenteredScreen>
      );

    case "instructions": {
      const params = state.params;
      if (!params) return <CenteredScreen>{null}</CenteredScreen>;
      return (
        <CenteredScreen>
          <p className="text-sm font-medium uppercase tracking-wide text-gray-400">Preview — no data is recorded</p>
          <h1 className="text-xl font-semibold text-gray-900">Instructions</h1>
          <p className="text-base leading-relaxed text-gray-800">{renderInstructions(params.instructions_text, params)}</p>
          <KeyMappingDiagram keyMap={params.key_map} />
          <Button onClick={() => startBlock("practice")}>Start practice</Button>
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
          {state.paused && (
            <div className="fixed inset-0 z-10 flex items-center justify-center bg-white/90">
              <div className="space-y-4 text-center">
                <p className="text-lg text-gray-900">Press Continue to re-enter fullscreen</p>
                <Button onClick={resume}>Continue</Button>
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
          <Button onClick={() => startBlock("test")}>Start test</Button>
        </CenteredScreen>
      );

    case "completed":
      return (
        <CenteredScreen>
          <p className="text-lg text-gray-900">Preview complete. No data was recorded.</p>
          <Button onClick={() => navigate(`/studies/${studyId}`)}>Back to study</Button>
        </CenteredScreen>
      );

    default:
      return <CenteredScreen>{null}</CenteredScreen>;
  }
}

export default function StudyPreviewPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  if (!id) return <Navigate to="/studies" replace />;
  return <PreviewRunner key={id} studyId={id} />;
}
