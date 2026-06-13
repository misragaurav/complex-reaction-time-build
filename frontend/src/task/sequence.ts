import type { RngFn } from "./rng";

/**
 * Draws a stimulus position uniformly at random from `[0, nPositions)`,
 * subject to FR-25: a position may not appear more than `maxConsecutiveRepeats`
 * times in a row. `history` is the sequence of previously drawn positions for
 * the current block, oldest first.
 */
export function drawPosition(
  rng: RngFn,
  nPositions: number,
  history: readonly number[],
  maxConsecutiveRepeats: number,
): number {
  let forbidden: number | null = null;
  if (maxConsecutiveRepeats > 0 && history.length >= maxConsecutiveRepeats) {
    const tail = history.slice(history.length - maxConsecutiveRepeats);
    const first = tail[0];
    if (first !== undefined && tail.every((p) => p === first)) {
      forbidden = first;
    }
  }

  const candidates: number[] = [];
  for (let i = 0; i < nPositions; i += 1) {
    if (i !== forbidden) candidates.push(i);
  }
  const pool = candidates.length > 0 ? candidates : Array.from({ length: nPositions }, (_, i) => i);
  const index = Math.min(Math.floor(rng() * pool.length), pool.length - 1);
  return pool[index] ?? 0;
}

/** Uniform random integer in `[minMs, maxMs]` inclusive (FR-26). */
export function drawForeperiod(rng: RngFn, minMs: number, maxMs: number): number {
  const span = maxMs - minMs + 1;
  const offset = Math.min(Math.floor(rng() * span), span - 1);
  return minMs + offset;
}
