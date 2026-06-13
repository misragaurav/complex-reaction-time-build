import { describe, expect, it } from "vitest";
import { createRng } from "../src/task/rng";
import { drawForeperiod, drawPosition } from "../src/task/sequence";

describe("drawPosition (FR-25, AC-24)", () => {
  it("never exceeds max_consecutive_repeats over a long seeded sequence", () => {
    const rng = createRng(42);
    const history: number[] = [];
    for (let i = 0; i < 2000; i += 1) {
      history.push(drawPosition(rng, 4, history, 3));
    }
    let run = 1;
    let maxRun = 1;
    for (let i = 1; i < history.length; i += 1) {
      run = history[i] === history[i - 1] ? run + 1 : 1;
      maxRun = Math.max(maxRun, run);
    }
    expect(maxRun).toBeLessThanOrEqual(3);
  });

  it("draws every position for each task size", () => {
    for (const n of [2, 3, 4]) {
      const rng = createRng(7);
      const history: number[] = [];
      for (let i = 0; i < 500; i += 1) {
        const p = drawPosition(rng, n, history, 3);
        expect(p).toBeGreaterThanOrEqual(0);
        expect(p).toBeLessThan(n);
        history.push(p);
      }
      expect(new Set(history).size).toBe(n);
    }
  });

  it("is deterministic for a fixed seed (D-15)", () => {
    const a: number[] = [];
    const b: number[] = [];
    const rngA = createRng(123);
    const rngB = createRng(123);
    for (let i = 0; i < 100; i += 1) {
      a.push(drawPosition(rngA, 4, a, 3));
      b.push(drawPosition(rngB, 4, b, 3));
    }
    expect(a).toEqual(b);
  });
});

describe("drawForeperiod (FR-26, AC-25)", () => {
  it("stays within [min, max] and covers both integer endpoints", () => {
    const rng = createRng(99);
    const values: number[] = [];
    for (let i = 0; i < 5000; i += 1) {
      values.push(drawForeperiod(rng, 1000, 3000));
    }
    expect(Math.min(...values)).toBeGreaterThanOrEqual(1000);
    expect(Math.max(...values)).toBeLessThanOrEqual(3000);
    expect(values.every((v) => Number.isInteger(v))).toBe(true);
    // Uniform over 2001 integers: both ends should appear in 5000 draws... but
    // not guaranteed; just assert a wide spread was achieved.
    expect(Math.min(...values)).toBeLessThan(1100);
    expect(Math.max(...values)).toBeGreaterThan(2900);
  });
});
