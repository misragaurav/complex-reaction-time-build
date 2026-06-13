import { useCallback, useEffect, useReducer, useRef } from "react";
import { errorMessage } from "../api/client";
import { runtimeApi } from "../api/runtime";
import type {
  Block,
  DemographicAnswerIn,
  DemographicFieldPublic,
  InvalidReason,
  StoredTrials,
  TaskParams,
  TaskType,
  TrialIn,
} from "../api/types";
import { isDeviceBlocked } from "./deviceGate";
import { measureRefreshRate } from "./refreshRate";
import { createRng } from "./rng";
import { BlockRunner, computeResumeState, type BlockProgress } from "./sessionRunner";
import { realClock, type EngineSnapshot } from "./trialEngine";
import { TrialUploadQueue } from "./uploadQueue";

export type RunnerPhase =
  | "loading"
  | "blocked-device"
  | "error"
  | "demographics"
  | "instructions"
  | "practice"
  | "interstitial"
  | "test"
  | "completing"
  | "completed";

export interface RunnerState {
  phase: RunnerPhase;
  error: string | null;
  params: TaskParams | null;
  taskType: TaskType | null;
  demographicsDue: DemographicFieldPublic[];
  snapshot: EngineSnapshot | null;
  progress: BlockProgress | null;
  pendingReentry: InvalidReason | null;
  bufferWarning: boolean;
}

const initialState: RunnerState = {
  phase: "loading",
  error: null,
  params: null,
  taskType: null,
  demographicsDue: [],
  snapshot: null,
  progress: null,
  pendingReentry: null,
  bufferWarning: false,
};

type Action =
  | { type: "blocked" }
  | { type: "loaded"; params: TaskParams; taskType: TaskType; demographicsDue: DemographicFieldPublic[] }
  | { type: "error"; message: string }
  | { type: "demographics-done" }
  | { type: "practice-start" }
  | { type: "snapshot"; snapshot: EngineSnapshot }
  | { type: "progress"; progress: BlockProgress }
  | { type: "invalidated"; reason: InvalidReason }
  | { type: "reentered" }
  | { type: "practice-done" }
  | { type: "test-start" }
  | { type: "completing" }
  | { type: "completed" }
  | { type: "buffer-warning" };

function reducer(state: RunnerState, action: Action): RunnerState {
  switch (action.type) {
    case "blocked":
      return { ...state, phase: "blocked-device" };
    case "loaded":
      return {
        ...state,
        phase: action.demographicsDue.length > 0 ? "demographics" : "instructions",
        params: action.params,
        taskType: action.taskType,
        demographicsDue: action.demographicsDue,
      };
    case "error":
      return { ...state, phase: "error", error: action.message };
    case "demographics-done":
      return { ...state, phase: "instructions", demographicsDue: [] };
    case "practice-start":
      return { ...state, phase: "practice", snapshot: null, progress: null, pendingReentry: null };
    case "snapshot":
      return { ...state, snapshot: action.snapshot };
    case "progress":
      return { ...state, progress: action.progress };
    case "invalidated":
      return { ...state, pendingReentry: action.reason };
    case "reentered":
      return { ...state, pendingReentry: null };
    case "practice-done":
      return { ...state, phase: "interstitial", snapshot: null, progress: null };
    case "test-start":
      return { ...state, phase: "test", snapshot: null, progress: null, pendingReentry: null };
    case "completing":
      return { ...state, phase: "completing" };
    case "completed":
      return { ...state, phase: "completed" };
    case "buffer-warning":
      return { ...state, bufferWarning: true };
    default:
      return state;
  }
}

/** `crypto.randomUUID` requires a secure context (https or localhost); fall
 * back to a standard RFC4122 v4 generator so trial uploads (keyed on
 * `client_uuid`, FR-34) work on plain-http deployments too. */
function randomUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function requestFullscreenIfNeeded(): void {
  if (document.fullscreenElement) return;
  document.documentElement.requestFullscreen?.().catch(() => {});
}

