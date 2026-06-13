import type { Block, InvalidReason, Outcome } from "../api/types";

/**
 * Abstraction over `performance.now`/`requestAnimationFrame`/`setTimeout` so
 * the trial state machine can be driven by a fake clock in tests (NFR-1)
 * without touching the DOM.
 */
export interface EngineClock {
  now: () => number;
  requestFrame: (cb: (time: number) => void) => number;
  cancelFrame: (handle: number) => void;
  setTimeout: (cb: () => void, ms: number) => number;
  clearTimeout: (handle: number) => void;
}

export const realClock: EngineClock = {
  now: () => performance.now(),
  requestFrame: (cb) => requestAnimationFrame(cb),
  cancelFrame: (handle) => cancelAnimationFrame(handle),
  setTimeout: (cb, ms) => window.setTimeout(cb, ms),
  clearTimeout: (handle) => window.clearTimeout(handle),
};

export type EnginePhase = "iti" | "foreperiod" | "stimulus" | "feedback";
export type FeedbackKind = "incorrect" | "timeout" | "too_soon";

/** Visual state for one trial, enough for the UI to render §5.1's layout. */
export interface EngineSnapshot {
  phase: EnginePhase;
  /** 0-based stimulus position currently showing the box, or null (all crosses). */
  boxPosition: number | null;
  feedback: FeedbackKind | null;
}

/** One completed trial row, matching `TrialIn` minus the fields the
 * orchestrator fills in (`client_uuid`, `attempt`). */
export interface TrialResult {
  block: Block;
  trial_index: number;
  stimulus_position: number;
  foreperiod_ms: number;
  key_pressed: string | null;
  response_position: number | null;
  outcome: Outcome;
  rt_ms: number | null;
  premature_count: number;
  extraneous_keys: number;
  invalid_reason: InvalidReason | null;
  stimulus_onset_client_ms: number | null;
  response_client_ms: number | null;
}

export interface TrialConfig {
  block: Block;
  /** 1-based index within the block; carried through to `TrialResult`. */
  trialIndex: number;
  /** 0-based position (0..nPositions-1) the box will appear at. */
  stimulusPosition: number;
  itiMs: number;
  responseTimeoutMs: number;
  feedbackDurationMs: number;
  practiceFeedback: boolean;
  /** `KeyboardEvent.code` values, index = stimulus position. */
  keyMap: string[];
  /** Draws a fresh foreperiod duration (FR-26); called again on FR-29 redraws. */
  drawForeperiod: () => number;
}

export interface TrialEngineCallbacks {
  onSnapshot: (snapshot: EngineSnapshot) => void;
  onComplete: (result: TrialResult) => void;
}

const TOO_SOON_DURATION_MS = 1000;

/** Rounds an RT to 1 decimal place (FR-27), clamping away tiny negative noise. */
function roundRt(ms: number): number {
  return Math.round(Math.max(0, ms) * 10) / 10;
}

interface FinishArgs {
  key_pressed: string | null;
  response_position: number | null;
  outcome: Outcome;
  rt_ms: number | null;
  response_client_ms: number | null;
  invalid_reason?: InvalidReason;
}

/**
 * Drives a single trial through §5.5's state machine:
 * ITI -> FOREPERIOD -> STIMULUS -> (RESPONSE | TIMEOUT) -> [FEEDBACK] -> done.
 */
export class TrialEngine {
  private phase: EnginePhase = "iti";
  private foreperiodMs: number;
  private prematureCount = 0;
  private extraneousKeys = 0;
  private onsetClientMs: number | null = null;
  private done = false;

  private timeoutHandle: number | null = null;
  private frameHandle: number | null = null;
  private feedbackTimeoutHandle: number | null = null;

  constructor(
    private readonly config: TrialConfig,
    private readonly clock: EngineClock,
    private readonly callbacks: TrialEngineCallbacks,
  ) {
    this.foreperiodMs = config.drawForeperiod();
  }

  start(): void {
    this.phase = "iti";
    this.emit(null);
    this.timeoutHandle = this.clock.setTimeout(() => this.beginForeperiod(), this.config.itiMs);
  }

  handleKeydown(code: string, timestamp: number, repeat: boolean): void {
    if (this.done || repeat) return;

    const responsePosition = this.config.keyMap.indexOf(code);
    const isMapped = responsePosition !== -1;

    switch (this.phase) {
      case "iti":
        if (isMapped) {
          this.prematureCount += 1;
          this.flashTooSoonDuring("iti");
        } else {
          this.extraneousKeys += 1;
        }
        return;

      case "foreperiod":
        if (isMapped) {
          this.prematureCount += 1;
          this.restartForeperiod();
        } else {
          this.extraneousKeys += 1;
        }
        return;

      case "stimulus":
        if (isMapped) {
          const rt = roundRt(timestamp - (this.onsetClientMs ?? timestamp));
          this.finish({
            key_pressed: code,
            response_position: responsePosition,
            outcome: responsePosition === this.config.stimulusPosition ? "correct" : "incorrect",
            rt_ms: rt,
            response_client_ms: timestamp,
          });
        } else {
          this.extraneousKeys += 1;
        }
        return;

      case "feedback":
        // Trial is wrapping up; further keydowns are not part of this trial.
        return;
    }
  }

