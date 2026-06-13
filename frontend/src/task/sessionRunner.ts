import type { Block, InvalidReason, TaskParams } from "../api/types";
import type { RngFn } from "./rng";
import { drawForeperiod, drawPosition } from "./sequence";
import { EngineClock, EngineSnapshot, TrialConfig, TrialEngine, TrialResult } from "./trialEngine";

/** FR-45/46: at most this many invalidated trials are re-queued per block. */
export const MAX_REQUEUES_PER_BLOCK = 5;

export interface BlockProgress {
  /** Trials finished so far (including invalid ones), 0-based count. */
  completedSlots: number;
  /** `blockSize + min(invalidationCount, 5)` (FR-45). */
  totalSlots: number;
}

export interface BlockRunnerCallbacks {
  onSnapshot: (snapshot: EngineSnapshot) => void;
  onTrialComplete: (result: TrialResult, progress: BlockProgress) => void;
  onBlockComplete: () => void;
}

export interface BlockRunnerOptions {
  block: Block;
  /** `practice_trials` or `test_trials` from the session's parameter snapshot. */
  blockSize: number;
  params: TaskParams;
  rng: RngFn;
  clock: EngineClock;
  /** Trial indices still to run, e.g. `[1..blockSize]` minus already-stored
   * trials on resume (FR-35). Defaults to the full block. */
  initialQueue?: number[];
  /** Re-queue slots already consumed before this runner started (resume). */
  initialInvalidationCount?: number;
}

/**
 * Runs the trials of one block (practice or test) back to back, handling
 * FR-25 position sequencing, FR-45/46 invalidation re-queueing, and progress
 * reporting for the UI.
 */
export class BlockRunner {
  private queue: number[];
  private invalidationCount: number;
  private totalSlots: number;
  private completedSlots: number;
  private positionHistory: number[] = [];
  private currentEngine: TrialEngine | null = null;
  private paused = false;

  constructor(
    private readonly options: BlockRunnerOptions,
    private readonly callbacks: BlockRunnerCallbacks,
  ) {
    this.queue = options.initialQueue ?? Array.from({ length: options.blockSize }, (_, i) => i + 1);
    this.invalidationCount = options.initialInvalidationCount ?? 0;
    this.totalSlots = options.blockSize + Math.min(this.invalidationCount, MAX_REQUEUES_PER_BLOCK);
    this.completedSlots = Math.max(0, this.totalSlots - this.queue.length);
  }

  start(): void {
    if (this.options.blockSize === 0) {
      this.callbacks.onBlockComplete();
      return;
    }
    this.runNext();
  }

  handleKeydown(code: string, timestamp: number, repeat: boolean): void {
    this.currentEngine?.handleKeydown(code, timestamp, repeat);
  }

  /** FR-45/46: invalidate the in-flight trial. The caller shows a "Press
   * Continue" overlay and calls `resume()` once ready. */
  invalidate(reason: InvalidReason): void {
    if (!this.currentEngine) return;
    this.paused = true;
    this.currentEngine.invalidate(reason);
  }

  resume(): void {
    if (!this.paused) return;
    this.paused = false;
    this.runNext();
  }

  dispose(): void {
    this.currentEngine?.dispose();
    this.currentEngine = null;
  }

  private runNext(): void {
    const trialIndex = this.queue.shift();
    if (trialIndex === undefined) {
      this.callbacks.onBlockComplete();
      return;
    }

    const { params, rng } = this.options;
    const nPositions = params.key_map.length;
    const stimulusPosition = drawPosition(rng, nPositions, this.positionHistory, params.max_consecutive_repeats);
    this.positionHistory.push(stimulusPosition);

    const config: TrialConfig = {
      block: this.options.block,
      trialIndex,
      stimulusPosition,
      itiMs: params.iti_ms,
      responseTimeoutMs: params.response_timeout_ms,
      feedbackDurationMs: params.feedback_duration_ms,
      practiceFeedback: params.practice_feedback,
      keyMap: params.key_map,
      drawForeperiod: () => drawForeperiod(rng, params.foreperiod_min_ms, params.foreperiod_max_ms),
    };

    this.currentEngine = new TrialEngine(config, this.options.clock, {
      onSnapshot: (snapshot) => this.callbacks.onSnapshot(snapshot),
      onComplete: (result) => this.handleTrialComplete(result),
    });
    this.currentEngine.start();
  }

  private handleTrialComplete(result: TrialResult): void {
    this.currentEngine = null;
    this.completedSlots += 1;

    if (result.outcome === "invalid" && this.invalidationCount < MAX_REQUEUES_PER_BLOCK) {
      this.invalidationCount += 1;
      this.queue.push(this.options.blockSize + this.invalidationCount);
      this.totalSlots = this.options.blockSize + Math.min(this.invalidationCount, MAX_REQUEUES_PER_BLOCK);
    }

    this.callbacks.onTrialComplete(result, { completedSlots: this.completedSlots, totalSlots: this.totalSlots });

    if (this.paused) return;
    this.runNext();
  }
}

export interface ResumeState {
  /** Trial indices not yet present in `storedIndices`, in ascending order. */
  queue: number[];
  /** FR-45 re-queue slots implied by stored indices beyond `blockSize`. */
  invalidationCount: number;
}

/**
 * FR-35: given the trial indices already stored for a block (from
 * `GET /sessions/{id}/start`'s `stored_trials`), computes the remaining queue
 * and how many FR-45 re-queue slots have already been used.
 */
export function computeResumeState(blockSize: number, storedIndices: readonly number[]): ResumeState {
  const stored = new Set(storedIndices);
  const maxStored = storedIndices.reduce((max, i) => Math.max(max, i), 0);
  const invalidationCount = Math.min(MAX_REQUEUES_PER_BLOCK, Math.max(0, maxStored - blockSize));
  const totalSlots = blockSize + invalidationCount;

  const queue: number[] = [];
  for (let i = 1; i <= totalSlots; i += 1) {
    if (!stored.has(i)) queue.push(i);
  }
  return { queue, invalidationCount };
}
