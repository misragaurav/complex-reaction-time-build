# Session Timeline

A chronological walk through everything that happens during one participant
session, from login to the researcher seeing results. References point at
the code that implements each step.

## 1. Before the session starts

| Step | What happens | Code |
|---|---|---|
| Participant logs in (or claims their code) | `POST /auth/participant/check`, `POST /auth/participant/set-password` or `POST /auth/participant/login` | [`backend/app/routers/auth.py`](backend/app/routers/auth.py) |
| `/me` page loads | `GET /me/sessions` lists this participant's sessions in `order_index` order; sessions after an incomplete one are shown locked (D-4) | [`frontend/src/pages/MySessionsPage.tsx`](frontend/src/pages/MySessionsPage.tsx) |
| Participant clicks "Start"/"Resume" on the first unlocked session | Navigates to `/run/:sessionId` | [`frontend/src/pages/TaskRunnerPage.tsx`](frontend/src/pages/TaskRunnerPage.tsx) |

## 2. `/run/:sessionId` boot sequence

This is `useTaskRunner`'s effect chain
([`frontend/src/task/useTaskRunner.ts`](frontend/src/task/useTaskRunner.ts)):

1. **Device gate (FR-44).** `isDeviceBlocked()` checks for a touch-primary
   pointer or a viewport smaller than 1024×600. If blocked, the runner stops
   here — no `/start` call is made, nothing is recorded.
2. **`POST /sessions/{id}/start`.** Server-side
   ([`backend/app/routers/runtime.py:start_session`](backend/app/routers/runtime.py)):
   - Rejects (409) if an earlier session in the participant's order is still
     incomplete, or if this session is already `completed`.
   - If the session was `created`, sets `status = "in_progress"` and
     `started_at = now`.
   - If it was already `in_progress` (refresh) or `abandoned` (FR-21:
     `in_progress` for >30 min with no activity), increments `resume_count`
     and re-marks it `in_progress`.
   - Returns the session's frozen `params` snapshot, `task_type`, `attempt`,
     any due demographic fields, and `stored_trials` (trial indices already
     recorded for `practice`/`test` in the current `attempt`, used for FR-35
     resume).
3. **`recordClientEnv` (FR-43, fire-and-forget).** Measures the display
   refresh rate and posts `user_agent`, screen size, device pixel ratio,
   refresh rate, and timezone via `POST /sessions/{id}/client-env`. Failures
   are swallowed — this is diagnostic only.
4. **Phase becomes `demographics`** if any due fields were returned, else
   `instructions`.

## 3. Demographics (if due)

- Participant answers the due fields; `POST /sessions/{id}/demographics`
  validates each value against its `field_type` (number/boolean/single-choice)
  and that all `required` due fields are answered (422 otherwise).
- `frequency = "once"` answers are stored against the participant with
  `session_id = NULL`; `frequency = "every_session"` answers are stored
  against this session.
- Phase becomes `instructions`.

## 4. Instructions screen

- Shows the task-specific instructions text with `{N}`/`{KEYS}`/`{P}`/`{T}`
  placeholders substituted from `params`
  ([`frontend/src/task/instructions.ts`](frontend/src/task/instructions.ts)).
- Participant clicks "Start practice" → `requestFullscreenIfNeeded()` is
  called and the phase becomes `practice`.

## 5. Practice block (and, identically, the test block)

A `BlockRunner` ([`frontend/src/task/sessionRunner.ts`](frontend/src/task/sessionRunner.ts))
runs `practice_trials` (or `test_trials`) trial slots back-to-back. On
resume, `computeResumeState()` rebuilds the queue from `stored_trials` so
already-recorded trials are skipped (FR-35).

For **each trial**, a `TrialEngine`
([`frontend/src/task/trialEngine.ts`](frontend/src/task/trialEngine.ts)) runs
this state machine:

1. **`iti` (inter-trial interval).** All positions show crosses for
   `iti_ms`. A mapped key here increments `premature_count` and (practice
   only) flashes "Too soon!" for 1000 ms, *without* restarting the ITI timer.
2. **`foreperiod`.** Crosses continue showing for a freshly-drawn duration in
   `[foreperiod_min_ms, foreperiod_max_ms]` (FR-26,
   [`drawForeperiod`](frontend/src/task/sequence.ts)). A mapped key here
   increments `premature_count` and **redraws** the foreperiod (practice:
   shows "Too soon!" for 1000 ms first, then redraws and re-arms).