/** FR-43: best-effort, never blocks the task. */
async function recordClientEnv(sessionId: string): Promise<void> {
  try {
    const refreshRateHz = await measureRefreshRate(realClock);
    await runtimeApi.submitClientEnv(sessionId, {
      user_agent: navigator.userAgent,
      screen_width: window.screen.width,
      screen_height: window.screen.height,
      device_pixel_ratio: window.devicePixelRatio,
      refresh_rate_hz: refreshRateHz,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
  } catch {
    /* data-quality auditing only */
  }
}

export interface RunnerActions {
  submitDemographics: (answers: DemographicAnswerIn[]) => Promise<void>;
  startPractice: () => void;
  startTest: () => void;
  reenterFullscreen: () => void;
}

/**
 * Orchestrates the full `/run/:sessionId` flow: device gate -> `/start` ->
 * demographics -> instructions -> practice -> interstitial -> test ->
 * `/complete`. Wires `BlockRunner`/`TrialUploadQueue` to real browser APIs
 * (keyboard, fullscreen, focus, page-unload).
 */
export function useTaskRunner(sessionId: string): { state: RunnerState; actions: RunnerActions } {
  const [state, dispatch] = useReducer(reducer, initialState);

  const phaseRef = useRef<RunnerPhase>(state.phase);
  phaseRef.current = state.phase;

  const startedRef = useRef(false);
  const paramsRef = useRef<TaskParams | null>(null);
  const attemptRef = useRef(1);
  const storedTrialsRef = useRef<StoredTrials>({ practice: [], test: [] });
  const blockRunnerRef = useRef<BlockRunner | null>(null);
  const uploadQueueRef = useRef<TrialUploadQueue | null>(null);
  const lastSnapshotRef = useRef<EngineSnapshot | null>(null);

  // ---- device gate -> /start ----
  useEffect(() => {
    if (isDeviceBlocked()) {
      dispatch({ type: "blocked" });
      return;
    }
    if (startedRef.current) return;
    startedRef.current = true;

    uploadQueueRef.current = new TrialUploadQueue(sessionId, () => dispatch({ type: "buffer-warning" }));
    runtimeApi
      .start(sessionId)
      .then((res) => {
        paramsRef.current = res.params;
        attemptRef.current = res.attempt;
        storedTrialsRef.current = res.stored_trials;
        dispatch({ type: "loaded", params: res.params, taskType: res.task_type, demographicsDue: res.demographics_due });
        void recordClientEnv(sessionId);
      })
      .catch((err: unknown) => {
        dispatch({ type: "error", message: errorMessage(err) });
      });
  }, [sessionId]);

  // ---- FR-34: flush buffered trials on tab hide / page unload ----
  useEffect(() => {
    const flushNow = (): void => uploadQueueRef.current?.flushOnUnload();
    const onVisibility = (): void => {
      if (document.hidden) flushNow();
    };
    window.addEventListener("pagehide", flushNow);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pagehide", flushNow);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  // ---- FR-45/46: fullscreen exit / focus loss invalidation ----
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

  // ---- keyboard input -> active trial (FR-28) ----
  useEffect(() => {
    const onKeydown = (e: KeyboardEvent): void => {
      if (phaseRef.current !== "practice" && phaseRef.current !== "test") return;
      if (paramsRef.current?.key_map.includes(e.code)) e.preventDefault();
      blockRunnerRef.current?.handleKeydown(e.code, e.timeStamp, e.repeat);
    };
    document.addEventListener("keydown", onKeydown);
    return () => document.removeEventListener("keydown", onKeydown);
  }, []);

  // ---- cleanup ----
  useEffect(
    () => () => {
      blockRunnerRef.current?.dispose();
      uploadQueueRef.current?.flushOnUnload();
    },
    [],
  );

  const finishSession = useCallback(async (): Promise<void> => {
    dispatch({ type: "completing" });
    try {
      await uploadQueueRef.current?.flush();
      await runtimeApi.complete(sessionId);
      dispatch({ type: "completed" });
    } catch (err) {
      dispatch({ type: "error", message: errorMessage(err) });
    }
  }, [sessionId]);

  const runBlock = useCallback(
    (block: Block): void => {
      const params = paramsRef.current;
      if (!params) return;
      const blockSize = block === "practice" ? params.practice_trials : params.test_trials;
      const stored = block === "practice" ? storedTrialsRef.current.practice : storedTrialsRef.current.test;
      const { queue, invalidationCount } = computeResumeState(blockSize, stored);

      const runner = new BlockRunner(
        {
          block,
          blockSize,
          params,
          rng: createRng(),
          clock: realClock,
          initialQueue: queue,
          initialInvalidationCount: invalidationCount,
        },
        {
          onSnapshot: (snapshot) => {
            lastSnapshotRef.current = snapshot;
            dispatch({ type: "snapshot", snapshot });
          },
          onTrialComplete: (result, progress) => {
            dispatch({ type: "progress", progress });
            if (result.outcome === "invalid" && result.invalid_reason) {
              dispatch({ type: "invalidated", reason: result.invalid_reason });
            }
            const trial: TrialIn = {
              client_uuid: randomUuid(),
              attempt: attemptRef.current,
              block: result.block,
              trial_index: result.trial_index,
              stimulus_position: result.stimulus_position,
              foreperiod_ms: result.foreperiod_ms,
              key_pressed: result.key_pressed,
              response_position: result.response_position,
              outcome: result.outcome,
              rt_ms: result.rt_ms,
              premature_count: result.premature_count,
              extraneous_keys: result.extraneous_keys,
              invalid_reason: result.invalid_reason,
              stimulus_onset_client_ms: result.stimulus_onset_client_ms,
              response_client_ms: result.response_client_ms,
            };
            uploadQueueRef.current?.push(trial);
          },
          onBlockComplete: () => {
            if (block === "practice") {
              void uploadQueueRef.current?.flush();
              dispatch({ type: "practice-done" });
            } else {
              void finishSession();
            }
          },
        },
      );
      blockRunnerRef.current = runner;
      runner.start();
    },
    [finishSession],
  );

  const submitDemographics = useCallback(
    async (answers: DemographicAnswerIn[]): Promise<void> => {
      await runtimeApi.submitDemographics(sessionId, { answers });
      dispatch({ type: "demographics-done" });
    },
    [sessionId],
  );

  const startPractice = useCallback((): void => {
    requestFullscreenIfNeeded();
    dispatch({ type: "practice-start" });
    runBlock("practice");
  }, [runBlock]);

  const startTest = useCallback((): void => {
    requestFullscreenIfNeeded();
    dispatch({ type: "test-start" });
    runBlock("test");
  }, [runBlock]);

  const reenterFullscreen = useCallback((): void => {
    requestFullscreenIfNeeded();
    dispatch({ type: "reentered" });
    blockRunnerRef.current?.resume();
  }, []);

  return {
    state,
    actions: { submitDemographics, startPractice, startTest, reenterFullscreen },
  };
}