  /** FR-45/46: invalidate the in-flight trial (fullscreen exit / focus loss). */
  invalidate(reason: InvalidReason): void {
    if (this.done) return;
    this.finish({
      key_pressed: null,
      response_position: null,
      outcome: "invalid",
      rt_ms: null,
      response_client_ms: null,
      invalid_reason: reason,
    });
  }

  dispose(): void {
    this.clearTimers();
  }

  private emit(feedback: FeedbackKind | null): void {
    this.callbacks.onSnapshot({
      phase: this.phase,
      boxPosition: this.phase === "stimulus" ? this.config.stimulusPosition : null,
      feedback,
    });
  }

  private clearTimers(): void {
    if (this.timeoutHandle !== null) {
      this.clock.clearTimeout(this.timeoutHandle);
      this.timeoutHandle = null;
    }
    if (this.frameHandle !== null) {
      this.clock.cancelFrame(this.frameHandle);
      this.frameHandle = null;
    }
    if (this.feedbackTimeoutHandle !== null) {
      this.clock.clearTimeout(this.feedbackTimeoutHandle);
      this.feedbackTimeoutHandle = null;
    }
  }

  private beginForeperiod(): void {
    this.phase = "foreperiod";
    this.timeoutHandle = null;
    this.emit(null);
    this.armStimulus();
  }

  private armStimulus(): void {
    // §5.6: setTimeout only "arms" the swap; the onset timestamp is the
    // performance.now() captured inside the rAF callback that paints the box.
    this.timeoutHandle = this.clock.setTimeout(() => {
      this.timeoutHandle = null;
      this.frameHandle = this.clock.requestFrame((frameTime) => {
        this.frameHandle = null;
        this.beginStimulus(frameTime);
      });
    }, this.foreperiodMs);
  }

  private beginStimulus(frameTime: number): void {
    this.phase = "stimulus";
    this.onsetClientMs = frameTime;
    this.emit(null);
    this.timeoutHandle = this.clock.setTimeout(() => this.handleTimeout(), this.config.responseTimeoutMs);
  }

  private handleTimeout(): void {
    this.timeoutHandle = null;
    this.finish({
      key_pressed: null,
      response_position: null,
      outcome: "timeout",
      rt_ms: null,
      response_client_ms: null,
    });
  }

  /** FR-29: a mapped keydown during ITI increments premature_count and (in
   * practice) flashes "Too soon!" without otherwise affecting the ITI timer. */
  private flashTooSoonDuring(phase: EnginePhase): void {
    if (this.config.block !== "practice") return;
    this.emit("too_soon");
    this.feedbackTimeoutHandle = this.clock.setTimeout(() => {
      this.feedbackTimeoutHandle = null;
      if (this.phase === phase) this.emit(null);
    }, TOO_SOON_DURATION_MS);
  }

  /** FR-29/D-5: a mapped keydown during the foreperiod redraws it and keeps
   * the same trial running; practice shows "Too soon!" for 1000 ms first. */
  private restartForeperiod(): void {
    this.clearTimers();
    if (this.config.block === "practice") {
      this.emit("too_soon");
      this.feedbackTimeoutHandle = this.clock.setTimeout(() => {
        this.feedbackTimeoutHandle = null;
        this.foreperiodMs = this.config.drawForeperiod();
        this.emit(null);
        this.armStimulus();
      }, TOO_SOON_DURATION_MS);
    } else {
      this.foreperiodMs = this.config.drawForeperiod();
      this.armStimulus();
    }
  }

  private feedbackFor(outcome: Outcome): FeedbackKind | null {
    if (this.config.block !== "practice" || !this.config.practiceFeedback) return null;
    if (outcome === "incorrect") return "incorrect";
    if (outcome === "timeout") return "timeout";
    return null;
  }

  private finish(args: FinishArgs): void {
    this.clearTimers();

    const result: TrialResult = {
      block: this.config.block,
      trial_index: this.config.trialIndex,
      stimulus_position: this.config.stimulusPosition,
      foreperiod_ms: this.foreperiodMs,
      key_pressed: args.key_pressed,
      response_position: args.response_position,
      outcome: args.outcome,
      rt_ms: args.rt_ms,
      premature_count: this.prematureCount,
      extraneous_keys: this.extraneousKeys,
      invalid_reason: args.invalid_reason ?? null,
      stimulus_onset_client_ms: this.onsetClientMs,
      response_client_ms: args.response_client_ms,
    };

    const feedback = this.feedbackFor(result.outcome);
    this.phase = "feedback";
    if (feedback) {
      this.emit(feedback);
      this.feedbackTimeoutHandle = this.clock.setTimeout(() => {
        this.feedbackTimeoutHandle = null;
        this.complete(result);
      }, this.config.feedbackDurationMs);
    } else {
      // Box reverts to a cross immediately; no feedback to display.
      this.emit(null);
      this.complete(result);
    }
  }

  private complete(result: TrialResult): void {
    this.done = true;
    this.callbacks.onComplete(result);
  }
}
