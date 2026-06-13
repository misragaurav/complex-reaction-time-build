import { describe, expect, it } from "vitest";
import type { TaskParams } from "../src/api/types";
import { createRng } from "../src/task/rng";
import { BlockRunner, computeResumeState, type BlockProgress } from "../src/task/sessionRunner";
import type { TrialResult } from "../src/task/trialEngine";
import { FakeClock, FRAME_MS } from "./fakeClock";

const PARAMS: TaskParams = {
  task_type: "CRT4",
  practice_trials: 3,
  test_trials: 5,
  foreperiod_min_ms: 1000,
  foreperiod_max_ms: 1000, // fixed so timing is deterministic
  response_timeout_ms: 3000,
  iti_ms: 500,
  key_map: ["KeyZ", "KeyX", "KeyN", "KeyM"],
  practice_feedback: false,
  feedback_duration_ms: 500,
  max_consecutive_repeats: 3,
  outlier_low_ms: 150,
  outlier_high_ms: 1500,
  show_progress: true,
  instructions_text: "",
};

/** Worst-case wall time of one timed-out trial with PARAMS. */
const TRIAL_MS = PARAMS.iti_ms + PARAMS.foreperiod_min_ms + FRAME_MS + PARAMS.response_timeout_ms;

interface Harness {
  clock: FakeClock;
  runner: BlockRunner;
  results: TrialResult[];
  progress: BlockProgress[];
  completed: () => boolean;
}

function makeHarness(block: "practice" | "test", initialQueue?: number[], initialInvalidationCount?: number): Harness {
  const clock = new FakeClock();
  const results: TrialResult[] = [];
  const progress: BlockProgress[] = [];
  let done = false;
  const runner = new BlockRunner(
    {
      block,
      blockSize: block === "practice" ? PARAMS.practice_trials : PARAMS.test_trials,
      params: PARAMS,
      rng: createRng(1),
      clock,
      initialQueue,
      initialInvalidationCount,
    },
    {
      onSnapshot: () => {},
      onTrialComplete: (r, p) => {
        results.push(r);
        progress.push(p);
      },
      onBlockComplete: () => {
        done = true;
      },
    },
  );
  return { clock, runner, results, progress, completed: () => done };
}

describe("BlockRunner", () => {
  it("runs exactly blockSize trials and completes (timeout path)", () => {
    const h = makeHarness("test");
    h.runner.start();
    h.clock.advance(TRIAL_MS * PARAMS.test_trials + 100);
    expect(h.results).toHaveLength(5);
    expect(h.results.map((r) => r.trial_index)).toEqual([1, 2, 3, 4, 5]);
    expect(h.results.every((r) => r.outcome === "timeout")).toBe(true);
    expect(h.completed()).toBe(true);
    expect(h.progress.at(-1)).toEqual({ completedSlots: 5, totalSlots: 5 });
  });

  it("re-queues an invalidated trial with the next index and pauses until resume (FR-45, AC-45)", () => {
    const h = makeHarness("test");
    h.runner.start();
    h.clock.advance(PARAMS.iti_ms + 100); // trial 1 in its foreperiod
    h.runner.invalidate("fullscreen_exit");

    expect(h.results).toHaveLength(1);
    expect(h.results[0]?.outcome).toBe("invalid");
    expect(h.results[0]?.invalid_reason).toBe("fullscreen_exit");
    expect(h.progress[0]).toEqual({ completedSlots: 1, totalSlots: 6 });

    // Paused: nothing advances until resume() is called.
    h.clock.advance(TRIAL_MS * 10);
    expect(h.results).toHaveLength(1);

    h.runner.resume();
    h.clock.advance(TRIAL_MS * 6);
    expect(h.completed()).toBe(true);
    // 1 invalid + 5 timeouts; the re-queued slot carries index 6.
    expect(h.results.map((r) => r.trial_index)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("stops re-queueing after 5 invalidations in a block (FR-45, AC-46)", () => {
    const h = makeHarness("practice"); // blockSize 3
    h.runner.start();

    for (let i = 0; i < 8; i += 1) {
      h.clock.advance(PARAMS.iti_ms + 50);
      h.runner.invalidate("focus_loss");
      h.runner.resume();
    }

    // 3 original + 5 re-queues = 8 slots; the 6th+ invalidations add nothing.
    expect(h.results).toHaveLength(8);
    expect(h.results.map((r) => r.trial_index)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(h.completed()).toBe(true);
    expect(h.progress.at(-1)).toEqual({ completedSlots: 8, totalSlots: 8 });
  });

  it("completes immediately when blockSize is 0", () => {
    const clock = new FakeClock();
    let done = false;
    const runner = new BlockRunner(
      { block: "practice", blockSize: 0, params: PARAMS, rng: createRng(1), clock },
      { onSnapshot: () => {}, onTrialComplete: () => {}, onBlockComplete: () => (done = true) },
    );
    runner.start();
    expect(done).toBe(true);
  });
});

describe("computeResumeState (FR-35, AC-35)", () => {
  it("resumes at the first missing trial index", () => {
    expect(computeResumeState(5, [1, 2, 4])).toEqual({ queue: [3, 5], invalidationCount: 0 });
  });

  it("returns the full queue for a fresh block", () => {
    expect(computeResumeState(3, [])).toEqual({ queue: [1, 2, 3], invalidationCount: 0 });
  });

  it("accounts for re-queue slots already consumed", () => {
    // Stored index 7 on a 5-trial block implies 2 invalidation re-queues.
    expect(computeResumeState(5, [1, 2, 3, 4, 5, 6, 7])).toEqual({ queue: [], invalidationCount: 2 });
    expect(computeResumeState(5, [1, 2, 3, 5, 6])).toEqual({ queue: [4], invalidationCount: 1 });
  });

  it("caps implied invalidations at 5", () => {
    expect(computeResumeState(5, [15])).toEqual({
      queue: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
      invalidationCount: 5,
    });
  });
});
