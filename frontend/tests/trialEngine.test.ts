import { describe, expect, it } from "vitest";
import type { Block } from "../src/api/types";
import {
  TrialEngine,
  type EngineSnapshot,
  type TrialConfig,
  type TrialResult,
} from "../src/task/trialEngine";
import { FakeClock, FRAME_MS } from "./fakeClock";

const KEY_MAP = ["KeyZ", "KeyX", "KeyN", "KeyM"];
const ITI_MS = 500;
const FOREPERIOD_MS = 1000;
const RESPONSE_TIMEOUT_MS = 3000;
const FEEDBACK_DURATION_MS = 500;

interface Harness {
  clock: FakeClock;
  engine: TrialEngine;
  snapshots: EngineSnapshot[];
  results: TrialResult[];
  /** Advances past ITI + foreperiod + the stimulus paint frame. */
  advanceToStimulus: () => void;
  onsetMs: () => number;
}

function makeHarness(overrides: Partial<TrialConfig> = {}): Harness {
  const clock = new FakeClock();
  const snapshots: EngineSnapshot[] = [];
  const results: TrialResult[] = [];
  const config: TrialConfig = {
    block: "practice" as Block,
    trialIndex: 1,
    stimulusPosition: 2,
    itiMs: ITI_MS,
    responseTimeoutMs: RESPONSE_TIMEOUT_MS,
    feedbackDurationMs: FEEDBACK_DURATION_MS,
    practiceFeedback: true,
    keyMap: KEY_MAP,
    drawForeperiod: () => FOREPERIOD_MS,
    ...overrides,
  };
  const engine = new TrialEngine(config, clock, {
    onSnapshot: (s) => snapshots.push(s),
    onComplete: (r) => results.push(r),
  });
  engine.start();
  return {
    clock,
    engine,
    snapshots,
    results,
    advanceToStimulus: () => clock.advance(ITI_MS + FOREPERIOD_MS + FRAME_MS),
    onsetMs: () => ITI_MS + FOREPERIOD_MS + FRAME_MS,
  };
}

