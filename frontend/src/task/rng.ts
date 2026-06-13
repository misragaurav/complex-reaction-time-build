export type RngFn = () => number;

/**
 * Mulberry32 PRNG. With a `seed` it is fully deterministic (D-15 test mode
 * for reproducible automated tests of the trial sequence); without one it
 * falls back to `Math.random`.
 */
export function createRng(seed?: number): RngFn {
  if (seed === undefined) {
    return Math.random;
  }
  let state = seed >>> 0;
  return (): number => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