3. **`stimulus`.** A `setTimeout` for the foreperiod fires, then a
   `requestAnimationFrame` callback paints the box at the drawn
   `stimulus_position` — the timestamp captured *inside that rAF callback* is
   `stimulus_onset_client_ms`. A `response_timeout_ms` timer starts.
   - **Mapped keydown** → trial finishes with `outcome = "correct"` or
     `"incorrect"` (depending on whether the pressed key's position matches
     `stimulus_position`) and `rt_ms` = time since onset.
   - **Unmapped keydown** → increments `extraneous_keys`, trial continues
     waiting.
   - **Timeout** → trial finishes with `outcome = "timeout"`, `rt_ms = null`.
4. **`feedback`** (practice only, only if `practice_feedback = true`, only
   for `incorrect`/`timeout` outcomes). Shows a "✗"/timeout indicator for
   `feedback_duration_ms`, then completes. Every other case (test block
   always; `correct` outcomes; practice without `practice_feedback`)
   completes immediately with no feedback shown.
5. **Trial complete** → `onTrialComplete` fires with the full `TrialResult`,
   which is converted to a `TrialIn` (adding `client_uuid`, `attempt`) and
   pushed onto the `TrialUploadQueue`.

### FR-45/46: fullscreen exit / focus loss mid-trial

If the participant exits fullscreen, or the tab loses focus/visibility while
in the `foreperiod` or `stimulus` phase, the active trial is **invalidated**:
`outcome = "invalid"`, `invalid_reason = "fullscreen_exit" | "focus_loss"`,
`rt_ms = null`. The `BlockRunner` pauses and the UI shows a "Press Continue to
re-enter fullscreen" overlay. Up to 5 such invalidations per block are
**re-queued** as extra trial slots beyond `blockSize` (slots
`blockSize+1 … blockSize+5`); a 6th+ invalidation in the same block is not
re-queued (the block ends one trial short on the server's expected-row check).

### FR-34: trial upload queue

`TrialUploadQueue` ([`frontend/src/task/uploadQueue.ts`](frontend/src/task/uploadQueue.ts))
batches completed trials and `POST`s them to `/sessions/{id}/trials` (batch
size 5, plus a flush at the end of the practice block, on tab-hide/unload via
`fetch(..., {keepalive: true})`, and before `/complete`). Each trial carries a
client-generated `client_uuid`; the server **upserts by `client_uuid`**, so
re-sending a batch after a dropped connection is a no-op.

## 6. Interstitial

- After the practice block completes, the queue is flushed and an
  interstitial screen is shown before the participant proceeds to the test
  block (`startTest()` → `requestFullscreenIfNeeded()` again, phase →
  `test`).

## 7. Test block

- Identical state machine to practice, except: feedback is **never** shown
  (regardless of `practice_feedback`), and "Too soon!" is never shown (it is
  practice-block-gated per Decision #1).
- When the block completes, phase → `completing`.

## 8. Completion

1. `finishSession()` flushes any remaining buffered trials, then calls
   `POST /sessions/{id}/complete`.
2. **Server-side check**
   ([`backend/app/routers/runtime.py:complete_session`](backend/app/routers/runtime.py)):
   counts `invalid` test-block trials (`k`), computes
   `expected_rows = test_trials + min(k, 5)`, and requires that the stored
   `trial_index` values for `block="test", attempt=session.attempt` are
   exactly `1..expected_rows`. If any are missing, returns 409 with the list
   of missing indices (the client can resume and fill them in).
3. On success: `status = "completed"`, `completed_at = now`, returns 204.
4. Phase → `completed`; the participant sees a "Session complete" screen.
   Participants never see their own results (D-12).

## 9. Researcher side, after the session

- **`GET /sessions/{id}/summary`** recomputes FR-47 statistics from the
  test-block trials of the session's *current attempt*: `n_trials`,
  `n_correct`, `accuracy_pct`, `n_timeouts`, `n_premature` (sum of
  `premature_count` across test trials), `n_invalid`,
  `n_outliers_flagged`, and raw/trimmed RT stats (mean, median, SD, CoV,
  IIV-within).
  ([`backend/app/services/statistics.py`](backend/app/services/statistics.py))
- **Dashboard tab** (`/studies/:id?tab=dashboard`) shows the sessions table
  and five charts built from these per-session summaries
  ([`frontend/src/pages/StudyDashboardTab.tsx`](frontend/src/pages/StudyDashboardTab.tsx)).
- **Exports** (`/sessions/{id}/export.csv`,
  `/participants/{id}/export.csv`, `/studies/{id}/export.zip`) emit one row
  per stored trial in `TRIAL_COLUMNS` order
  ([`backend/app/services/exports.py`](backend/app/services/exports.py)).

## 10. Reset / re-attempt (researcher-initiated)

- A researcher can **reset** a session from the Sessions tab
  (`POST /sessions/{id}/reset`): `attempt` is incremented, `status` returns
  to `created`, and all prior trials are **kept** (tagged with the old
  `attempt` number) — the next `/start` begins a fresh `attempt` with an
  empty `stored_trials` for that attempt.