describe("TrialEngine", () => {
  it("stores rt_ms = 234.5 for a keydown 234.5 ms after stimulus onset (AC-26)", () => {
    const h = makeHarness();
    h.advanceToStimulus();
    expect(h.snapshots.at(-1)?.phase).toBe("stimulus");
    expect(h.snapshots.at(-1)?.boxPosition).toBe(2);

    h.engine.handleKeydown("KeyN", h.onsetMs() + 234.5, false);
    const result = h.results[0];
    expect(result?.outcome).toBe("correct");
    expect(result?.rt_ms).toBe(234.5);
    expect(result?.stimulus_onset_client_ms).toBe(h.onsetMs());
  });

  it("ignores auto-repeat keydowns (AC-27)", () => {
    const h = makeHarness();
    h.advanceToStimulus();
    h.engine.handleKeydown("KeyN", h.onsetMs() + 100, true);
    expect(h.results).toHaveLength(0);
    h.engine.handleKeydown("KeyN", h.onsetMs() + 200, false);
    expect(h.results).toHaveLength(1);
  });

  it("marks a wrong mapped key incorrect with RT recorded (AC-40)", () => {
    const h = makeHarness();
    h.advanceToStimulus();
    h.engine.handleKeydown("KeyZ", h.onsetMs() + 300, false);
    h.clock.advance(FEEDBACK_DURATION_MS); // practice shows the red x first
    const result = h.results[0];
    expect(result?.outcome).toBe("incorrect");
    expect(result?.response_position).toBe(0);
    expect(result?.rt_ms).toBe(300);
  });

  it("premature keydown during foreperiod increments premature_count, redraws the foreperiod, and shows 'Too soon!' in practice (AC-28)", () => {
    const draws: number[] = [];
    const h = makeHarness({
      drawForeperiod: () => {
        draws.push(FOREPERIOD_MS);
        return FOREPERIOD_MS;
      },
    });
    expect(draws).toHaveLength(1);

    h.clock.advance(ITI_MS + 100); // into the foreperiod
    h.engine.handleKeydown("KeyZ", ITI_MS + 100, false);
    expect(h.snapshots.at(-1)?.feedback).toBe("too_soon");

    // "Too soon!" displays for 1000 ms, then a fresh foreperiod is drawn.
    h.clock.advance(1000);
    expect(draws).toHaveLength(2);
    expect(h.snapshots.at(-1)?.feedback).toBeNull();

    // The same trial then continues to stimulus and completes normally.
    h.clock.advance(FOREPERIOD_MS + FRAME_MS);
    const onset = ITI_MS + 100 + 1000 + FOREPERIOD_MS + FRAME_MS;
    h.engine.handleKeydown("KeyN", onset + 250, false);
    const result = h.results[0];
    expect(result?.outcome).toBe("correct");
    expect(result?.premature_count).toBe(1);
  });

  it("does not show 'Too soon!' for premature responses in the test block", () => {
    const h = makeHarness({ block: "test" });
    h.clock.advance(ITI_MS + 100);
    h.engine.handleKeydown("KeyZ", ITI_MS + 100, false);
    expect(h.snapshots.some((s) => s.feedback === "too_soon")).toBe(false);
    // Foreperiod restarts immediately (no 1000 ms pause).
    h.clock.advance(FOREPERIOD_MS + FRAME_MS);
    expect(h.snapshots.at(-1)?.phase).toBe("stimulus");
  });

  it("counts unmapped keys as extraneous only (AC-29)", () => {
    const h = makeHarness();
    h.advanceToStimulus();
    h.engine.handleKeydown("KeyQ", h.onsetMs() + 50, false);
    expect(h.results).toHaveLength(0);
    h.engine.handleKeydown("KeyN", h.onsetMs() + 400, false);
    const result = h.results[0];
    expect(result?.outcome).toBe("correct");
    expect(result?.extraneous_keys).toBe(1);
    expect(result?.premature_count).toBe(0);
  });

  it("yields outcome timeout with null RT when no key arrives within response_timeout_ms (AC-30)", () => {
    const h = makeHarness({ block: "test", practiceFeedback: false });
    h.advanceToStimulus();
    h.clock.advance(RESPONSE_TIMEOUT_MS);
    const result = h.results[0];
    expect(result?.outcome).toBe("timeout");
    expect(result?.rt_ms).toBeNull();
    expect(result?.key_pressed).toBeNull();
  });

  it("shows red feedback on practice errors only when practice_feedback is true (AC-31)", () => {
    const withFeedback = makeHarness({ practiceFeedback: true });
    withFeedback.advanceToStimulus();
    withFeedback.engine.handleKeydown("KeyZ", withFeedback.onsetMs() + 300, false);
    expect(withFeedback.snapshots.at(-1)?.feedback).toBe("incorrect");
    expect(withFeedback.results).toHaveLength(0); // feedback still displaying
    withFeedback.clock.advance(FEEDBACK_DURATION_MS);
    expect(withFeedback.results).toHaveLength(1);

    const withoutFeedback = makeHarness({ practiceFeedback: false });
    withoutFeedback.advanceToStimulus();
    withoutFeedback.engine.handleKeydown("KeyZ", withoutFeedback.onsetMs() + 300, false);
    expect(withoutFeedback.snapshots.some((s) => s.feedback === "incorrect")).toBe(false);
    expect(withoutFeedback.results).toHaveLength(1);
  });

  it("never shows feedback in the test block (AC-32)", () => {
    const h = makeHarness({ block: "test", practiceFeedback: true });
    h.advanceToStimulus();
    h.engine.handleKeydown("KeyZ", h.onsetMs() + 300, false); // incorrect
    expect(h.snapshots.every((s) => s.feedback === null)).toBe(true);
    expect(h.results).toHaveLength(1);

    const timeoutCase = makeHarness({ block: "test", practiceFeedback: true });
    timeoutCase.advanceToStimulus();
    timeoutCase.clock.advance(RESPONSE_TIMEOUT_MS);
    expect(timeoutCase.snapshots.every((s) => s.feedback === null)).toBe(true);
  });

  it("invalidate() finishes the trial as invalid with the given reason (FR-45/46)", () => {
    const h = makeHarness({ block: "test", practiceFeedback: false });
    h.advanceToStimulus();
    h.engine.invalidate("fullscreen_exit");
    const result = h.results[0];
    expect(result?.outcome).toBe("invalid");
    expect(result?.invalid_reason).toBe("fullscreen_exit");
    expect(result?.rt_ms).toBeNull();
  });

  it("counts a mapped keydown during the ITI as premature without restarting the ITI (FR-29)", () => {
    const h = makeHarness();
    h.clock.advance(100); // inside ITI
    h.engine.handleKeydown("KeyZ", 100, false);
    expect(h.snapshots.at(-1)?.feedback).toBe("too_soon");

    // The ITI timer was not restarted: foreperiod begins at the original time.
    h.clock.advance(ITI_MS - 100);
    expect(h.snapshots.at(-1)?.phase).toBe("foreperiod");

    h.clock.advance(FOREPERIOD_MS + FRAME_MS);
    h.engine.handleKeydown("KeyN", h.clock.now(), false);
    expect(h.results[0]?.premature_count).toBe(1);
  });
});
