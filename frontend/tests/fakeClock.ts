import type { EngineClock } from "../src/task/trialEngine";

/** Simulated frame interval for `requestFrame` callbacks (~60 Hz). */
export const FRAME_MS = 16;

interface ScheduledTask {
  id: number;
  due: number;
  seq: number;
  cb: (time: number) => void;
}

/**
 * Deterministic `EngineClock` for driving the trial state machine in tests:
 * `advance(ms)` executes every timer/frame due within the window in time
 * order, moving `now()` to each task's due time as it fires.
 */
export class FakeClock implements EngineClock {
  private time = 0;
  private nextId = 1;
  private nextSeq = 1;
  private tasks: ScheduledTask[] = [];

  now = (): number => this.time;

  setTimeout = (cb: () => void, ms: number): number => {
    const id = this.nextId++;
    this.tasks.push({ id, due: this.time + ms, seq: this.nextSeq++, cb });
    return id;
  };

  clearTimeout = (handle: number): void => {
    this.tasks = this.tasks.filter((t) => t.id !== handle);
  };

  requestFrame = (cb: (time: number) => void): number => {
    const id = this.nextId++;
    this.tasks.push({ id, due: this.time + FRAME_MS, seq: this.nextSeq++, cb });
    return id;
  };

  cancelFrame = (handle: number): void => {
    this.clearTimeout(handle);
  };

  /** Runs all tasks due within the next `ms` milliseconds, in order. */
  advance(ms: number): void {
    const end = this.time + ms;
    for (;;) {
      const due = this.tasks.filter((t) => t.due <= end);
      if (due.length === 0) break;
      due.sort((a, b) => a.due - b.due || a.seq - b.seq);
      const next = due[0];
      if (!next) break;
      this.tasks = this.tasks.filter((t) => t.id !== next.id);
      this.time = Math.max(this.time, next.due);
      next.cb(this.time);
    }
    this.time = end;
  }
}
