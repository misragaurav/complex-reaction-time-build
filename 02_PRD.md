# Product Requirements Document — Choice Reaction Time (CRT) Web Application

**Version:** 1.0 | **Date:** 2026-06-10 | **Status:** Final — ready for implementation
**Build target:** This document is the sole input to an LLM coding agent (Claude Sonnet 4.6 in Claude Code). Every requirement is numbered. Nothing in this document is optional unless marked "Future work." Where the agent must choose between equally valid implementations, Appendix A (Decisions & Defaults) governs.

---

## 1. Overview & Goals

### 1.1 Purpose

A self-hostable web application for a university lab that measures **choice reaction time (CRT)** in human participants, modeled on the Deary-Liewald paradigm. Researchers create studies, issue participant IDs, assign sessions running one of three tasks (2-, 3-, or 4-choice RT), monitor progress, and export trial-level data. Participants log in with a researcher-issued ID, run the task in a desktop browser with a physical keyboard, and their per-trial responses are captured with millisecond-resolution timing.

### 1.2 Goals

- G-1: Administer 2-CRT, 3-CRT, and 4-CRT tasks with researcher-configurable parameters (Deary-Liewald defaults pre-filled).
- G-2: Support repeated measures: each participant ID can have multiple sessions, enabling intra-individual variability (IIV) analysis across trials and across sessions.
- G-3: Capture per-trial data with documented browser-timing precision; never silently discard data.
- G-4: Provide a researcher dashboard with summary statistics, visualizations, and one-click CSV export of every data view. Also, a one-click export of all data for a participant. Also, a one-click export of all data for all participants.
- G-5: Zero-rework deployment path: identical Docker artifact runs on a laptop, behind a Tailscale/ngrok tunnel for lab testing, and on a public host (Railway/Render/Fly.io/Replit), differing only in environment variables.

### 1.3 Non-goals

- NG-1: No simple (single-stimulus) reaction time task (future work).
- NG-2: No mobile/touch support — touch devices are actively blocked.
- NG-3: No OAuth/SSO, no email sending (password resets are done by researchers in-app).
- NG-4: No multi-site/multi-tenant features; one deployment = one lab.
- NG-5: No collection of participant names, emails, or other direct identifiers.
- NG-6: No real-time collaboration; standard request/response is sufficient.

---

## 2. Users & Roles

Three roles: **Admin**, **Researcher**, **Participant**.

- **Admin** — lab PI or manager. Everything a researcher can do, plus manage researcher accounts. At least one admin always exists (seeded at first boot from environment variables `ADMIN_EMAIL`, `ADMIN_PASSWORD`).
- **Researcher** — creates and manages studies, participants, and sessions; views dashboards; exports data. Cannot view, edit, deactivate, or create admin or researcher accounts.
- **Participant** — logs in with a researcher-issued participant code and self-chosen password; sees only their own assigned sessions; runs tasks. Never sees any data views, other participants, or configuration.

### 2.1 Permission matrix

| Capability | Admin | Researcher | Participant |
|---|---|---|---|
| Log in with email + password | ✔ | ✔ | — |
| Log in with participant code + password | — | — | ✔ |
| Create/deactivate researcher accounts | ✔ | ✖ | ✖ |
| Create/deactivate admin accounts | ✔ | ✖ | ✖ |
| Edit own profile/password | ✔ | ✔ | ✔ (password only) |
| Create/edit/archive studies | ✔ | ✔ (all studies — lab trust model, see D-2) | ✖ |
| Define demographic fields | ✔ | ✔ | ✖ |
| Create participants, reset participant passwords, deactivate participants | ✔ | ✔ | ✖ |
| Create/reset/cancel sessions | ✔ | ✔ | ✖ |
| Run a task session | ✖ | ✖ (use preview mode, FR-33) | ✔ (own sessions only) |
| View dashboards & summaries | ✔ | ✔ | ✖ |
| Export CSV | ✔ | ✔ | ✖ |

Per D-2: all researchers in the lab can see and manage all studies (small-lab trust model); the study stores its creator for attribution.

---

## 3. User Flows

### 3.1 Researcher flow (happy path)

1. Researcher navigates to the app URL, clicks **Researcher login** tab, enters email + password.
2. Lands on **Studies** list. Clicks **New study**.
3. Fills in: study name, description (optional), task type (2-CRT / 3-CRT / 4-CRT), and task parameters. All parameters are pre-filled with the defaults in §5.4 and editable inline. Saves.
4. On the study page, opens **Demographics** tab; adds zero or more demographic fields (label, type, options, required, frequency = once / every session). Example fields offered as one-click templates: "Device used (Desktop/Laptop/Tablet-with-keyboard)", "Handedness (Left/Right/Ambidextrous)".
5. Opens **Participants** tab; clicks **Add participants**, enters a count (e.g., 10) and an optional code prefix (e.g., `PILOT`). System generates globally unique codes (`PILOT-A7F3`, …). Alternatively enters custom codes manually (validated unique). Codes are displayed and downloadable as CSV for offline linkage.
6. For each participant (or in bulk for all selected), clicks **Assign sessions**, chooses number of sessions (e.g., 3) and optional per-session task-type/parameter overrides. Sessions are created in a fixed order (session 1, 2, 3 …).
7. Distributes to each participant: the app URL + their participant code (out of band — email, paper, in person).
8. Monitors the **Dashboard** tab: per-participant session status, completion %, RT summaries, visualizations.
9. Clicks **Export CSV** (whole study, single session, or current dashboard view) at any time.

### 3.2 Participant flow (happy path)

