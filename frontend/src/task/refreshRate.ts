import type { EngineClock } from "./trialEngine";

const SAMPLE_FRAMES = 60;

/** FR-43: estimate the display refresh rate (Hz) by timing 60 rAF frames. */
export function measureRefreshRate(clock: Pick<EngineClock, "requestFrame">): Promise<number> {
  return new Promise((resolve) => {
    let frameCount = 0;
    let firstTimestamp: number | null = null;

    const step = (time: number): void => {
      if (firstTimestamp === null) {
        firstTimestamp = time;
      }
      frameCount += 1;
      if (frameCount < SAMPLE_FRAMES) {
        clock.requestFrame(step);
        return;
      }
      const elapsedMs = time - firstTimestamp;
      const fps = elapsedMs > 0 ? (1000 * (frameCount - 1)) / elapsedMs : 60;
      resolve(Math.round(fps * 10) / 10);
    };

    clock.requestFrame(step);
  });
}
