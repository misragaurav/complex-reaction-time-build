import { describe, expect, it } from "vitest";
import type { TaskParams } from "../src/api/types";
import { renderInstructions } from "../src/task/instructions";

const PARAMS: TaskParams = {
  task_type: "CRT4",
  practice_trials: 3,
  test_trials: 20,
  foreperiod_min_ms: 1000,
  foreperiod_max_ms: 3000,
  response_timeout_ms: 3000,
  iti_ms: 500,
  key_map: ["KeyZ", "KeyX", "KeyN", "KeyM"],
  practice_feedback: true,
  feedback_duration_ms: 500,
  max_consecutive_repeats: 3,
  outlier_low_ms: 150,
  outlier_high_ms: 1500,
  show_progress: true,
  instructions_text: "",
};

describe("renderInstructions (§5.3)", () => {
  it("substitutes {N}, {KEYS}, {P}, {T}", () => {
    const text = renderInstructions("See {N} crosses. Keys: {KEYS}. {P} practice, {T} test.", PARAMS);
    expect(text).toBe("See 4 crosses. Keys: Z X N M. 3 practice, 20 test.");
  });

  it("renders arrow-key labels for CRT2 defaults", () => {
    const params: TaskParams = { ...PARAMS, task_type: "CRT2", key_map: ["ArrowLeft", "ArrowRight"] };
    expect(renderInstructions("{N}: {KEYS}", params)).toBe("2: ← →");
  });

  it("replaces repeated placeholders everywhere", () => {
    expect(renderInstructions("{P}{P}{T}", PARAMS)).toBe("3320");
  });
});