1. Participant navigates to the app URL, **Participant login** tab is the default. Enters participant code only; the client calls the code-check endpoint (API #4a).
2. **First access** (`password_set: false`): participant is prompted to create a password (min 6 characters) and confirm it, then is logged in. **Subsequent access** (`password_set: true`): a password field appears; participant enters it and logs in.
3. Lands on **My sessions**: an ordered list of assigned sessions with statuses. Only the earliest non-completed session has a **Start** button; later ones are locked ("Complete session N first").
4. Clicks **Start**. If the device has touch as primary input or viewport < 1024×600, a polite block screen is shown instead (FR-44).
5. **Demographics step** (only if the study defines fields due to be asked now): one-page form, then continue.
6. **Instructions screen:** task-specific instructions with a diagram of the crosses, the key mapping, and the prompt "Place your fingers on the keys: Z X N M" (keys per session config). Button: **Start practice**. Entering the task requests fullscreen (FR-45).
7. **Practice block** (default 3 trials) with feedback on errors/timeouts if enabled.
8. Interstitial screen: "Practice complete. The real test starts now. Respond as quickly and as accurately as you can." Button: **Start test**.
9. **Test block** (default 20 trials), no feedback.
10. **Completion screen:** "Session complete. Thank you!" No RT results are shown to the participant (D-12). Button returns to **My sessions**, where the next session is now unlocked.

### 3.3 Unhappy paths (must be handled; details in §5.7)

- Participant enters an unknown/deactivated code → generic error "Code not recognized. Contact your researcher."
- Participant refreshes or loses connection mid-session → on next login the session resumes at the first un-submitted trial.
- Participant abandons (30 min inactivity while in-progress) → session auto-marked **abandoned**; researcher can reset it.
- Researcher resets a session → status returns to **created**, prior trial data is retained and tagged with an incremented `attempt` number; the next run starts at trial 1 of attempt N+1.

### 3.4 Screen inventory (frontend routes)

| Route | Screen | Access |
|---|---|---|
| `/login` | Tabbed login (Participant default / Researcher) incl. participant set-password step | public |
| `/me` | Participant session list ("My sessions") | P |
| `/run/:sessionId` | Task runner (device gate → demographics → instructions → practice → interstitial → test → completion) | P |
| `/studies` | Studies list + create | A,R |
| `/studies/:id` | Study detail with tabs: Settings, Demographics, Participants, Sessions, Dashboard | A,R |
| `/studies/:id/preview` | Task preview mode (FR-33) | A,R |
| `/admin/users` | User management | A |
| `/account` | Own profile/password | A,R |

Unknown routes → redirect to `/login` or role home. Role guards enforced client-side for UX and server-side for security.

---

## 4. Functional Requirements

Numbered FR-1 … FR-57, grouped by module. Every FR has acceptance criteria in §10 (AC numbers match FR numbers).

### 4.1 Authentication & accounts

- **FR-1** The system shall provide email + password login for admins and researchers, returning a signed JWT access token (30 min expiry) and a refresh token (7 days) stored as an `httpOnly`, `SameSite=Lax` cookie. Passwords hashed with bcrypt, cost 12.
- **FR-2** The system shall provide participant login with participant code + password, issuing a JWT with role `participant` scoped to that participant ID only.
- **FR-3** On first participant access (code exists, `password_hash` is NULL), the system shall require the participant to set a password (min 6 characters) before proceeding. The set-password endpoint shall only succeed while `password_hash` is NULL.
- **FR-4** Admins shall be able to create, list, edit (name, email, role), and deactivate admin and researcher accounts. An admin cannot deactivate their own account. Deactivated users cannot log in; their data remains.
- **FR-5** Researchers and admins shall be able to reset a participant's password (sets `password_hash` to NULL, forcing the set-password flow on next access).
- **FR-6** All auth endpoints shall be rate-limited: max 10 failed attempts per identifier per 15 minutes (in-memory or DB-backed counter), responding `429` thereafter.
- **FR-7** On first application boot, if no admin exists, the system shall create one from `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment variables and log a warning prompting a password change.
- **FR-8** Logout shall invalidate the refresh cookie. Access tokens expire naturally.

### 4.2 Study management

- **FR-9** Researchers shall create studies with: name (required, ≤120 chars), description (optional, ≤2000 chars), task type (`CRT2` | `CRT3` | `CRT4`), and a full task-parameter set (defaults per §5.4, all editable at creation and any time before the first session starts; after any session has started, parameters become read-only on the study and a banner explains why — per-session snapshots guarantee historical integrity regardless).
- **FR-10** Studies shall be listable (with participant/session counts and completion stats), editable (name/description always; parameters per FR-9), and archivable. Archived studies are hidden from default lists, block new sessions, but retain all data and remain exportable.
- **FR-11** Each study shall record `created_by` (user id) and timestamps.

### 4.3 Demographics builder

- **FR-12** Researchers shall define, per study, an ordered list of demographic fields. Each field: label (≤80 chars), type (`text` | `number` | `single_choice` | `boolean`), options (required array of ≤20 strings for `single_choice`), required flag, and frequency (`once` = asked at the participant's first session in the study; `every_session` = asked at the start of every session).
- **FR-13** Fields shall be addable/editable/deletable until any participant has answered them; thereafter label and options are read-only (a new field must be created instead) to keep responses interpretable.
- **FR-14** The participant-facing demographics form shall render all fields due for the current session on one page, validate required fields and number ranges client- and server-side, and store answers linked to participant and session.
- **FR-15** No field capable of capturing direct identifiers shall be templated; free-text fields shall display a researcher-facing hint at creation: "Do not use this to collect names or contact details."

### 4.4 Participant & session management

- **FR-16** Researchers shall create participants under a study either (a) in bulk: count N (1–500) + optional prefix → system generates codes of form `{PREFIX-}XXXX` where `XXXX` is 4 chars from the unambiguous alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, globally unique; or (b) manually: custom codes 3–32 chars `[A-Za-z0-9_-]`, validated globally unique (case-insensitive).
- **FR-17** The participant list shall show: code, password-set status, sessions assigned/completed, last activity, active flag. Researchers can deactivate participants (blocks login, keeps data) and download the code list as CSV.
- **FR-18** Researchers shall assign sessions to one or many selected participants at once: number of sessions to add (1–50), each new session inheriting the study's task type and parameter set as an immutable **snapshot** at creation time, with optional overrides (any parameter, including task type) applied before snapshotting. New sessions' `order_index` continues from each participant's current maximum (a participant with sessions 1–2 who receives 2 more gets 3 and 4).
- **FR-19** Each session shall store: UUID id, unique 8-char session code (same alphabet as FR-16), participant id, study id, order index (1-based per participant), task type, full parameter snapshot (JSON), status (`created` | `in_progress` | `completed` | `abandoned`), `attempt` counter (starts 1), `started_at`, `completed_at`, `created_at`.
- **FR-20** Sessions for a participant shall be runnable strictly in order: the participant UI and the `start` endpoint shall both refuse to start session k+1 while session k is not `completed` (server returns `409`).
- **FR-21** A session shall transition `created → in_progress` on start, `in_progress → completed` when the final test trial is submitted and the complete endpoint is called, and `in_progress → abandoned` when last trial activity is older than 30 minutes (evaluated lazily on any read of the session, no background scheduler required).
- **FR-22** Researchers shall be able to **reset** a `completed`/`abandoned`/`in_progress` session: status → `created`, `attempt` += 1; existing trial rows are retained with their original attempt number. Researchers shall also be able to **delete** a session only if it has zero trial rows.
- **FR-23** Researchers shall be able to cancel (soft-delete) unstarted sessions; cancelled sessions disappear from the participant's list.

### 4.5 Task engine (common to all tasks)

- **FR-24** The task engine shall implement the trial state machine of §5.5 exactly, driven entirely by the session's parameter snapshot — no hard-coded parameter values in the task code.
- **FR-25** The engine shall draw the stimulus position on each trial uniformly at random from the task's positions, with the constraint configurable as `max_consecutive_repeats` (default 3; a position may not appear more than 3 times in a row).
- **FR-26** Foreperiod per trial shall be drawn uniformly at random from `[foreperiod_min_ms, foreperiod_max_ms]` (integer ms, defaults 1000–3000).
- **FR-27** Stimulus onset shall be scheduled via `requestAnimationFrame`; the onset timestamp shall be the `performance.now()` value captured inside the rAF callback that paints the box. Keyboard responses shall be captured via a `keydown` listener; RT = `event.timeStamp` (or `performance.now()` in the handler) − onset timestamp, reported in ms with 1 decimal place.
- **FR-28** Keys shall be matched by `KeyboardEvent.code` (physical key position, layout-independent: `KeyZ`, `KeyX`, `KeyC`, `KeyN`, `KeyM`, `ArrowLeft`, `ArrowRight`); the UI shall display the corresponding key cap labels. Key auto-repeat (`event.repeat === true`) shall be ignored.
- **FR-29** A mapped keydown during the foreperiod is a **premature response**: increment the trial's `premature_count`, log it, restart the foreperiod with a fresh random draw (same trial), and — in practice block only — show "Too soon!" for 1000 ms first. A mapped keydown during the ITI likewise increments `premature_count` (with the same practice warning) but the ITI simply continues. The trial itself always continues; it is never discarded for prematurity.
- **FR-30** Non-mapped keys during the response window shall be ignored for outcome purposes but counted in the trial's `extraneous_keys`.
- **FR-31** If no mapped key is pressed within `response_timeout_ms` (default 3000) of stimulus onset, the trial outcome is `timeout` (rt null). In practice, if feedback is enabled, show "Too slow" for `feedback_duration_ms`.
- **FR-32** Practice-block feedback (if `practice_feedback` true, default true): on incorrect → red "✗" centered below the stimuli for `feedback_duration_ms` (default 500); on timeout → "Too slow"; on correct → no feedback. Test block never shows feedback.
- **FR-33** Researchers shall have a **Preview** button on a study that runs the exact task client (practice + test, both shortened to 3 trials) without creating any session or trial data.
- **FR-34** Trial data shall be buffered client-side and POSTed in batches of 5 trials, plus a flush at each block end and on `pagehide`/`visibilitychange` via `navigator.sendBeacon`. Each trial row carries a client-generated UUID; the server upserts idempotently on it (safe retries).
- **FR-35** On session start/resume, the server shall return the set of already-stored trial UUIDs/indices for the current attempt so the client resumes at the first missing trial (per block); a resumed session increments a `resume_count` on the session.

### 4.6 Task-specific requirements

- **FR-36 (4-CRT)** Four crosses in a horizontal row. Default key mapping left→right: `KeyZ`, `KeyX`, `KeyN`, `KeyM`. Instructions name the fingers: left middle, left index, right index, right middle.
- **FR-37 (3-CRT)** Three crosses in a horizontal row. Default key mapping left→right: `KeyZ`, `KeyX`, `KeyC`.
- **FR-38 (2-CRT)** Two crosses (left, right). Default key mapping: `ArrowLeft`, `ArrowRight`.
- **FR-39** Key mappings shall be editable per study/session: the researcher picks any distinct `KeyboardEvent.code` values from an allowed list (all letters, digits, arrows); the UI prevents duplicates and shows resulting labels.
- **FR-40** Correctness = pressed key's mapped position index equals the stimulus position index. Any other mapped key → `incorrect` with RT recorded.

### 4.7 Data capture

- **FR-41** Each trial row shall store: client UUID, session id, attempt, block (`practice`|`test`), trial index (1-based within block), stimulus position (0-based), foreperiod ms (as drawn), key pressed (code or null), response position (or null), outcome (`correct`|`incorrect`|`timeout`|`invalid`), rt_ms (float, 1 decimal, null for timeout/invalid), premature_count, extraneous_keys, invalid_reason (null | `focus_loss` | `fullscreen_exit`), outlier_flag (bool, computed server-side per study thresholds), client timestamps (onset, response) and server `created_at`.
- **FR-42** Outlier flagging: server marks `outlier_flag = true` where outcome=`correct` and (rt < `outlier_low_ms` or rt > `outlier_high_ms`) (defaults 150 / 1500, editable per study). Flagged trials are **never deleted**; statistics report raw and trimmed variants (§4.9).
- **FR-43** The client shall record and send, once per session start: user agent, screen resolution, devicePixelRatio, reported refresh-rate estimate (measured by timing 60 rAF frames), and timezone — stored on the session for data-quality auditing.

### 4.8 Device gating & display integrity

- **FR-44** Before starting a session the client shall block devices where `navigator.maxTouchPoints > 0` AND `matchMedia('(pointer: coarse)')` matches, or viewport < 1024×600, showing: "This experiment requires a desktop or laptop computer with a physical keyboard. Please switch devices and log in again."
- **FR-45** Entering the task (instructions → practice) shall request browser fullscreen. If the participant exits fullscreen mid-trial, the current trial is invalidated (`invalid_reason = fullscreen_exit`), the task pauses with "Press Continue to re-enter fullscreen", and the invalidated trial is re-queued at the end of its block (max 5 re-queues per block; beyond that, invalid trials stand). **Re-queue indexing:** the invalid trial keeps its `trial_index`; the re-queued replacement is appended with the next available index in that block (e.g., test trial 7 invalidated → replacement becomes trial 21 of a 20-trial block). A block with k invalidations therefore has `block_size + min(k, 5)` rows, of which `block_size − max(0, k − 5)` are non-invalid.
- **FR-46** `blur`/`visibilitychange` (hidden) during foreperiod or response window invalidates the current trial likewise (`invalid_reason = focus_loss`), same re-queue rule as FR-45.

### 4.9 Summary statistics

All statistics are computed server-side, on **test-block trials of the latest attempt** of a session, in two variants: **raw** (all correct trials) and **trimmed** (correct, `outlier_flag = false`). Definitions (D-9):

- **FR-47** Per-session summary: n_trials, n_correct, accuracy % (= n_correct / (n_trials − n_invalid) × 100; timeouts count as errors), n_timeouts, n_premature (sum of premature_count), n_invalid, n_outliers_flagged; and for each variant: mean RT, median RT, SD RT, **CoV = SD/mean**, **IIV(within) = intra-individual SD of RTs** (numerically equal to SD RT; reported under its own label for the dashboard's IIV views).
- **FR-48** Per-participant summary (per study): the per-session stats per FR-47 for every completed session, plus across-session aggregates when ≥2 sessions are completed: mean of session means, **IIV(between) = SD of session mean RTs**, CoV(between) = IIV(between)/mean of session means.
- **FR-49** Per-study summary: distribution of per-session trimmed mean RT, SD, accuracy across participants (group mean ± SD per metric), completion counts.

### 4.10 Researcher dashboard

- **FR-50** Dashboard (per study) shall show: a sessions table (participant code, session order, status, started/completed timestamps, attempt, trimmed mean RT, accuracy, flags count) with filters (status, participant) and column sorting.
- **FR-51** Visualizations (client-rendered with Recharts): (a) RT histogram for a selected session (trial RTs, 50 ms bins, outliers highlighted); (b) box/strip plot of trimmed mean RT per participant across the study; (c) per-participant bar chart of SD RT (IIV-within) by session; (d) line chart of session-mean RT across session order per participant (visualizing IIV-between); (e) accuracy % per participant.
- **FR-52** Every table and every chart's underlying data shall have a **Download CSV** button that exports exactly the rows/points displayed (current filters applied).
- **FR-53** A study-level header shall show: participants (n), sessions completed / assigned, overall completion %, last activity.

### 4.11 Export

- **FR-54** Trial-level CSV export at three scopes: single session, single participant (all sessions), whole study. One row per trial (all attempts, practice and test included; columns identify them). Exact columns, in order: `study_name, study_id, task_type, participant_code, session_code, session_order, attempt, block, trial_index, stimulus_position, foreperiod_ms, key_pressed, response_position, outcome, rt_ms, premature_count, extraneous_keys, invalid_reason, outlier_flag, stimulus_onset_client_ms, session_started_at_iso, session_completed_at_iso`.
- **FR-55** Summary CSV export at study scope: one row per session with all FR-47 statistics (raw and trimmed columns suffixed `_raw` / `_trim`), plus participant across-session rows per FR-48 in a second file `participants_summary.csv` (study scope export returns a ZIP containing `trials.csv`, `sessions_summary.csv`, `participants_summary.csv`, `demographics.csv`).
- **FR-56** Demographics CSV: one row per participant per session-asked instance: `participant_code, session_code (blank for frequency=once), field_label, field_type, value, answered_at_iso`.
- **FR-57** CSV format: UTF-8, comma-separated, RFC 4180 quoting, header row, ISO-8601 UTC timestamps, decimal point `.`, empty string for nulls. Filenames: `{study_name_slug}_{scope}_{YYYYMMDD-HHMM}.csv|zip`.

---

## 5. Task Specification

### 5.1 Visual layout

- Task screen: solid white background (`#FFFFFF`), all stimuli pure black (`#000000`). No other UI elements during trials except a thin, 4 px-tall progress bar at the very bottom of the screen (light gray, fills per completed trial; absent if `show_progress` = false, default true).
- Stimulus row: horizontally and vertically centered in the viewport. N stimulus containers (N = 2, 3, or 4 per task), each **96 × 96 px**, separated by **48 px** gaps.
- **Cross (default state):** a plus sign drawn as two centered strokes, arm length 56 px total (28 px each side of center), stroke width 6 px.
- **Box (stimulus):** the cross is replaced by an open square outline, 64 × 64 px, stroke width 6 px, centered in the same container. Exactly one container shows the box at a time; all others keep crosses.
- Below the row, 64 px down, a feedback zone (practice only): "✗" (red `#CC0000`, 48 px), "Too slow", or "Too soon!" (32 px black text).
- Render with plain DOM/SVG (not canvas); toggling cross→box must change only the one container's content to keep paint cost minimal.

### 5.2 Key mappings (defaults)

| Task | Positions (left→right) | Default codes | Displayed labels |
|---|---|---|---|
| 2-CRT | 0, 1 | `ArrowLeft`, `ArrowRight` | ← → |
| 3-CRT | 0, 1, 2 | `KeyZ`, `KeyX`, `KeyC` | Z X C |
| 4-CRT | 0, 1, 2, 3 | `KeyZ`, `KeyX`, `KeyN`, `KeyM` | Z X N M |

### 5.3 Instructions copy (verbatim default, editable per study via `instructions_text`; placeholders `{N}` = number of positions, `{KEYS}` = key labels left→right, `{P}` = practice trials, `{T}` = test trials are substituted at render time)

> You will see {N} crosses on the screen. On each trial, one of the crosses will change into a box. Press the key that matches the position of the box as quickly and as accurately as you can. The keys are: {KEYS}. Place your fingers on these keys now. There will be {P} practice trials first, then {T} test trials.

### 5.4 Parameters & Deary-Liewald defaults

Every session snapshot contains exactly these keys:

| Parameter | Type | Default | Constraints |
|---|---|---|---|
| `task_type` | enum | (per study) | `CRT2` \| `CRT3` \| `CRT4` |
| `practice_trials` | int | 3 | 0–50 |
| `test_trials` | int | 20 | 1–500 |
| `foreperiod_min_ms` | int | 1000 | 200–10000, ≤ max |
| `foreperiod_max_ms` | int | 3000 | 200–10000 |
| `response_timeout_ms` | int | 3000 | 500–10000 |
| `iti_ms` | int | 500 | 0–5000 |
| `key_map` | array of codes | per §5.2 | distinct, length = N positions |
| `practice_feedback` | bool | true | — |
| `feedback_duration_ms` | int | 500 | 100–3000 |
| `max_consecutive_repeats` | int | 3 | 1–10 |
| `outlier_low_ms` | int | 150 | ≥0 |
| `outlier_high_ms` | int | 1500 | > low |
| `show_progress` | bool | true | — |
| `instructions_text` | string | §5.3 template | ≤2000 chars |

### 5.5 Trial state machine

States per trial: `ITI → FOREPERIOD → STIMULUS → (RESPONSE | TIMEOUT) → [FEEDBACK] → next trial`.

1. **ITI** (`iti_ms`, default 500 ms): all crosses displayed.
2. **FOREPERIOD** (uniform random integer in `[foreperiod_min_ms, foreperiod_max_ms]`, drawn per trial): all crosses displayed. Mapped keydown here or in ITI → premature handling per FR-29 (count, optional "Too soon!" in practice, redraw foreperiod, stay in this trial).
3. **STIMULUS**: at the scheduled time, the next rAF callback swaps the target cross for the box and records onset = `performance.now()`. Crosses remain in all other positions; box stays visible until response or timeout (Deary-Liewald style).
4. **RESPONSE**: first non-repeat mapped keydown → record key, RT, outcome `correct`/`incorrect`; box reverts to cross.
5. **TIMEOUT**: no mapped key within `response_timeout_ms` → outcome `timeout`.
6. **FEEDBACK** (practice only, per FR-31/32), then loop to ITI of next trial.

Block sequence: instructions → practice (n = `practice_trials`; skip block entirely if 0) → interstitial → test (n = `test_trials`) → completion. Trial indices restart at 1 per block.

### 5.6 Timing implementation & documented precision limits

- All client timestamps from `performance.now()` (monotonic, sub-ms resolution; browsers may coarsen to 0.1–1 ms — acceptable).
- Stimulus onset error is bounded by display refresh: at 60 Hz up to one frame (~16.7 ms) between rAF paint and physical pixels, plus monitor latency. Keyboard adds ~1–15 ms USB polling/debounce. Net effect: absolute RTs may carry ~5–30 ms constant-plus-jitter offset, comparable to published web-based RT validations; within-participant comparisons (the scientific use case) are unaffected by the constant component.
- The client measures approximate refresh rate at session start (FR-43) so researchers can audit outliers from 30 Hz or variable-refresh displays.
- Never use `setTimeout` to time stimulus onset directly; use it only to schedule "arm the next rAF swap" ahead of the target time, then swap on the first rAF whose timestamp ≥ target.

### 5.7 Edge cases (normative)

| Event | Handling |
|---|---|
| Early keypress (ITI/foreperiod) | FR-29: premature_count++, foreperiod redrawn, trial continues |
| Wrong mapped key | Outcome `incorrect`, RT recorded |
| Unmapped key | Ignored; extraneous_keys++ |
| Key held down (auto-repeat) | `event.repeat` ignored |
| Focus loss / tab hidden mid-trial | Trial → `invalid` (`focus_loss`), pause overlay, re-queue at block end (≤5/block) |
| Fullscreen exited mid-trial | Same as above with `fullscreen_exit` |
| Refresh / crash / network loss | Batched idempotent uploads (FR-34); resume at first missing trial (FR-35) |
| Network error on batch POST | Retry with exponential backoff (1 s, 2 s, 4 s … max 30 s) while buffering; task continues uninterrupted; warn only if buffer > 50 trials |
| 30 min inactivity in-progress | Session `abandoned` (lazy, FR-21) |
| Two browser tabs same session | `start` endpoint returns the same resume state; last writer wins on idempotent upserts — documented, not prevented (D-13) |

---

## 6. Non-Functional Requirements

- **NFR-1 Timing:** as specified in §5.6; the implementation shall include an automated test that fakes rAF/`performance.now()` to verify RT computation logic to ±0.1 ms.
- **NFR-2 Browsers:** latest 2 major versions of Chrome, Edge, Firefox, plus Safari ≥ 16.4, desktop only. No IE/legacy support.
- **NFR-3 Performance:** trial loop produces zero network requests during FOREPERIOD/STIMULUS/RESPONSE states (uploads only in ITI/feedback/block boundaries); dashboard pages load < 2 s for 100 participants × 10 sessions × 500 trials.
- **NFR-4 Accessibility (researcher UI only):** semantic HTML, labels on all inputs, keyboard navigable, WCAG AA contrast. The participant task screen is exempt by experimental necessity (fixed colors/geometry).
- **NFR-5 Security:** bcrypt cost 12; JWT signed HS256 with `SECRET_KEY` ≥ 32 random bytes; rate limiting per FR-6; CORS allowlist from `ALLOWED_ORIGINS` env (empty = same-origin only); all cookies `Secure` when `APP_ENV != "development"`; HTTPS terminated by the tunnel/host (the app never handles certs); SQL via ORM parameterization only; no secrets in code or logs.
- **NFR-6 Privacy / IRB-friendliness:** no participant PII fields anywhere in schema or UI; participant codes are the only identifier; server logs exclude request bodies on participant endpoints; data deletable per participant (deactivate + cascade-export then manual SQL is acceptable; in-app hard delete is future work).
- **NFR-7 Reliability:** idempotent trial ingestion (FR-34); all state transitions enforced server-side; database is the single source of truth.
- **NFR-8 Code quality:** typed Python (mypy-clean), TypeScript strict mode; backend unit tests for statistics (FR-47/48 against hand-computed fixtures), state transitions, and auth; minimal frontend tests for RT computation and the trial state machine.

---

## 7. Data Model

PostgreSQL 16 (production) / SQLite (only if `DATABASE_URL` is absent in local dev). SQLAlchemy 2.x models + Alembic migrations. UUID PKs (`uuid4`) except `trials.id BIGSERIAL`. All timestamps `timestamptz` UTC.

```text
users
  id UUID PK | email TEXT NOT NULL (UNIQUE INDEX on lower(email)) | password_hash TEXT NOT NULL
  full_name TEXT NOT NULL | role TEXT CHECK (role IN ('admin','researcher'))
  is_active BOOL DEFAULT true | created_at | updated_at

studies
  id UUID PK | name TEXT NOT NULL | description TEXT
  task_type TEXT CHECK (task_type IN ('CRT2','CRT3','CRT4'))
  params JSONB NOT NULL            -- full §5.4 parameter set (study defaults)
  created_by UUID FK->users | is_archived BOOL DEFAULT false
  created_at | updated_at

participants
  id UUID PK | study_id UUID FK->studies
  code TEXT UNIQUE NOT NULL        -- globally unique, case-insensitive (store uppercase)
  password_hash TEXT NULL          -- NULL until first access
  is_active BOOL DEFAULT true | created_at | last_login_at NULL

demographic_fields
  id UUID PK | study_id FK->studies | label TEXT NOT NULL
  field_type TEXT CHECK (IN ('text','number','single_choice','boolean'))
  options JSONB NULL | required BOOL | frequency TEXT CHECK (IN ('once','every_session'))
  display_order INT | is_retired BOOL DEFAULT false | created_at

demographic_responses
  id UUID PK | participant_id FK | field_id FK | session_id UUID NULL FK
  value TEXT NOT NULL | created_at
  -- NULL session_id rows (frequency=once) would not collide under a plain UNIQUE
  -- constraint, so use two partial unique indexes:
  UNIQUE INDEX (participant_id, field_id) WHERE session_id IS NULL
  UNIQUE INDEX (participant_id, field_id, session_id) WHERE session_id IS NOT NULL
  -- re-submission upserts (last write wins)

sessions
  id UUID PK | code TEXT UNIQUE NOT NULL | participant_id FK | study_id FK
  order_index INT NOT NULL         -- 1-based per participant
  task_type TEXT | params JSONB NOT NULL   -- immutable snapshot
  status TEXT CHECK (IN ('created','in_progress','completed','abandoned','cancelled'))
  attempt INT DEFAULT 1 | resume_count INT DEFAULT 0
  client_env JSONB NULL            -- FR-43 payload
  started_at NULL | completed_at NULL | last_activity_at NULL | created_at
  UNIQUE (participant_id, order_index)

trials
  id BIGSERIAL PK | client_uuid UUID UNIQUE NOT NULL | session_id FK
  attempt INT | block TEXT CHECK (IN ('practice','test')) | trial_index INT
  stimulus_position INT | foreperiod_ms INT
  key_pressed TEXT NULL | response_position INT NULL
  outcome TEXT CHECK (IN ('correct','incorrect','timeout','invalid'))
  rt_ms NUMERIC(7,1) NULL | premature_count INT DEFAULT 0
  extraneous_keys INT DEFAULT 0 | invalid_reason TEXT NULL
  outlier_flag BOOL DEFAULT false
  stimulus_onset_client_ms NUMERIC(12,1) NULL | response_client_ms NUMERIC(12,1) NULL
  created_at
  UNIQUE (session_id, attempt, block, trial_index)
  INDEX (session_id, attempt, block)
```

Relationships: users 1-N studies; studies 1-N participants, demographic_fields, sessions; participants 1-N sessions, demographic_responses; sessions 1-N trials. Deletes: studies/participants are never hard-deleted (archive/deactivate); sessions hard-deletable only with zero trials (FR-22).

---

## 8. API Design

FastAPI, prefix `/api/v1`, JSON. Auth via `Authorization: Bearer <JWT>` (refresh via httpOnly cookie on `/auth/refresh`). Roles: **A**dmin, **R**esearcher, **P**articipant. Errors: RFC 7807-style `{"detail": "..."}` with appropriate 4xx/5xx.

| # | Method & path | Auth | Request → Response (shapes abbreviated) |
|---|---|---|---|
| 1 | POST `/auth/login` | — | `{email, password}` → `{access_token, user:{id,email,full_name,role}}` + refresh cookie |
| 2 | POST `/auth/refresh` | cookie | → new `{access_token}` |
| 3 | POST `/auth/logout` | any | → 204, clears cookie |
| 4 | POST `/auth/participant/login` | — | `{code, password}` → `{access_token, participant:{id, code, study_name}}` + refresh cookie (so long sessions survive the 30-min access-token expiry); `409 password_not_set` if first access |
| 4a | POST `/auth/participant/check` | — | `{code}` → `{password_set: bool}`; 404 for unknown/deactivated codes (same generic message; rate-limited per FR-6) |
| 5 | POST `/auth/participant/set-password` | — | `{code, password}` (only while hash NULL) → as #4 |
| 6 | GET/POST `/users` | A | list / `{email, full_name, role, password}` → user |
| 7 | PATCH `/users/{id}` | A | `{full_name?, email?, role?, is_active?, password?}` → user (cannot deactivate self) |
| 8 | GET/POST `/studies` | A,R | list (query: `archived`) / `{name, description?, task_type, params?}` → study (params merged over §5.4 defaults) |
| 9 | GET/PATCH `/studies/{id}` | A,R | study detail incl. counts / edit per FR-9/10; `{is_archived}` to archive |
| 10 | GET/POST `/studies/{id}/demographic-fields` | A,R | list / create per FR-12 |
| 11 | PATCH/DELETE `/demographic-fields/{id}` | A,R | edit/delete per FR-13 (DELETE retires if answered) |
| 12 | GET/POST `/studies/{id}/participants` | A,R | list per FR-17 / `{count, prefix?}` or `{codes:[...]}` → created participants |
| 13 | PATCH `/participants/{id}` | A,R | `{is_active?, reset_password?:true}` |
| 14 | GET `/studies/{id}/participants.csv` | A,R | CSV of codes |
| 15 | POST `/studies/{id}/sessions` | A,R | `{participant_ids:[...], count, overrides?:{task_type?, params?}}` → sessions created |
| 16 | GET `/studies/{id}/sessions` | A,R | query: `status?, participant_id?, sort?` → session rows incl. summary stats |
| 17 | PATCH `/sessions/{id}` | A,R | `{action: "reset" | "cancel"}` per FR-22/23 |
| 18 | DELETE `/sessions/{id}` | A,R | 204 only if zero trials, else 409 |
| 19 | GET `/me/sessions` | P | participant's ordered sessions with statuses and lock state |
| 20 | POST `/sessions/{id}/start` | P (owner) | → `{params, task_type, attempt, demographics_due:[fields], stored_trials:{practice:[idx], test:[idx]}}`; 409 if out of order (FR-20) |
| 21 | POST `/sessions/{id}/demographics` | P | `{answers:[{field_id, value}]}` → 204 |
| 22 | POST `/sessions/{id}/trials` | P | `{trials:[TrialIn, …≤25]}` idempotent upsert by client_uuid → `{accepted: n}`; updates `last_activity_at`; server overrides any client-sent `attempt` with the session's current attempt; rejects (409) if session not `in_progress` |
| 23 | POST `/sessions/{id}/complete` | P | → 204; validates the test block per the FR-45 row-count rule — `rows = test_trials + min(k, 5)` and contiguous `trial_index` 1..rows, where k = invalid test rows — else 409 with the missing indices; sets `completed` |
| 24 | POST `/sessions/{id}/client-env` | P | FR-43 payload → 204 |
| 25 | GET `/sessions/{id}/summary` | A,R | FR-47 stats (raw + trimmed) |
| 26 | GET `/participants/{id}/summary` | A,R | FR-48 incl. IIV(between) |
| 27 | GET `/studies/{id}/summary` | A,R | FR-49 + dashboard aggregates (FR-50/51 data) |
| 28 | GET `/sessions/{id}/export.csv` | A,R | trial CSV (FR-54) |
| 29 | GET `/participants/{id}/export.csv` | A,R | trial CSV |
| 30 | GET `/studies/{id}/export.zip` | A,R | ZIP per FR-55 |
| 31 | GET `/health` | — | `{status:"ok", db:"ok"}` |
| 32 | POST `/studies/{id}/preview` | A,R | → `{params}` for preview mode (no session created) |

`TrialIn` = `{client_uuid, attempt, block, trial_index, stimulus_position, foreperiod_ms, key_pressed, response_position, outcome, rt_ms, premature_count, extraneous_keys, invalid_reason, stimulus_onset_client_ms, response_client_ms}`. Server recomputes `outcome` consistency (position vs key vs key_map) and `outlier_flag`; rejects rows for sessions not `in_progress` or not owned by the token.

---

## 9. Deployment & Migration Plan

### 9.1 Repository layout & containers

```
/backend   FastAPI app, SQLAlchemy, Alembic, pytest
/frontend  React 18 + TypeScript + Vite + Tailwind + Recharts
/docker-compose.yml
/.env.example
```

Docker Compose services:

1. `db` — `postgres:16-alpine`, volume `pgdata`, healthcheck `pg_isready`.
2. `api` — Python 3.12 image; runs `alembic upgrade head` then `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
3. `web` — multi-stage build: `node:20` builds Vite bundle → `nginx:alpine` serves static files **and proxies `/api/` to `api:8000`**. Exposes container port 80, published per `WEB_PORT` (default 8080).

The frontend calls the API at the **relative path `/api/v1`** — never an absolute URL. This single-origin design eliminates CORS and means the same images work unmodified on localhost, a tunnel URL, or a public domain (G-5).

### 9.2 Environment variables (complete list, `.env.example` must include all)

| Variable | Used by | Default (dev) | Notes |
|---|---|---|---|
| `DATABASE_URL` | api | `postgresql+psycopg://crt:crt@db:5432/crt` | SQLite fallback `sqlite:///./dev.db` only when unset and `APP_ENV=development` |
| `SECRET_KEY` | api | — (required) | ≥32 random bytes |
| `APP_ENV` | api | `development` | `development` \| `production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | api | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | api | `7` | |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | api | — (required first boot) | seed admin (FR-7) |
| `ALLOWED_ORIGINS` | api | empty | comma-separated; empty = same-origin proxy only |
| `WEB_PORT` | compose | `8080` | host port for `web` |
| `POSTGRES_USER/PASSWORD/DB` | db | `crt/crt/crt` | change in production |

### 9.3 Phase 1 — Local development

`docker compose up` → app at `http://localhost:8080`. Hot-reload dev mode optional via `docker-compose.dev.yml` (uvicorn `--reload`, Vite dev server with proxy).

### 9.4 Phase 2 — Lab testing via tunnel

Run the same compose stack on one lab machine. Expose with either:

- **Tailscale (preferred):** `tailscale up` on the host; lab members join the tailnet and use `http://<machine-name>:8080`, or `tailscale serve --bg 8080` for HTTPS at `https://<machine-name>.<tailnet>.ts.net`. Access limited to tailnet members — no public exposure.
- **ngrok:** `ngrok http 8080` → temporary public HTTPS URL; protect with `--basic-auth` for casual privacy.

No application changes: cookies are host-relative, API path is relative, HTTPS is terminated by the tunnel.

### 9.5 Phase 3 — Public hosting

Deploy the same two images (api, web) + managed Postgres to Railway, Render, or Fly.io (all support Docker + managed Postgres; Replit via its Docker/VM deployments). Checklist: set `APP_ENV=production`, real `SECRET_KEY`, managed-Postgres `DATABASE_URL`, strong `ADMIN_PASSWORD`, custom domain + platform TLS, automated DB backups, run `alembic upgrade head` (already automatic on api start). **Nothing else changes** — this is the zero-rework guarantee.

Note: Lovable/Bolt are not deployment targets for this stack (they generate JS-only apps); Replit/Railway/Render/Fly.io are the supported public hosts.

---

## 10. Acceptance Criteria

Each AC is testable as written; AC-n maps to FR-n (one or more criteria per FR).

- **AC-1** Logging in with valid researcher credentials returns 200 with a JWT whose payload contains the user id and role; an invalid password returns 401; the response sets an httpOnly refresh cookie.
- **AC-2** A participant JWT cannot call any A/R endpoint (403) and cannot start another participant's session (403/404).
- **AC-3** Set-password succeeds exactly once for a fresh code; a second call returns 409; passwords < 6 chars return 422.
- **AC-4** A researcher token calling `POST /users` receives 403; an admin succeeds; an admin PATCHing their own `is_active=false` receives 409.
- **AC-5** After reset_password, the participant's next login returns `409 password_not_set` and the set-password flow succeeds.
- **AC-6** The 11th failed login within 15 minutes for the same identifier returns 429.
- **AC-7** Booting with an empty users table and `ADMIN_EMAIL/PASSWORD` set creates exactly one active admin.
- **AC-8** After logout, `POST /auth/refresh` returns 401.
- **AC-9/10/11** Creating a study with no params uses §5.4 defaults verbatim (verify JSON equality); editing params after a session has started returns 409; archived studies reject new session creation with 409.
- **AC-12–15** Creating a `single_choice` field without options returns 422; a field answered by ≥1 participant rejects label edits (409) and DELETE retires it instead; required-field omission on submit returns 422; submitted answers appear in the demographics CSV.
- **AC-16** Bulk-creating 100 participants yields 100 globally unique codes matching `^[A-Z0-9_-]+$`; supplying a duplicate custom code returns 409.
- **AC-17** Deactivated participant login returns 401; their data still exports.
- **AC-18/19** Sessions created for 3 selected participants with count 2 yields 6 sessions with order_index 1–2 each and `params` deep-equal to study params merged with overrides; snapshots do not change when the study is later edited.
- **AC-20** Starting session 2 while session 1 is `created`/`in_progress` returns 409; the UI shows it locked.
- **AC-21** A session with `last_activity_at` 31 minutes old reads back as `abandoned`.
- **AC-22** Reset sets status `created`, attempt 2; old attempt-1 trials remain queryable and exported with `attempt=1`; DELETE on a session with trials returns 409.
- **AC-23** `complete` on a session missing test trial rows returns 409 listing the missing indices; with all `test_trials` rows present (or the FR-45 invalid/re-queue arithmetic satisfied) it returns 204 and the session reads back `completed` with `completed_at` set; calling it twice returns 409 the second time.
- **AC-4a** `check` with an unclaimed code returns `{password_set:false}`, with a claimed code `{password_set:true}`, and with an unknown or deactivated code a 404 whose message is identical in both cases.
- **AC-24–32 (task engine, automated where possible + manual script)** With a seeded RNG in test mode: positions never exceed 3 consecutive repeats; foreperiods all within [1000, 3000]; a simulated keydown 234.5 ms after onset stores `rt_ms = 234.5`; `event.repeat` keydowns are ignored; a mapped keydown during foreperiod increments `premature_count`, redraws the foreperiod, and (practice) shows "Too soon!" for 1000 ms; unmapped keys increment `extraneous_keys` only; absence of keys for `response_timeout_ms` yields outcome `timeout` with null RT; practice shows "✗" on errors only when `practice_feedback` is true; test block never shows feedback; preview mode creates zero DB rows.
- **AC-34/35** Killing the network mid-block loses at most the unflushed buffer (<5 trials, recovered by sendBeacon in normal navigation); re-POSTing the same batch changes nothing (idempotent); after a forced refresh mid-test, resuming presents exactly the first missing trial index and `resume_count` = 1.
- **AC-36–40** For each task type, the rendered DOM contains exactly N containers; default key maps equal §5.2; a key map with duplicate codes is rejected 422; pressing the key mapped to position 2 when stimulus is at position 2 → `correct`, at position 0 → `incorrect` with RT recorded.
- **AC-41–43** A completed session's trial rows contain every §4.7 field non-null where applicable; a correct 120 ms trial is `outlier_flag=true` given default thresholds; `client_env` contains user agent and measured refresh rate.
- **AC-44** With Chrome DevTools device emulation (touch + 390×844), the start screen shows the block message and no session starts.
- **AC-45/46** Exiting fullscreen mid-trial marks that trial `invalid/fullscreen_exit`, shows the resume overlay, and appends a re-queued trial to the block (verified in trial indices); the 6th invalidation in a block is not re-queued.
- **AC-47** For a fixture session with hand-computed statistics (provide ≥20 synthetic trials in tests), mean/median/SD/CoV/accuracy match to 4 decimals in both raw and trimmed variants; IIV(within) equals SD.
- **AC-48** For a participant with 3 completed sessions of known means, IIV(between) equals the hand-computed SD of those means.
- **AC-50–53** Dashboard table filters by status and participant; each chart and table has a working CSV download whose row count equals the visible data; study header counts match the database.
- **AC-54–57** Exported trial CSV has exactly the FR-54 columns in order; a study export ZIP contains the four named files; all CSVs parse with Python `csv` and pandas without warnings; timestamps end in `Z` or `+00:00`.
- **AC-NFR** mypy and `tsc --noEmit` pass clean; statistics unit tests pass; `docker compose up` from a clean clone with only `.env` copied from `.env.example` (plus SECRET_KEY/ADMIN vars) reaches a healthy `/health` within 2 minutes.

---

## 11. Out of Scope / Future Work

Simple (single-stimulus) RT task; vigilance/Go-No-Go variants; participant-facing results; email delivery and self-service password reset; OAuth/SSO; multi-lab tenancy; i18n (English only at launch); in-app hard deletion of participant data; native desktop client for sub-frame timing; variable refresh-rate compensation; practice-to-test automatic gating on accuracy.

---

## Appendix A — Decisions & Defaults

- **D-1 Participant codes are globally unique** (not per-study) so participant login needs no study selector. Stored uppercase; login is case-insensitive.
- **D-2 Lab trust model:** all researchers see all studies. Rationale: small lab, simpler permissions; `created_by` retained for attribution.
- **D-3 Set-password trust window:** anyone holding an unclaimed code can claim it. Accepted risk for lab use; mitigated by rate limiting (FR-6) and researcher password reset (FR-5). Codes avoid ambiguous characters.
- **D-4 Session order enforcement** (FR-20) is strict; researchers wanting parallel sessions create them as separate studies.
- **D-5 Premature responses restart the foreperiod** within the same trial (per Deary-Liewald software behavior) rather than aborting the trial; the count is preserved per trial.
- **D-6 Box remains until response/timeout** (no fixed stimulus duration), matching the Deary-Liewald task.
- **D-7 ITI is fixed** (default 500 ms), not random; randomness lives in the foreperiod.
- **D-8 Practice default is 3 trials** per the edited prompt (Deary-Liewald uses 8; researchers can change it).
- **D-9 IIV definitions:** within-session IIV = intra-individual SD of correct RTs (numerically identical to SD RT; surfaced separately because the dashboard treats it as a primary outcome); between-session IIV = SD of session mean RTs (requires ≥2 completed sessions). CoV = SD/mean at each level. Statistics computed on test block, latest attempt, raw and trimmed variants.
- **D-10 Outliers are flagged, never dropped**; trimmed statistics exclude flagged trials; raw statistics include them. Timeouts and invalid trials are excluded from RT statistics in both variants but counted.
- **D-11 Demographics `once` fields** are asked at the participant's first started session in the study and never again, stored with `session_id = NULL`.
- **D-12 Participants never see their results** — avoids motivation/reactivity confounds; completion screen is neutral.
- **D-13 Concurrent tabs** on one session are not actively prevented; idempotent upserts make the damage bounded. Documented for researchers.
- **D-14 Stack versions:** Python 3.12, FastAPI ≥0.110, SQLAlchemy 2.x, Pydantic v2, Alembic; React 18, TypeScript 5, Vite 5, Tailwind CSS, Recharts; nginx serving + proxy; bcrypt via `passlib`.
- **D-15 RNG:** `crypto.getRandomValues`-seeded PRNG (or Math.random) is acceptable for stimulus/foreperiod randomization; a test mode accepts a fixed seed for reproducible automated tests.
- **D-16 Time zones:** all storage UTC; researcher UI renders local time.
- **D-17 SQLite fallback** exists only for unit tests / no-Docker dev; JSONB columns degrade to JSON TEXT transparently via SQLAlchemy `JSON` type.
- **D-18 Hosting note:** Lovable/Bolt cannot host the FastAPI backend; public hosting targets are Railway/Render/Fly.io/Replit (§9.5).

*End of PRD.*


