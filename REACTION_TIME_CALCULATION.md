# Reaction Time Calculation, and the `premature_count` Column

## How `rt_ms` is calculated

All timing happens in [`frontend/src/task/trialEngine.ts`](frontend/src/task/trialEngine.ts).

1. **Stimulus onset.** When the foreperiod timer fires, the engine schedules
   a `requestAnimationFrame` callback. The browser passes that callback a
   high-resolution timestamp (`performance.now()`-based) for the frame in
   which the stimulus box is actually painted. This timestamp is stored as
   `onsetClientMs` (`stimulus_onset_client_ms` in the trial row):

   ```ts
   private armStimulus(): void {
     this.timeoutHandle = this.clock.setTimeout(() => {
       this.frameHandle = this.clock.requestFrame((frameTime) => {
         this.beginStimulus(frameTime);
       });
     }, this.foreperiodMs);
   }

   private beginStimulus(frameTime: number): void {
     this.phase = "stimulus";
     this.onsetClientMs = frameTime;   // <- RT zero-point
     ...
   }
   ```

2. **Response.** When a *mapped* key is pressed while `phase === "stimulus"`,
   the engine takes the `KeyboardEvent.timeStamp` of that keydown
   (`response_client_ms`) and computes:

   ```ts
   case "stimulus":
     if (isMapped) {
       const rt = roundRt(timestamp - (this.onsetClientMs ?? timestamp));
       this.finish({ ..., rt_ms: rt, response_client_ms: timestamp });
     }
   ```

3. **Rounding (FR-27).** `roundRt` rounds to one decimal place and clamps any
   tiny negative value up to zero:

   ```ts
   function roundRt(ms: number): number {
     return Math.round(Math.max(0, ms) * 10) / 10;
   }
   ```

4. **Server-side storage.** The server does **not** recompute `rt_ms` from
   the two client timestamps — it trusts the client's `rt_ms` for
   `correct`/`incorrect` outcomes (rounding it to 1 dp again as a `Decimal`),
   but it *does* recompute `outcome`, `response_position`, and `outlier_flag`
   from `key_pressed` vs. `key_map`/`stimulus_position`
   ([`backend/app/routers/runtime.py:_upsert_trial`](backend/app/routers/runtime.py)):

   ```python
   if outcome == "correct" and trial_in.rt_ms is not None:
       outlier_flag = trial_in.rt_ms < outlier_low or trial_in.rt_ms > outlier_high
   else:
       outlier_flag = False

   rt_ms = _to_decimal(trial_in.rt_ms) if outcome in ("correct", "incorrect") else None
   ```

   So `rt_ms` is stored only for `correct`/`incorrect` outcomes; it is
   `null`/empty for `timeout` and `invalid` rows.

## Can `rt_ms` be negative?

**No — by construction it cannot be negative, and it cannot be recorded for
a key pressed before the stimulus appears at all.**

Two separate guards make this true:

- **A keydown can only produce an `rt_ms` value while `phase === "stimulus"`.**
  Any mapped keydown during `iti` or `foreperiod` (i.e. *before* the stimulus
  is shown) is handled in a completely different branch — it does **not**
  finish the trial or produce an `rt_ms`. Instead it:
  - increments `premature_count` (see below), and
  - in the `foreperiod` case, **redraws the foreperiod and restarts the wait**
    — so the trial that eventually does produce an `rt_ms` is timed from a
    *new* stimulus onset, not the moment of the premature key press.

  In other words, "pressing too soon" never reaches the RT-computing code
  path at all; it is captured separately as a premature response.

- **`roundRt()` clamps to zero.** Even within the `stimulus` phase, RT is
  `timestamp - onsetClientMs`, and `onsetClientMs` is set the instant the
  stimulus is painted and *before* the engine starts listening for a
  qualifying response in that phase — so a sub-zero value should not occur in
  practice. `Math.max(0, ms)` is a defensive floor in case of any
  floating-point/timing edge case (e.g. the keydown event's timestamp being
  marginally earlier than the rAF timestamp due to clock-source differences),
  ensuring the stored value is never negative.

So the answer to "should RT be negative if the participant presses too
soon / before the stimulus appears" is: **it is never negative, because a
too-soon press is never timed as an RT in the first place** — it's recorded
via `premature_count` on whichever trial eventually completes, with that
trial's RT (if any) measured from its own (possibly redrawn) stimulus onset.

## What is `premature_count`?

`premature_count` is a **per-trial counter of how many times the participant
pressed a *mapped* key before the stimulus for that trial appeared** — i.e.
during the `iti` or `foreperiod` phases.

From `trialEngine.ts`:

```ts
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
```

Key points:

- **Only mapped keys count.** A press of a key that isn't in `key_map` during
  `iti`/`foreperiod` increments `extraneous_keys` instead, not
  `premature_count`.
- **It can be greater than 1.** Each premature mapped keypress both
  increments the counter *and* (during `foreperiod`) redraws/restarts the
  foreperiod — so a participant who keeps pressing early keeps incrementing
  `premature_count` on the same trial slot, with the foreperiod redrawn each
  time, until they finally wait for the stimulus.
- **It resets to zero per trial.** Each `TrialEngine` instance starts with
  `prematureCount = 0`; the final value is written into that trial's
  `premature_count` column when the trial completes.
- **"Too soon!" feedback (FR-29) is separate from the counter.** The 1-second
  "Too soon!" message is shown only in **practice** blocks (regardless of the
  `practice_feedback` flag — see `DECISIONS_TAKEN.md` #1), but
  `premature_count` is incremented in **both** practice and test blocks
  whenever a premature mapped key is pressed.
- **Aggregated for reporting.** The session summary's `n_premature`
  (FR-47) is the **sum of `premature_count` across all test-block trials**
  of the session's current attempt:

  ```python
  n_premature = sum(t.premature_count for t in test_trials)
  ```

- **Stored verbatim, not recomputed server-side.** Unlike `outcome`,
  `response_position`, and `outlier_flag`, the server trusts the client's
  `premature_count` and `extraneous_keys` values as-is
  (`existing.premature_count = trial_in.premature_count`).

## Worked example

Suppose `foreperiod_min_ms = 1000`, `foreperiod_max_ms = 3000`, and during
trial 5 (test block) the participant:

1. Presses a mapped key 400 ms into the foreperiod → `premature_count = 1`,
   foreperiod is redrawn (say, newly drawn as 2200 ms) and restarted.
2. Waits, then presses the *correct* mapped key 318.4 ms after the stimulus
   (from the second foreperiod) appears.

The resulting row for trial 5 is:

| column | value |
|---|---|
| `foreperiod_ms` | 2200 (the *final*, used foreperiod) |
| `outcome` | `correct` |
| `rt_ms` | `318.4` |
| `premature_count` | `1` |
| `extraneous_keys` | `0` |

The early 400 ms press is never timed — it only shows up as
`premature_count = 1`.
