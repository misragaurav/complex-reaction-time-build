# Modifications PRD (v1.1) — CRT Web Application

Generated from `04_Modifications_PRD_Prompt.md` against baseline `02_PRD.md`.
This document specifies MOD-1 through MOD-6 in full. It is a new version
(v2), not a feature flag: every feature described here is always present
once built. Any baseline requirement (FR-1…FR-57, AC-1…AC-57, AC-NFR) not
explicitly superseded below remains in force unchanged.

---

## 1. Scope statement

v2 adds, on top of the v1 application described by `02_PRD.md`:

1. **MOD-1 — Enlarged stimulus geometry.** Pure presentational change to the
   task-runner canvas and instructional/feedback text sizes. No data model,
   API, or behavioural change. Supersedes the pixel values in baseline §5.1
   only; all other §5 behaviour is unchanged.

2. **MOD-2 — Simple Reaction Time (SRT) task type.** A fourth task type
   (`SRT`, alongside `CRT2`/`CRT3`/`CRT4`) with a single stimulus position and
   a single mapped key (default `Space`). Reuses the existing trial state
   machine, sequencing, statistics, dashboard, and export pipeline unchanged.
   Extends the `task_type` CHECK constraints (studies, sessions), the
   frontend `TaskType` union, default key maps, and key-map validation
   (FR-39).

3. **MOD-3 — Fixed longitudinal protocol & session labelling.** Every study
   now has a fixed protocol shape: 1 onboarding session + N intervention
   pairs (pre/post), where N = `num_intervention_sessions`. New study-level
   config fields and new per-session label fields (`session_type`,
   `intervention_session_number`, `week_number`, `day_within_week`,
   `display_label`, `display_label_overridden`). A new "Generate protocol
   sessions" helper replaces ad-hoc session assignment as the primary
   participant-session-creation path (endpoint #15 remains available for
   ad-hoc/manual assignment; the new endpoint is additive).

4. **MOD-4 — Participant groups.** Studies may define named groups.
   Participants belong to at most one group, assigned once (immutable).
   Adds `groups` and `participant_group_assignments` tables, group CRUD +
   assignment API, a new "Groups" tab on the study dashboard, and a
   `group_name` column on every CSV export.

5. **MOD-5 — Researcher-controlled session activation (gating).** Adds
   `activated` and `expired` to the session status enum. Participants can
   only start a session that is `activated`. Adds group-level and
   single-session activate/deactivate endpoints, new transition rules, three
   new session columns (`activated_at`, `expired_at`, `activated_by`), and
   new "My sessions" UI states (Locked / Ready / In progress / Done /
   Missed).

6. **MOD-6 — Interaction description.** Normative walkthrough showing how
   MOD-3 (labelling), MOD-4 (groups), and MOD-5 (activation) operate together
   in a typical researcher session-opening workflow. Introduces no new
   fields/endpoints beyond the requirement that `POST /groups/{id}/activate`
   responses include each activated session's `display_label`.

### What is explicitly unchanged

- Authentication, JWT/refresh, rate limiting, user management (FR-1…FR-8).
- Demographic fields and responses (FR-12…FR-15).
- Trial state machine timing, sequencing RNG, premature/timeout/invalid
  handling (FR-24…FR-35), except that SRT participates in it per MOD-2.
- Device gating (FR-44…FR-46).
- Statistics formulas (FR-47…FR-49).
- Dashboard charts (FR-50…FR-53) other than the new Groups tab and
  `Record<SessionStatus, …>` / `Record<TaskType, …>` exhaustiveness updates
  required by MOD-2/MOD-5.
- CSV column sets and ordering (FR-54…FR-57) other than the additional
  `group_name` column (MOD-4).
- `GET /health`, preview mode (FR-33), export ZIP contents.

Every baseline FR/AC not named above or in the MFR list (§4) applies as
written in `02_PRD.md`.

---

## 2. Modified / new user flows

### 2.1 Researcher flow — study creation (modified, MOD-2 + MOD-3)

1. Researcher opens **Studies → Create study**.
2. Fills name, description, **task type** — dropdown now offers `SRT`,
   `CRT2`, `CRT3`, `CRT4` (MOD-2).
3. Fills new **protocol configuration** fields: `num_intervention_sessions`
   (default 24), `sessions_per_week` (default 3), `task_type_onboarding`,
   `task_type_pre`, `task_type_post` (each default `CRT4`, each one of
   `SRT`/`CRT2`/`CRT3`/`CRT4`) (MOD-3).
4. Client validates `num_intervention_sessions % sessions_per_week === 0`
   before submit; server re-validates and returns 422 with message
   `"num_intervention_sessions must be a multiple of sessions_per_week"` if
   not.
5. Study created with these fields persisted; `params` defaults as before
   (FR-9).

### 2.2 Researcher flow — protocol generation (new, MOD-3)

1. Researcher adds participants as before (FR-16).
2. On the **Participants** tab, researcher clicks **Generate protocol
   sessions**.
3. Dialog shows: number of intervention sessions to generate (pre-filled
   from study's `num_intervention_sessions`), week start (default 1), and the
   three task-type fields (`task_type_onboarding`, `task_type_pre`,
   `task_type_post`) pre-filled from study config but editable for this
   generation run.
4. Researcher selects which participants to generate for (default: all
   without a protocol yet) and clicks **Generate**.
5. Server creates, per selected participant, `1 + 2N` sessions
   (`session_type` = onboarding/pre/post, `order_index` per §5 formula in
   MFR-17, `task_type` snapshot from the dialog's task-type fields,
   `display_label` auto-computed) in `created` status.
6. **Idempotent**: participants who already have any generated-protocol
   sessions are skipped; response reports `{created: [...], skipped: [...]}`
   with a per-participant skip count.
7. Researcher may edit any session's `display_label` afterwards from the
   Sessions tab (sets `display_label_overridden = true`).

### 2.3 Researcher flow — group management (new, MOD-4)

1. Researcher opens the new **Groups** tab on a study.
2. Clicks **Create group**, enters `name` (required, unique within study) and
   optional `description` (≤200 chars).
3. On **Participants** tab, researcher selects one or more unassigned
   participants via checkboxes, picks a group from a dropdown, clicks
   **Assign to group**. Each participant row always shows its group name or
   "Unassigned".
4. Attempting to assign an already-assigned participant returns 409
   (`"Participant {code} is already assigned to group {name}. Assignments
   cannot be changed."`); the UI surfaces this per-participant without
   aborting assignment of the other selected participants when the API is
   called per-batch (see MFR-24 for exact batch semantics).
5. Groups tab lists each group's size, `current_intervention_session`, and
   member codes. A soft warning ("Groups are recommended to have 4–6
   participants.") is shown for groups with <4 or >6 members — never
   blocking.
6. Researcher can increment `current_intervention_session` with a **+1**
   button, or edit it directly as a number, on the group detail panel. This
   value is purely informational (MFR-23).

### 2.4 Researcher flow — session activation (new, MOD-5)

1. On a group's detail panel, researcher sees an **Open session / Close
   session** toggle.
2. Clicking **Open session** calls `POST /groups/{id}/activate`. Response
   lists, per participant, the session that was activated (including its
   `display_label`); UI shows a confirmation summary, e.g. "You are opening:
   Week 2 · Day 2 · Pre for 4 participants."
3. If any group member already has a session `activated` or `in_progress`,
   the call is rejected (409) and the UI shows which participants/sessions
   are blocking.
4. While a session is open, the panel shows elapsed time since
   `activated_at` and a live count of members in `activated` / `in_progress`
   / `completed` for the open session.
5. Clicking **Close session** calls `POST /groups/{id}/deactivate`. If any
   member's session is still `activated` (not started), the UI shows the
   confirmation dialog from MFR-32 and, on confirm, resends with
   `{force: true}`.
6. Sessions tab and group detail panel also expose **Activate** / **Deactivate**
   buttons per individual session (`POST /sessions/{id}/activate` /
   `POST /sessions/{id}/deactivate}`) for one-off overrides (e.g.
   re-activating an `expired` session for a participant who missed it).

### 2.5 Participant flow — "My sessions" (modified, MOD-3 + MOD-5)

1. Participant logs in, lands on **My sessions**.
2. Each row shows: `display_label` (prominent), a colour-coded session-type
   chip (`onboarding`=grey, `pre`=blue, `post`=green), and a status
   presentation per the table in MFR-35:
   - `created` → "Locked 🔒", greyed out, no button.
   - `activated` → "Ready ▶", green highlight, **Start** button.
   - `in_progress` → "In progress →", **Resume** button.
   - `completed` → "Done ✔", greyed out.
   - `expired` → "Missed ✗", muted red, no button.
   - `cancelled` → hidden from the list entirely.
3. Clicking **Start** on an `activated` session calls `POST
   /sessions/{id}/start` as before; calling it on a non-`activated` session
   (only reachable via direct API misuse, since the UI hides the button)
   returns 403 with body `{"detail": "Session not open. Ask your researcher
   to open this session."}`, shown verbatim if surfaced.
4. All other task-runner behaviour (demographics, instructions, practice,
   test, completion) is unchanged, except MOD-1 geometry and MOD-2 SRT
   support.

---

## 3. Modified / new screen inventory (delta vs §3.4 baseline)

Only screens with changes are listed. All other §3.4 rows are unchanged.

| Route | Screen | Change |
|---|---|---|
| `/me` | Participant session list ("My sessions") | MOD-3: shows `display_label` + session-type chip per row. MOD-5: status presentation extended to 6 states (Locked/Ready/In progress/Done/Missed/hidden) per MFR-35; `cancelled` rows omitted. |
| `/run/:sessionId` | Task runner | MOD-1: stimulus geometry, feedback text size, key-cap legend styling per MFR-1…MFR-4. MOD-2: renders correctly for `task_type='SRT'` via existing `key_map.length`-driven layout (no structural change). |
| `/studies` | Studies list + create | MOD-2: task-type selector includes `SRT`. MOD-3: create form gains `num_intervention_sessions`, `sessions_per_week`, `task_type_onboarding`, `task_type_pre`, `task_type_post` fields with client-side multiple-of validation. |
| `/studies/:id` (Settings tab) | Study settings | MOD-2: task-type label map includes `SRT`. MOD-3: protocol config fields editable here post-creation (same multiple-of validation; see MFR-12 for lock timing). |
| `/studies/:id` (Participants tab) | Participants | MOD-3: new **Generate protocol sessions** button + dialog. MOD-4: checkboxes, group dropdown, **Assign to group** button, "Group" column showing group name or "Unassigned". |
| `/studies/:id` (Sessions tab) | Sessions | MOD-2: task-type label map includes `SRT`. MOD-3: new `display_label` and session-type columns. MOD-5: status label/badge maps extended for `activated`/`expired`; new `activated_at`/`expired_at` columns; per-row **Activate**/**Deactivate** buttons. |
| `/studies/:id` (Dashboard tab) | Dashboard | MOD-2: `TASK_TYPE_LABELS` includes `SRT`. MOD-5: `STATUS_LABELS`/status-keyed maps extended for `activated`/`expired` (exhaustiveness only — these statuses are rare in completed-session charts but the maps must type-check and render sensibly, e.g. grouped with `created` as "not yet run"). |
| `/studies/:id` (**new** Groups tab) | Groups | **New** (MOD-4): tab added to `TABS`. Lists groups (name, size, `current_intervention_session`, member codes, soft-warning badge if size <4 or >6). Create-group form. Group detail panel: member list with per-member session statuses, `current_intervention_session` +1/edit control, Open/Close session toggle (MOD-5), per-session Activate/Deactivate overrides. |
| `/studies/:id/preview` | Task preview | No change — `nPositions = params.key_map.length` already handles SRT (1 position). |

---

## 4. Functional requirements (MFR-N)

Numbered MFR-1…MFR-37, a namespace separate from baseline FR-1…FR-57. Where
an MFR supersedes a baseline FR, this is stated explicitly; otherwise the
MFR is additive and the baseline FRs remain in force unchanged.

### MOD-1 — Geometry (MFR-1…MFR-4)

**MFR-1 — Stimulus geometry constants.** Supersedes the pixel values of
baseline §5.1 (visual layout). `frontend/src/task/TaskCanvas.tsx` constants
change as follows:

| Element | v1 value | v2 value |
|---|---|---|
| Stimulus container | 96×96 px | **128×128 px** |
| Cross arm length (total) | 56 px (28 px per side) | **80 px (40 px per side)** |
| Gap between containers | 48 px | **64 px** |
| Box stimulus | 64×64 px | **88×88 px** |
| Stroke width (cross & box) | 6 px | **8 px** |

All other §5.1 properties (colours, container shape/border, layout
direction) are unchanged.

**MFR-2 — Minimum instructional/feedback text size.** All instructional and
feedback text in the task runner — instructions screen, practice feedback,
interstitial screen, and completion screen — renders at a minimum of **20
px** (Tailwind `text-xl` or larger). Applies to `TaskRunnerPage.tsx` and
`StudyPreviewPage.tsx`; any body/paragraph text currently below 20px (e.g.
`text-base`/`text-sm`) is bumped to `text-xl`. Headings already ≥20px are
unchanged.

**MFR-3 — Unified feedback text size.** In `TaskCanvas.tsx`, the three
feedback strings (`"✗"` for `incorrect`, `"Too soon!"` for premature/foreperiod
violation, `"Too slow"` for `timeout`) all render at **40 px** (previously
48px for `incorrect`, 32px for `timeout`/`too_soon`).

**MFR-4 — Key-cap legend styling.** `KeyMappingDiagram`'s key labels render
at **18 px**, monospace font, with a 1px border, 4px padding, and 4px
border-radius (a "key-cap" appearance). Layout (gap/positioning) driven by
the updated `GAP` constant from MFR-1.

### MOD-2 — Simple Reaction Time task (MFR-5…MFR-10)

**MFR-5 — SRT task type (schema and type system).** Supersedes the
`task_type` CHECK constraint values in §7 for `studies` and `sessions`
(all other columns of both tables unchanged):

- `studies.task_type` and `sessions.task_type` CHECK constraints extended to
  `('SRT','CRT2','CRT3','CRT4')`.
- Backend `TaskType` Literal/Enum gains `SRT`.
- Frontend `TaskType` union (`frontend/src/api/types.ts`) gains `"SRT"`.
- Every `Record<TaskType, …>` exhaustive map gains an `SRT` entry, including
  (at minimum) `TASK_TYPE_LABELS` in `StudiesListPage.tsx`,
  `StudySettingsTab.tsx`, `StudySessionsTab.tsx`, and `MySessionsPage.tsx` —
  label `"Simple reaction time"`.

**MFR-6 — SRT visual layout and default key map.** Single stimulus
container, centred, using the same per-container geometry as MFR-1
(`TASK_POSITIONS.SRT = 1`). Default response key is `Space`
(`KeyboardEvent.code === "Space"`):

- `DEFAULT_KEY_MAPS.SRT = ["Space"]`
- `KEY_LABELS.Space = "Space"`
- `ALLOWED_KEY_CODES` gains `"Space"`
- Backend `task_defaults.py` SRT defaults: `key_map=["Space"]`, all other
  §5.4 parameters (foreperiod range, response timeout,
  `max_consecutive_repeats`, practice/test trial counts, etc.) identical to
  the existing baseline defaults.

**MFR-7 — SRT trial structure (state-machine reuse).** SRT trials use the
**identical** state machine to baseline §5.5 (ITI → foreperiod → stimulus →
response/timeout → feedback); no changes to `trialEngine.ts`,
`sessionRunner.ts`, or `sequence.ts`.

- `stimulus_position` is always `0` (the only position). `sequence.ts`'s
  `drawPosition(rng, 1, …)` already returns `0` unconditionally for n=1.
- `response_position` is `0` for a valid keypress of the single mapped key,
  `null` for `timeout`/`invalid`.
- With exactly one mapped key, `outcome='incorrect'` is **structurally
  impossible**: any keydown matching the mapped key resolves the trial as
  `correct`. Any other key during the response window increments
  `extraneous_keys` only and does not resolve the trial. `timeout` and
  `invalid` (premature response, fullscreen exit, etc.) behave exactly as in
  §5.5/§5.6.
- `params.max_consecutive_repeats` is accepted and stored for SRT studies
  but has **no effect** on trial-sequence generation (vacuous when N=1,
  since every trial necessarily repeats position 0). No code branch is
  required beyond `sequence.ts`'s existing behaviour; document as "ignored
  for SRT" in `task_defaults.py`.

**MFR-8 — SRT key-map cardinality validation.** For `task_type='SRT'`,
`params.key_map` MUST contain **exactly 1** entry. Creating or updating a
study/session/preview/protocol-generation payload with `task_type='SRT'` and
`len(key_map) != 1` → **422**. Extends FR-39 (the existing no-duplicate-codes
rule continues to apply; this is an additional SRT-specific cardinality
rule). Enforced wherever `task_type`+`params` are validated together: study
create/update (#8/#9), session override (#15), protocol generation
(MFR-18), preview (#32).

**MFR-9 — SRT statistics, dashboard, export reuse.** FR-47…FR-49 statistics
are computed identically for `task_type='SRT'` sessions; no new fields, no
SRT-specific branches. Accuracy will be ~100% for any session containing at
least one non-`timeout`/non-`invalid` trial (since `incorrect` cannot occur
for SRT). Dashboard (FR-50…FR-53) and export (FR-54…FR-57) require zero new
columns or views for SRT — the existing `task_type` column identifies these
rows.

**MFR-10 — SRT instructions copy.** Instructions screen uses the existing
§5.3 template with `{N}=1` and `{KEYS}` = the single key's label (e.g.
`"Space"`). If the current template in
`frontend/src/task/instructions.ts` assumes `N≥2` (e.g. pluralised "one of
[...]" phrasing), add a singular-N (`N===1`) phrasing branch — e.g. "Press
**Space** as quickly as you can when you see the box." — so SRT instructions
read grammatically.

### MOD-3 — Session labelling and protocol structure (MFR-11…MFR-19)

**MFR-11 — Study-level protocol configuration fields.** New columns on
`studies`:

| Field | Type | Default | Constraints |
|---|---|---|---|
| `num_intervention_sessions` | INT NOT NULL | 24 | 1–156 |
| `sessions_per_week` | INT NOT NULL | 3 | 1–7 |
| `task_type_onboarding` | TEXT NOT NULL (CHECK) | `'CRT4'` | one of `SRT,CRT2,CRT3,CRT4` |
| `task_type_pre` | TEXT NOT NULL (CHECK) | `'CRT4'` | one of `SRT,CRT2,CRT3,CRT4` |
| `task_type_post` | TEXT NOT NULL (CHECK) | `'CRT4'` | one of `SRT,CRT2,CRT3,CRT4` |

Settable at study creation (#8 request body gains these as optional fields,
server-defaulted as above); editable via #9 subject to MFR-12.

**MFR-12 — Multiple-of validation and post-generation lock.**
`num_intervention_sessions % sessions_per_week == 0` is enforced on create
(#8) and update (#9): **422** `"num_intervention_sessions must be a multiple
of sessions_per_week"` otherwise. Once any session with non-null
`session_type` exists for the study (i.e. the protocol has been generated at
least once), `num_intervention_sessions`, `sessions_per_week`,
`task_type_onboarding`, `task_type_pre`, and `task_type_post` become
**read-only** via #9 — **422** `"protocol configuration is locked after
sessions have been generated"`. The study-settings UI renders these fields
read-only with an explanatory note once locked.

**MFR-13 — Protocol shape.** Every study's protocol = 1 onboarding session
(`session_type='onboarding'`) + N intervention pairs (N =
`num_intervention_sessions`), each pair = 1 `pre` + 1 `post`. Total sessions
per participant after generation = **1 + 2N** (49 for N=24). This is
additive structure on top of FR-16/FR-18 (manual participant/session
assignment), which remain available for sessions outside the generated
protocol.

**MFR-14 — Session label fields (schema).** New columns on `sessions`:

| Field | Type | Nullability | Notes |
|---|---|---|---|
| `session_type` | TEXT CHECK IN ('onboarding','pre','post') | NOT NULL | set at creation |
| `intervention_session_number` | INT (1–156) | NULL for onboarding; NOT NULL for pre/post | which intervention pair (1..N) |
| `week_number` | INT (1–52) | NULL for onboarding | auto-computed (MFR-15) |
| `day_within_week` | INT (1–7) | NULL for onboarding | auto-computed (MFR-15) |
| `display_label` | TEXT (≤80 chars) | NOT NULL | auto-computed (MFR-16), researcher-overridable |
| `display_label_overridden` | BOOL NOT NULL DEFAULT false | | true once researcher manually sets `display_label` |

`display_label` is researcher-editable only while `status IN ('created',
'expired')` (i.e. before/after activation but not while
`activated`/`in_progress`/`completed`) — **409** `"display_label cannot be
changed once a session has been activated"` otherwise. `session_type`,
`intervention_session_number`, `week_number`, `day_within_week`,
`order_index` are immutable after creation (set only by protocol
generation).

**MFR-15 — week_number / day_within_week computation.** For a session with
`intervention_session_number = k` and the study's `sessions_per_week = s`:

```
week_number     = ceil(k / s)
day_within_week = ((k - 1) mod s) + 1
```

Both `NULL` for onboarding. Computed once at protocol-generation time using
the study's `sessions_per_week` at that time (immutable thereafter per
MFR-14/MFR-12). Worked table for `sessions_per_week=3`:

| k (intervention_session_number) | week_number | day_within_week |
|---|---|---|
| 1 | 1 | 1 |
| 2 | 1 | 2 |
| 3 | 1 | 3 |
| 4 | 2 | 1 |
| 5 | 2 | 2 |
| 6 | 2 | 3 |
| 24 | 8 | 3 |

**MFR-16 — display_label computation and override semantics.** At
protocol-generation time:

- Onboarding → `"Onboarding"`
- Pre (k) → `"Week {week_number} · Day {day_within_week} · Pre"`
- Post (k) → `"Week {week_number} · Day {day_within_week} · Post"`

`display_label_overridden` starts `false`. If the researcher edits
`display_label` directly (subject to MFR-14's status gate), the server sets
`display_label_overridden=true` and stores the literal value verbatim (≤80
chars, **422** if longer). An overridden label is never recomputed or
overwritten by any later operation. (Since `intervention_session_number`,
`week_number`, `day_within_week` are immutable post-creation per MFR-14,
there is no other trigger for recomputation; `display_label_overridden`
exists purely to record provenance for the UI and for MAC testing.)

**MFR-17 — order_index formula.** For onboarding: `order_index = 1`. For
intervention pair k (1..N): Pre → `order_index = 2k`, Post → `order_index =
2k+1`. Maximum `order_index = 2N+1`. FR-20's strict in-order-completion rule
applies unchanged across this full sequence.

**MFR-18 — Protocol generation endpoint + UI.** New endpoint `POST
/studies/{id}/generate-protocol`:

- Request: `{participant_ids?: [uuid,...], num_intervention_sessions?: int,
  week_start?: int, task_type_onboarding?: TaskType, task_type_pre?:
  TaskType, task_type_post?: TaskType}`. All fields optional;
  `participant_ids` defaults to all active participants of the study that do
  not yet have a generated protocol; the four other fields default to the
  study's corresponding columns (MFR-11).
- For each selected participant: if the participant already has ANY session
  with non-null `session_type`, skip (record in `skipped`). Otherwise create
  `1+2N` sessions per MFR-13…MFR-17 with `task_type` snapshotted from the
  relevant `task_type_onboarding`/`task_type_pre`/`task_type_post` value,
  `params` snapshotted from the study's current `params` (existing FR-18
  semantics), `status='created'`.
- `week_start` (default `1`) offsets every computed `week_number`:
  `week_number = week_start - 1 + ceil(k/s)`. Default `week_start=1`
  reproduces MFR-15 exactly.
- MFR-8 (SRT key-map cardinality) is validated against each of the three
  task-type/params combinations before any session is created; **422** with
  no sessions created if any combination is invalid.
- Response: `{created: [{participant_id, code, session_count}], skipped:
  [{participant_id, code, reason: "already_generated"}]}`.
- UI: "Generate protocol sessions" button on the Participants tab opens a
  dialog pre-filled with the study's `num_intervention_sessions`, `week_start
  = 1`, and the three `task_type_*` fields (all editable for this run);
  researcher selects participants (default: all without a protocol) and
  clicks **Generate**. On success, shows created/skipped counts.

**MFR-19 — Participant-facing display_label and chips.** `GET /me/sessions`
(#19) response items gain `session_type` and `display_label` (both already
columns on `sessions` per MFR-14). "My sessions" (`/me`) renders
`display_label` as each row's primary label, with a colour-coded chip for
`session_type`: `onboarding`=grey, `pre`=blue, `post`=green.

### MOD-4 — Participant groups (MFR-20…MFR-27)

**MFR-20 — `groups` table.**

```text
groups
  id UUID PK | study_id UUID FK->studies NOT NULL
  name TEXT NOT NULL              -- UNIQUE within study_id
  description TEXT NULL           -- <=200 chars
  current_intervention_session INT NULL  -- 1-52, manual researcher counter
  created_at TIMESTAMPTZ NOT NULL
  UNIQUE (study_id, name)
```

**MFR-21 — `participant_group_assignments` table.**

```text
participant_group_assignments
  id UUID PK
  participant_id UUID UNIQUE FK->participants NOT NULL  -- one group per participant, ever
  group_id UUID FK->groups NOT NULL
  assigned_at TIMESTAMPTZ NOT NULL
```

The `UNIQUE` constraint on `participant_id` enforces one-group-per-participant
at the database level (defence in depth alongside the API-level 409 in
MFR-24). Assignments are immutable: no update/delete path exists in the API
(MFR-27) for this table beyond the initial insert via `assign`.

**MFR-22 — Group size guidance.** UI-only, non-blocking. The Groups tab and
group detail panel show the text "Groups are recommended to have 4–6
participants." whenever a group's member count is `<4` or `>6` (including
`0`). Never prevents group creation, assignment, or any other action.

**MFR-23 — `current_intervention_session` counter.**
`groups.current_intervention_session` (INT NULL, 1–52), researcher-managed
via `PATCH /groups/{id}` `{current_intervention_session: int|null}`. Has
**no effect** on session gating, activation eligibility (MOD-5), data
export, or task execution — purely an at-a-glance indicator. UI provides a
**+1** button (increments by 1, clamped at 52 — no-op/disabled at 52) and
direct numeric entry (1–52 or empty/null).

**MFR-24 — Assignment workflow.** `POST /groups/{id}/assign`
`{participant_ids: [uuid,...]}`:

- For each `participant_id`: if the participant already has a row in
  `participant_group_assignments` (to any group, including this one), it is
  reported in `conflicts` (`{participant_id, code, current_group_name}`) and
  NOT reassigned. Otherwise, create an assignment to this group.
- If `conflicts` is non-empty and `assigned` is empty (every requested
  participant was already assigned — the single-participant-reassignment
  case), the endpoint returns **409** `{"detail": "Participant {code} is
  already assigned to group {current_group_name}. Assignments cannot be
  changed.", "conflicts": [...]}`.
- If at least one participant was newly assigned, the endpoint returns
  **200** `{"assigned": [{participant_id, code}], "conflicts": [...]}` (a
  multi-select batch is not all-or-nothing blocked by one already-assigned
  participant).
- UI (Participants tab): checkboxes per participant row + a group-selection
  dropdown + **Assign to group** button. Each row always shows the
  participant's `group_name` or "Unassigned". Conflicts are surfaced inline
  without blocking the rest of the batch.

**MFR-25 — Groups dashboard tab.** New "Groups" tab on `/studies/:id`
(`TABS` gains `"groups"`). Shows, per group: `name`, `description`, member
count (+ MFR-22 badge if applicable), `current_intervention_session` (with
+1/edit control), and member list (participant codes, each with current
session status). Also shows per-group session completion counts:
completed-pre / completed-post / total-assigned — both for the group's
`current_intervention_session` (if set; counts sessions with that
`intervention_session_number`) and overall (across all sessions). The group
detail panel additionally hosts the MOD-5 Open/Close session toggle
(MFR-36).

**MFR-26 — `group_name` in CSV exports.** Extends FR-54…FR-57: every CSV
export (trial-level — endpoints #28/#29 and the four files inside the #30
ZIP — and any session/participant summary CSV) gains a trailing
`group_name` column, appended after all previously-specified columns (so
existing column order/positions are unchanged). Value = the participant's
assigned group's `name`, or `""` (empty string) if unassigned.

**MFR-27 — Groups API endpoints.**

| Endpoint | Auth | Behaviour |
|---|---|---|
| `GET /studies/{id}/groups` | A,R | List groups for the study with member counts and `current_intervention_session`. |
| `POST /studies/{id}/groups` | A,R | `{name, description?}` → group. **409** if `name` not unique within the study. |
| `GET /groups/{id}` | A,R | Group detail: all group fields + full member list (`participant_id`, `code`, current session status per member). |
| `PATCH /groups/{id}` | A,R | `{name?, description?, current_intervention_session?}` → updated group. **409** on duplicate `name` within study. |
| `DELETE /groups/{id}` | A,R | **204** if zero participants assigned; else **409** `"Group has assigned participants and cannot be deleted."` |
| `POST /groups/{id}/assign` | A,R | Per MFR-24. |

### MOD-5 — Researcher-controlled session activation (MFR-28…MFR-36)

**MFR-28 — Session status enum extension.** Supersedes the `status` enum
portion of FR-19 / §7 `sessions.status` (all other columns/constraints of
`sessions` unchanged by this MFR). `sessions.status` CHECK constraint
extended from `('created','in_progress','completed','abandoned',
'cancelled')` to:

```text
('created','activated','in_progress','completed','abandoned','expired','cancelled')
```

**MFR-29 — Full status state machine.** Supersedes FR-19 (status enum) and
the transition portion of FR-21 (lazy abandonment, FR-21's 30-minute rule
itself is unchanged and is listed below for completeness).

| From | To | Trigger | Actor |
|---|---|---|---|
| `created` | `activated` | group activate (MFR-31) or single-session activate (MFR-33) | researcher |
| `created` | `cancelled` | cancel (FR-23, unchanged) | researcher |
| `activated` | `in_progress` | `POST /sessions/{id}/start` (MFR-34) | participant |
| `activated` | `expired` | group deactivate (MFR-32) or single-session deactivate (MFR-33) | researcher |
| `activated` | `cancelled` | cancel (FR-23, unchanged) | researcher |
| `expired` | `activated` | re-activation — group activate (MFR-31) or single-session activate (MFR-33) | researcher |
| `expired` | `cancelled` | cancel (FR-23, unchanged) | researcher |
| `in_progress` | `completed` | `POST /sessions/{id}/complete` (unchanged) | participant |
| `in_progress` | `abandoned` | 30-min inactivity, lazy (FR-21, unchanged) | server |

`completed`, `abandoned`, and `cancelled` are terminal — no outgoing
transitions (consistent with existing FR-21/FR-23 terminality). `in_progress`
and `completed` sessions can never be activated, deactivated, or cancelled.

**MFR-30 — `sessions` table additions.**

```text
activated_at  TIMESTAMPTZ NULL
expired_at    TIMESTAMPTZ NULL
activated_by  UUID NULL FK->users
```

`activated_at` and `activated_by` are (re)set on every `→activated`
transition (including `expired→activated` re-activation, overwriting prior
values). `expired_at` is set on every `→expired` transition.

**MFR-31 — `POST /groups/{id}/activate`.**

1. **Pre-condition (409):** before any transition, if ANY participant in the
   group currently has a session with `status IN ('activated',
   'in_progress')` in this study, reject the ENTIRE request with **409**
   `{"detail": "...", "blocking": [{participant_id, code, session_id,
   status, display_label}]}`. No transitions are performed.
2. For each non-`cancelled`, non-fully-`completed` participant in the group,
   find the next-due session = lowest `order_index` among that
   participant's sessions with `status IN ('created','expired')`.
3. If no such session exists for a participant (all sessions
   `completed`/`cancelled`), skip that participant silently — not an error.
4. Transition each found session `created|expired → activated`; set
   `activated_at=now()`, `activated_by=<acting researcher's user id>`.
5. Response: `{activated: [{participant_id, code, session_id,
   display_label, session_type, order_index}]}`. Per MOD-6 (MFR-37),
   `display_label` MUST be present on every activated entry.

**MFR-32 — `POST /groups/{id}/deactivate`.** Request: `{force?: bool =
false}`.

1. Find all group members' sessions with `status='activated'`.
2. If that count is `>0` and `force` is not `true`: return **409**
   `{"detail": "...", "not_started_count": n, "sessions": [{participant_id,
   code, session_id, display_label}]}`. No transitions performed.
3. If count is `0`, or `force=true`: transition all such `activated`
   sessions → `expired`, set `expired_at=now()`.
4. `in_progress` sessions are never touched by this endpoint — they run to
   `completed`/`abandoned` normally.
5. Response: `{expired: [{participant_id, code, session_id, display_label}],
   in_progress_count: n}`.

UI confirmation dialog (shown when step 2 returns 409, before resending with
`force:true`): *"N participant(s) have not yet started this session. Their
session will be marked Missed and can be re-opened individually. In-progress
sessions will not be interrupted. Continue?"*

**MFR-33 — Single-session activate/deactivate endpoints.**

| Endpoint | Auth | Behaviour |
|---|---|---|
| `POST /sessions/{id}/activate` | A,R | Session must be `created` or `expired`, else **409**. **409** if the owning participant has ANY OTHER session `activated`/`in_progress` in the study. On success: `created\|expired → activated`, sets `activated_at`/`activated_by`. Returns the updated session (incl. `display_label`). |
| `POST /sessions/{id}/deactivate` | A,R | Session must be `activated`, else **409** (e.g. `in_progress` → 409). On success: `activated → expired`, sets `expired_at`. Returns the updated session. |

**MFR-34 — `POST /sessions/{id}/start` requires `activated`.** Modifies
endpoint #20. The precondition changes from "session is the participant's
next session in `order_index` order AND `status='created'`" to simply
**`status == 'activated'`**. The `order_index` ordering check (FR-20) is
subsumed: a session can only become `activated` via MFR-31 (which selects
the lowest-`order_index` eligible session per participant) or MFR-33 (an
explicit researcher override, deliberately allowed out of order).

- If `status != 'activated'`: **403** `{"detail": "Session not open. Ask
  your researcher to open this session."}` — this replaces the prior
  409-out-of-order response for this endpoint specifically, and is shown
  verbatim to the participant if surfaced.
- On success (`status=='activated'`): transition `activated → in_progress`,
  set `started_at=now()` on first start or increment `resume_count` on
  resume (unchanged FR-21 resume semantics). Response shape unchanged:
  `{params, task_type, attempt, demographics_due, stored_trials}`.

**MFR-35 — Participant "My sessions" UI states.**

| `status` | Display | Button |
|---|---|---|
| `created` | "Locked 🔒" (greyed out) | none |
| `activated` | "Ready ▶" (green highlight) | **Start** |
| `in_progress` | "In progress →" | **Resume** |
| `completed` | "Done ✔" (greyed out) | none |
| `expired` | "Missed ✗" (muted red) | none |
| `cancelled` | hidden from list | — |

`GET /me/sessions` (#19): the previous `locked` boolean (meaning "not next in
`order_index` order") is superseded as the UI's gating signal — the frontend
now derives its 6-state presentation directly from `status` per this table.
(`locked` may remain present in the response payload for shape continuity,
but MUST NOT be used to gate the Start/Resume button; `status` is
authoritative.)

**MFR-36 — Researcher UI: Open/Close session toggle.** The group detail
panel shows a single **Open session / Close session** toggle bound to
MFR-31/MFR-32 respectively. While any group member's relevant session is
`activated`/`in_progress` following an "Open", the panel shows elapsed time
since that activation round's `activated_at` and live counts of members
currently `activated` / `in_progress` / `completed` for that round. The
Sessions tab shows `activated_at` and `expired_at` (formatted timestamp or
"—") as columns on every row, plus per-row **Activate**/**Deactivate**
buttons (MFR-33), enabled/disabled per that MFR's status preconditions.

### MOD-6 — Interaction tie-together (MFR-37)

**MFR-37 — Group activation response surfaces `display_label`.** Restates
and is satisfied by MFR-31 item 5: `POST /groups/{id}/activate` responses
include `display_label` (and `session_type`, `order_index`) for every
activated session, enabling the researcher UI to confirm "You are opening:
{display_label} for {n} participants" — the explicit MOD-6 normative
requirement.

---

## 5. Data model delta

Format mirrors baseline §7. Only tables that change are repeated in full
(with new/changed lines marked `-- MOD-n`); `users`, `participants`,
`demographic_fields`, `demographic_responses`, and `trials` are unchanged
and not repeated.

```text
studies
  id UUID PK | name TEXT NOT NULL | description TEXT
  task_type TEXT CHECK (task_type IN ('SRT','CRT2','CRT3','CRT4'))   -- MOD-2: adds 'SRT'
  params JSONB NOT NULL            -- full §5.4 parameter set (study defaults)
  num_intervention_sessions INT NOT NULL DEFAULT 24  -- MOD-3, CHECK 1-156
  sessions_per_week INT NOT NULL DEFAULT 3           -- MOD-3, CHECK 1-7
  task_type_onboarding TEXT NOT NULL DEFAULT 'CRT4'  -- MOD-3, CHECK IN ('SRT','CRT2','CRT3','CRT4')
  task_type_pre TEXT NOT NULL DEFAULT 'CRT4'         -- MOD-3, CHECK IN ('SRT','CRT2','CRT3','CRT4')
  task_type_post TEXT NOT NULL DEFAULT 'CRT4'        -- MOD-3, CHECK IN ('SRT','CRT2','CRT3','CRT4')
  created_by UUID FK->users | is_archived BOOL DEFAULT false
  created_at | updated_at
  CHECK (num_intervention_sessions % sessions_per_week = 0)  -- MOD-3 (DB-level best-effort; API is authoritative, see MFR-12)
```

```text
sessions
  id UUID PK | code TEXT UNIQUE NOT NULL | participant_id FK | study_id FK
  order_index INT NOT NULL         -- 1-based per participant
  task_type TEXT CHECK (task_type IN ('SRT','CRT2','CRT3','CRT4'))   -- MOD-2: adds 'SRT'
  params JSONB NOT NULL            -- immutable snapshot
  status TEXT CHECK (status IN ('created','activated','in_progress','completed','abandoned','expired','cancelled'))  -- MOD-5: adds 'activated','expired'
  attempt INT DEFAULT 1 | resume_count INT DEFAULT 0
  session_type TEXT NOT NULL CHECK (session_type IN ('onboarding','pre','post'))  -- MOD-3
  intervention_session_number INT NULL  -- MOD-3, CHECK 1-156, NULL iff session_type='onboarding'
  week_number INT NULL                  -- MOD-3, CHECK 1-52, NULL iff session_type='onboarding'
  day_within_week INT NULL              -- MOD-3, CHECK 1-7, NULL iff session_type='onboarding'
  display_label TEXT NOT NULL           -- MOD-3, CHECK length <= 80
  display_label_overridden BOOL NOT NULL DEFAULT false  -- MOD-3
  activated_at TIMESTAMPTZ NULL         -- MOD-5
  expired_at TIMESTAMPTZ NULL           -- MOD-5
  activated_by UUID NULL FK->users      -- MOD-5
  client_env JSONB NULL            -- FR-43 payload
  started_at NULL | completed_at NULL | last_activity_at NULL | created_at
  UNIQUE (participant_id, order_index)
  INDEX (study_id, session_type, intervention_session_number)  -- MOD-3: protocol-generation idempotency lookups
```

```text
groups                                                  -- MOD-4, new table
  id UUID PK | study_id UUID FK->studies NOT NULL
  name TEXT NOT NULL               -- UNIQUE within study_id
  description TEXT NULL            -- <=200 chars
  current_intervention_session INT NULL  -- CHECK 1-52; manual researcher counter, display-only (MFR-23)
  created_at TIMESTAMPTZ NOT NULL
  UNIQUE (study_id, name)
```

```text
participant_group_assignments                          -- MOD-4, new table
  id UUID PK
  participant_id UUID UNIQUE FK->participants NOT NULL  -- one group per participant, ever (MFR-21)
  group_id UUID FK->groups NOT NULL
  assigned_at TIMESTAMPTZ NOT NULL
  INDEX (group_id)  -- member-list queries
```

**New relationships:** studies 1-N groups; groups 1-N
participant_group_assignments; participants 0..1
participant_group_assignments (enforced by the UNIQUE constraint on
`participant_id`).

**Migrations** (dependency order, each implements `downgrade()`, none edits
an existing migration file):

| File | MOD | Changes |
|---|---|---|
| `0002_mod2_add_srt_task_type.py` | MOD-2 | Widen `studies.task_type` and `sessions.task_type` CHECK constraints to include `'SRT'`. |
| `0003_mod3_protocol_and_labels.py` | MOD-3 | Add `num_intervention_sessions`, `sessions_per_week`, `task_type_onboarding`, `task_type_pre`, `task_type_post` to `studies` (with defaults, backfilled for existing rows); add `session_type`, `intervention_session_number`, `week_number`, `day_within_week`, `display_label`, `display_label_overridden` to `sessions` (existing rows backfilled: `session_type='pre'`, `display_label=''` is invalid under the `NOT NULL`/length constraints — backfill existing rows with `session_type='pre'`, `intervention_session_number=order_index`, `week_number=1`, `day_within_week=order_index`, `display_label='Session ' || order_index`, `display_label_overridden=false`; see Decisions §10 for the backfill rationale). Add the `(study_id, session_type, intervention_session_number)` index. |
| `0004_mod4_groups.py` | MOD-4 | Create `groups` and `participant_group_assignments` tables with constraints/indexes above. |
| `0005_mod5_activation_gating.py` | MOD-5 | Widen `sessions.status` CHECK constraint to include `'activated'`,`'expired'`; add `activated_at`, `expired_at`, `activated_by` columns. |

---

## 6. API delta

Format mirrors baseline §8 (prefix `/api/v1`, JSON,
`Authorization: Bearer <JWT>`, roles A/R/P, errors `{"detail": "..."}`).
New endpoints continue numbering from #33. Modified existing endpoints are
listed with **Δ** and describe only the changed portion; everything else
about them is unchanged from baseline §8.

### 6.1 Modified existing endpoints

| # | Method & path | Δ |
|---|---|---|
| 8 | POST `/studies` | Request body gains optional MOD-3 fields: `num_intervention_sessions?, sessions_per_week?, task_type_onboarding?, task_type_pre?, task_type_post?` (defaults per MFR-11). `task_type` (incl. body's `params.key_map` if provided) validated against MFR-8 (SRT ⇒ `len(key_map)==1`) and the new CHECK values (MFR-5). **422** if `num_intervention_sessions % sessions_per_week != 0` (MFR-12). Response (`StudyOut`) includes the five new fields. |
| 9 | PATCH `/studies/{id}` | Same five fields editable, subject to MFR-12's multiple-of validation and post-generation lock (**422** `"protocol configuration is locked after sessions have been generated"`). `params.key_map` updates re-validated against MFR-8 for the study's `task_type` (and `task_type_onboarding/pre/post` if those are SRT). |
| 15 | POST `/studies/{id}/sessions` | `overrides.task_type='SRT'` ⇒ `overrides.params.key_map` (or the resulting effective key_map) must have length 1 (**422** otherwise, MFR-8). Created sessions get `session_type='pre'`-shaped defaults are NOT auto-applied here — this endpoint remains the manual/ad-hoc path (MFR-13); `session_type`/`intervention_session_number`/`week_number`/`day_within_week`/`display_label`/`display_label_overridden` are required columns, so this endpoint sets `session_type='pre'`, `intervention_session_number=NULL→`(not allowed, NOT NULL only for pre/post)... see Decisions §10.D1 for the exact defaulting rule used for non-protocol sessions created via this endpoint. |
| 19 | GET `/me/sessions` | Each item gains `session_type`, `display_label` (MFR-19), `activated_at`, `expired_at` (for UI display per MFR-36, read-only to participants). `locked` remains present but is no longer the Start/Resume gating signal — `status` is (MFR-35). |
| 20 | POST `/sessions/{id}/start` | Precondition changed to `status=='activated'` (was: next-in-order AND `status=='created'`). **403** `{"detail": "Session not open. Ask your researcher to open this session."}` if not `activated` (MFR-34, replacing the prior 409-out-of-order response for this endpoint). Success response shape unchanged. |
| 28 | GET `/sessions/{id}/export.csv` | Adds trailing `group_name` column (MFR-26). |
| 29 | GET `/participants/{id}/export.csv` | Adds trailing `group_name` column (MFR-26). |
| 30 | GET `/studies/{id}/export.zip` | All four CSV files inside gain a trailing `group_name` column (MFR-26). |

### 6.2 New endpoints

| # | Method & path | Auth | Request → Response |
|---|---|---|---|
| 33 | POST `/studies/{id}/generate-protocol` | A,R | `{participant_ids?:[uuid], num_intervention_sessions?:int, week_start?:int, task_type_onboarding?, task_type_pre?, task_type_post?}` → `{created:[{participant_id,code,session_count}], skipped:[{participant_id,code,reason}]}`. **422** on MFR-8 violation for any of the three task types (MFR-18). |
| 34 | GET `/studies/{id}/groups` | A,R | → `[{id,name,description,member_count,current_intervention_session,created_at}]` (MFR-27). |
| 35 | POST `/studies/{id}/groups` | A,R | `{name, description?}` → group. **409** if `name` not unique within study (MFR-20/MFR-27). |
| 36 | GET `/groups/{id}` | A,R | → `{id,study_id,name,description,current_intervention_session,created_at, members:[{participant_id,code,session_status_summary}]}` (MFR-27). |
| 37 | PATCH `/groups/{id}` | A,R | `{name?, description?, current_intervention_session?}` → group. **409** on duplicate `name` (MFR-23/MFR-27). |
| 38 | DELETE `/groups/{id}` | A,R | → **204** if no participants assigned; else **409** `"Group has assigned participants and cannot be deleted."` (MFR-27). |
| 39 | POST `/groups/{id}/assign` | A,R | `{participant_ids:[uuid]}` → `{assigned:[{participant_id,code}], conflicts:[{participant_id,code,current_group_name}]}`; **409** if all requested are conflicts (MFR-24). |
| 40 | POST `/groups/{id}/activate` | A,R | → `{activated:[{participant_id,code,session_id,display_label,session_type,order_index}]}`. **409** `{"detail":"...","blocking":[...]}` if any member already `activated`/`in_progress` (MFR-31/MFR-37). |
| 41 | POST `/groups/{id}/deactivate` | A,R | `{force?:bool=false}` → `{expired:[{participant_id,code,session_id,display_label}], in_progress_count:int}`. **409** `{"detail":"...","not_started_count":n,"sessions":[...]}` if `not_started_count>0` and `force` is false (MFR-32). |
| 42 | POST `/sessions/{id}/activate` | A,R | → updated session (incl. `display_label`). **409** if session not `created`/`expired`, or if owner has another `activated`/`in_progress` session in the study (MFR-33). |
| 43 | POST `/sessions/{id}/deactivate` | A,R | → updated session. **409** if session not `activated` (MFR-33). |

---

## 7. SRT task specification

Complete equivalent of baseline §5 for `task_type='SRT'`. Where this section
is silent, baseline §5 applies verbatim with `N` (number of stimulus
positions / key-map entries) `= 1`.

**7.1 Visual layout.** A single stimulus container, centred in the task area
(no other containers). Uses the same per-container geometry as MFR-1
(128×128 px container, 80px-total cross, 88×88 px box, 8px stroke). The `GAP`
constant (64px, MFR-1) is unused for SRT since there is only one container.
Trial visual sequence is identical to CRT: cross (fixation) → box (go
signal) appears in the single container.

**7.2 Key map.** `TASK_POSITIONS.SRT = 1`. Default `params.key_map =
["Space"]` (`KeyboardEvent.code === "Space"`, label `"Space"`). Configurable
via the existing FR-39 key-map editor, but constrained to **exactly 1**
entry for `task_type='SRT'` — **422** otherwise (MFR-8). The key-cap legend
(MFR-4) renders this single key below the stimulus container.

**7.3 Trial state machine — differences from CRT.** Identical ITI →
foreperiod → stimulus → response/timeout → feedback machine as baseline
§5.5 (`trialEngine.ts`/`sessionRunner.ts`/`sequence.ts` unchanged). Per-step
differences:

| Aspect | CRT (N≥2) | SRT (N=1) |
|---|---|---|
| `stimulus_position` | drawn from `{0..N-1}`, ≤3 consecutive repeats | always `0` |
| Valid response | key matching the position's mapped key → `correct`; any other mapped key → `incorrect` with `response_position` set | only one mapped key exists; pressing it → `correct`. `incorrect` is **structurally impossible** |
| `response_position` | 0..N-1 (correct or incorrect), or `null` (timeout/invalid) | `0` (correct) or `null` (timeout/invalid) |
| Unmapped keydown | `extraneous_keys += 1`, trial continues | identical: `extraneous_keys += 1`, trial continues |
| `max_consecutive_repeats` | enforced during sequence generation | accepted, stored, **ignored** (vacuous — every trial is necessarily position 0) |
| Timeout | `outcome='timeout'`, `rt_ms=null`, feedback "Too slow" (test/practice per §5.6) | identical |
| Premature (foreperiod) response | `premature_count += 1`, redraw foreperiod, practice shows "Too soon!" for 1000ms | identical |
| Invalid (fullscreen exit etc.) | `outcome='invalid'`, `invalid_reason` set, re-queued per §5.7 | identical |

**7.4 Instructions.** Uses the §5.3 template with `{N}=1`, `{KEYS}` = `"Space"`
(or the configured key's label). Singular phrasing per MFR-10 (e.g. "Press
**Space** as quickly as you can when the box appears.") rather than the
plural "press one of [...]" phrasing used for N≥2.

**7.5 Parameters (§5.4).** All parameters (foreperiod range, response
timeout, practice/test trial counts, `practice_feedback`,
`max_consecutive_repeats`, etc.) apply with the same defaults and the same
JSON shape as CRT. Only `max_consecutive_repeats` has no observable effect
(7.3).

**7.6 Timing.** Identical timing source and precision to CRT (the shared
`trialEngine.ts` uses the same `EngineClock`/RT-capture path) — no SRT-specific
timing notes; SRT exists specifically to allow apples-to-apples RT
comparison against CRT and a lab apparatus.

**7.7 Statistics, dashboard, export.** Per MFR-9: FR-47…FR-49 statistics,
FR-50…FR-53 dashboard, and FR-54…FR-57 export all apply unchanged;
`task_type='SRT'` in the existing column identifies these sessions. Expected
accuracy ≈100% on any session with ≥1 non-`timeout`/non-`invalid` trial.

---

## 8. Acceptance criteria (MAC-N)

One MAC per MFR (MAC-N ↔ MFR-N), each testable as written.

| MAC | Criterion |
|---|---|
| MAC-1 | `TaskCanvas.tsx` renders containers at 128×128px, cross arms at 40px/side (80px total), gap 64px, box 88×88px, stroke 8px — verified by inspection/snapshot of the rendered SVG/DOM geometry. |
| MAC-2 | Every instructional/feedback text element in `TaskRunnerPage.tsx` and `StudyPreviewPage.tsx` computes to ≥20px (Tailwind `text-xl`+). |
| MAC-3 | `TaskCanvas.tsx` renders `"✗"`, `"Too soon!"`, and `"Too slow"` all at 40px. |
| MAC-4 | `KeyMappingDiagram` key labels render at 18px, monospace, with a 1px border, 4px padding, 4px border-radius. |
| MAC-5 | A study/session can be created with `task_type='SRT'`; `GET` returns `task_type:'SRT'`; backend rejects `task_type` values outside `{SRT,CRT2,CRT3,CRT4}` with 422; `tsc --noEmit` passes with `SRT` added to every `Record<TaskType,…>`. |
| MAC-6 | For `task_type='SRT'` with default params, `key_map === ["Space"]`, `TASK_POSITIONS.SRT===1`; task runner renders exactly 1 stimulus container. |
| MAC-7 | pytest: a generated SRT trial sequence has `stimulus_position===0` for all trials regardless of `max_consecutive_repeats` value (including `1`); `response_position` is `0` for correct, `null` for timeout/invalid; no trial has `outcome='incorrect'`. |
| MAC-8 | pytest: creating/updating a study or session with `task_type='SRT'` and `key_map` of length 0 or ≥2 → **422**. |
| MAC-9 | `GET /sessions/{id}/summary` for an SRT session returns the same field shape as for CRT, with accuracy computed identically (no `incorrect` outcomes contribute). |
| MAC-10 | SRT instructions render grammatically for `N=1` (no "one of [...]" plural phrasing); copy includes the key label "Space" (or configured key). |
| MAC-11 | New study defaults to `num_intervention_sessions=24, sessions_per_week=3, task_type_onboarding=task_type_pre=task_type_post='CRT4'`; all five fields round-trip via create→get and update→get. |
| MAC-12 | pytest: create with `num_intervention_sessions=25, sessions_per_week=3` → 422; after `generate-protocol` has run once for the study, `PATCH /studies/{id}` with any of the five protocol fields → 422 "protocol configuration is locked...". |
| MAC-13 | For `num_intervention_sessions=24`, `generate-protocol` creates exactly 49 sessions per participant: 1 onboarding + 24 pre + 24 post. |
| MAC-14 | pytest: `display_label` editable via PATCH while `status IN ('created','expired')`; **409** while `status IN ('activated','in_progress','completed')`; `session_type`/`intervention_session_number`/`week_number`/`day_within_week`/`order_index` are rejected/ignored on PATCH (immutable). |
| MAC-15 | pytest: for `sessions_per_week ∈ {1,2,3,4,5,6,7}` and a range of `intervention_session_number` values, `week_number=ceil(k/s)` and `day_within_week=((k-1) mod s)+1` match hand-computed values (including the `s=3` table: k=1→(1,1), k=2→(1,2), k=3→(1,3), k=4→(2,1), k=5→(2,2), k=6→(2,3), k=24→(8,3)). |
| MAC-16 | pytest: generated `display_label` matches `"Onboarding"` / `"Week {w} · Day {d} · Pre"` / `"Week {w} · Day {d} · Post"`; after a manual `display_label` PATCH, `display_label_overridden=true` and the value persists unchanged across any subsequent read. |
| MAC-17 | pytest: generated `order_index` sequence is `1` (onboarding), then `2,3,4,5,...,2N,2N+1` (pre/post pairs for k=1..N) — i.e. pre(k)=2k, post(k)=2k+1; FR-20 ordering still enforced across the full sequence. |
| MAC-18 | pytest: `POST /studies/{id}/generate-protocol` creates `1+2N` sessions per selected participant; a second call for the same participants returns them all in `skipped` and creates zero new sessions; `week_start>1` shifts `week_number` by `week_start-1`. |
| MAC-19 | `GET /me/sessions` items include `session_type` and `display_label`; `/me` renders `display_label` as the primary label with a chip coloured grey/blue/green for onboarding/pre/post. |
| MAC-20 | `groups` table exists with `(study_id, name)` unique; `POST /studies/{id}/groups` creates a group; duplicate `name` within the same study → 409. |
| MAC-21 | pytest: a participant can be assigned to at most one group, enforced by the `participant_group_assignments.participant_id` UNIQUE constraint and by API-level 409 (overlaps MAC-24). |
| MAC-22 | Groups tab / group detail panel shows "Groups are recommended to have 4–6 participants." for groups with <4 or >6 members, and does not show it for groups with 4–6 members; no action is blocked by this. |
| MAC-23 | `PATCH /groups/{id} {current_intervention_session: 5}` round-trips via `GET`; `+1` button increments by 1 (clamped at 52); changing this value has no effect on any session's `status` or any other endpoint's behaviour. |
| MAC-24 | pytest: `POST /groups/{id}/assign` with a single already-assigned `participant_id` → 409 with the existing group's name in the message; a batch containing one new and one already-assigned participant → 200 with the new one in `assigned` and the other in `conflicts`. |
| MAC-25 | Groups tab shows, per group, name/description/member-count/`current_intervention_session`/member codes + statuses, and completed-pre/completed-post/total-assigned counts both for `current_intervention_session` and overall. |
| MAC-26 | pytest: `group_name` is the last column in `/sessions/{id}/export.csv`, `/participants/{id}/export.csv`, and all four files in `/studies/{id}/export.zip`; equals the assigned group's name or `""` for unassigned participants; all previously-specified columns retain their original order. |
| MAC-27 | pytest: full CRUD lifecycle — create group, get, patch (rename, dup-name→409), assign members, attempt delete with members→409, unassign is impossible by design (no endpoint), delete an empty group→204. |
| MAC-28 | `sessions.status` CHECK constraint accepts `'activated'` and `'expired'` in addition to the original five values; rejects any seventh value. |
| MAC-29 | pytest: every transition in the MFR-29 table succeeds when preconditions hold and is rejected (409/403 as appropriate) when attempted from a non-listed `(from,to)` pair — e.g. `created→in_progress` directly via `/start` → 403; `in_progress→activated` → 409/404 (no such endpoint path succeeds); `completed→cancelled` → 409 (per existing FR-23 terminality). |
| MAC-30 | `activated_at`/`activated_by`/`expired_at` are `null` on a freshly created session; populated correctly after activate/expire; `activated_at`/`activated_by` are overwritten (not appended) on `expired→activated` re-activation. |
| MAC-31 | pytest: `POST /groups/{id}/activate` activates exactly the lowest-`order_index` `created`/`expired` session per eligible member, sets `activated_at`/`activated_by`, and returns each with its `display_label`; if any member already has an `activated`/`in_progress` session, the entire call → 409 and no session changes. |
| MAC-32 | pytest: with ≥1 member `activated` (not started), `POST /groups/{id}/deactivate {force:false}` → 409 with `not_started_count`; `{force:true}` → those sessions become `expired` with `expired_at` set; any `in_progress` member sessions are untouched and remain `in_progress`. |
| MAC-33 | pytest: `POST /sessions/{id}/activate` on a `created`/`expired` session succeeds (→`activated`); fails 409 if the participant has another `activated`/`in_progress` session; `POST /sessions/{id}/deactivate` on an `activated` session succeeds (→`expired`); fails 409 on any other status. |
| MAC-34 | pytest: `POST /sessions/{id}/start` on a `created` (non-activated) session → **403** `{"detail":"Session not open. Ask your researcher to open this session."}`; on an `activated` session → 200 and `status→in_progress`. |
| MAC-35 | `/me` renders each of the 6 states (`created`→Locked🔒/no button, `activated`→Ready▶/Start, `in_progress`→In progress→/Resume, `completed`→Done✔/no button, `expired`→Missed✗/no button, `cancelled`→not rendered) exactly per the MFR-35 table. |
| MAC-36 | Group detail panel's Open/Close toggle calls `/activate`/`/deactivate`; while a round is open, shows elapsed time since `activated_at` and live `activated`/`in_progress`/`completed` member counts; Sessions tab shows `activated_at`/`expired_at` on every row with working per-row Activate/Deactivate buttons. |
| MAC-37 | `POST /groups/{id}/activate` response's `activated[]` entries each include a non-empty `display_label` matching the corresponding session's stored `display_label`. |

---

## 9. Interaction walkthrough (MOD-6) and state-transition table

### 9.1 Full session-status transition matrix

All 7 statuses × 7 statuses. `—` = no-op (same status, not a transition).
`✅ <actor> (<trigger>)` = valid transition. `✗` = invalid; any API call that
would cause it is rejected (403/409 as specified by the relevant MFR).

| From ＼ To | created | activated | in_progress | completed | abandoned | expired | cancelled |
|---|---|---|---|---|---|---|---|
| **created** | — | ✅ R (group/single activate) | ✗ | ✗ | ✗ | ✗ | ✅ R (cancel, FR-23) |
| **activated** | ✗ | — | ✅ P (`/start`) | ✗ | ✗ | ✅ R (group/single deactivate) | ✅ R (cancel, FR-23) |
| **in_progress** | ✗ | ✗ | — | ✅ P (`/complete`) | ✅ server (30-min lazy, FR-21) | ✗ | ✗ |
| **completed** | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ |
| **abandoned** | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ |
| **expired** | ✗ | ✅ R (re-activate, group/single) | ✗ | ✗ | ✗ | — | ✅ R (cancel, FR-23) |
| **cancelled** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — |

Notes:
- `completed`, `abandoned`, `cancelled` are terminal (no outgoing edges) —
  consistent with existing FR-21/FR-23 terminality.
- The lazy 30-minute job (FR-21, unchanged) only ever performs
  `in_progress → abandoned`; it never touches `created`/`activated`/
  `expired`.
- `✗` cells map to: attempting `/start` from `created`/`expired`/`completed`/
  `abandoned`/`cancelled` → **403** (MFR-34, only non-`activated` case
  defined); attempting `/activate` from `in_progress`/`completed`/
  `abandoned`/`cancelled`, or `/deactivate` from anything but `activated` →
  **409** (MFR-33); attempting cancel from `in_progress`/`completed` → 409
  (unchanged FR-23).

### 9.2 Worked walkthrough — Group A's 5th intervention session

This walkthrough instantiates MOD-3 + MOD-4 + MOD-5 together, for a study
with `sessions_per_week=3`. "Group A" is about to run its **5th intervention
session** (`intervention_session_number=5`).

1. On Group A's detail panel, the researcher has set
   `current_intervention_session=5` (MFR-23 — informational only, set
   manually via the `+1` button or direct edit over the prior weeks).

2. Each active Group A participant's next-due session (lowest `order_index`
   with `status IN ('created','expired')`) is the **pre** session for
   `intervention_session_number=5`: `order_index = 2×5 = 10`,
   `session_type='pre'`. Per MFR-15 with `sessions_per_week=3`:
   `week_number = ceil(5/3) = 2`, `day_within_week = ((5-1) mod 3)+1 = 2`.
   Per MFR-16, `display_label = "Week 2 · Day 2 · Pre"`. All these sessions
   are currently `created` (first time) or `expired` (if a prior open/close
   cycle missed some participants).

3. Researcher clicks **Open session** on Group A's panel →
   `POST /groups/{groupA_id}/activate`. The MFR-31 pre-condition check finds
   no Group A member currently `activated`/`in_progress`, so it proceeds:
   each member's `order_index=10` session transitions
   `created|expired → activated`, with `activated_at`/`activated_by` set.
   The response's `activated[]` lists each participant with `session_id`,
   `session_type='pre'`, `order_index=10`, and
   `display_label="Week 2 · Day 2 · Pre"` (MFR-37). The UI shows: *"You are
   opening: Week 2 · Day 2 · Pre for 4 participants."*

4. Participants log in to **My sessions**. The `order_index=10` row shows
   `display_label="Week 2 · Day 2 · Pre"` with a blue "Pre" chip and status
   "Ready ▶" (green highlight, MFR-35). Each participant clicks **Start** →
   `POST /sessions/{id}/start`; since `status=='activated'`, this succeeds
   (→`in_progress`, `started_at` set) and the task runs using the session's
   snapshotted `params`/`task_type` (= the study's `task_type_pre` at
   protocol-generation time).

5. After all participants finish (or the researcher decides not to wait
   further), the researcher clicks **Close session** →
   `POST /groups/{groupA_id}/deactivate`. Any member whose `order_index=10`
   session is still `activated` (not yet started) causes a 409 with
   `not_started_count > 0`; the researcher confirms the dialog from MFR-32,
   resending with `{force:true}`. Those sessions → `expired`
   (`expired_at` set). Any sessions already `in_progress` are **not**
   touched and continue to `completed`/`abandoned` normally.

6. Later (same day or a future day), the researcher repeats the cycle for
   the **post** session of `intervention_session_number=5`:
   `order_index = 2×5+1 = 11`, `session_type='post'`, same
   `week_number=2`/`day_within_week=2` →
   `display_label = "Week 2 · Day 2 · Post"`. **Open session** now activates
   each member's `order_index=11` session (the new lowest `created`/`expired`
   `order_index`, since `order_index=10` is now `completed` or `expired`);
   the UI shows *"You are opening: Week 2 · Day 2 · Post for 4
   participants."* **Close session** repeats step 5's logic.

> **Resolved spec inconsistency (see Decisions §10, D-MOD6):** the original
> MOD-6 prose used the illustrative labels "Week 5 · Session 5 · Pre" /
> "Week 5 · Session 5 · Post" for this walkthrough. Applying MFR-15/MFR-16's
> explicit formulas to `intervention_session_number=5`,
> `sessions_per_week=3` yields `week_number=2`, `day_within_week=2`, hence
> `display_label="Week 2 · Day 2 · Pre"` / `"...Post"`, as used above. The
> formula-derived values are authoritative; the original prose is corrected
> here and is the value all MAC-16/MAC-37 tests must assert.

---

## 10. Decisions & Defaults appendix

Every assumption made while writing this PRD, beyond what
`04_Modifications_PRD_Prompt.md` / `02_PRD.md` state explicitly. Numbering
continues independently of `DECISIONS_TAKEN.md` (which records
*implementation*-time decisions); cross-references are given where a
decision here will also be logged there during the build.

**D-MOD6 — MOD-6 walkthrough label correction.** The MOD-6 prompt's
walkthrough prose ("Week 5 · Session 5 · Pre/Post") conflicts with the
MFR-15/MFR-16 formulas applied to `intervention_session_number=5,
sessions_per_week=3` (which yield "Week 2 · Day 2 · Pre/Post"). **The
formulas are authoritative.** §9.2 uses the corrected labels; all MAC tests
referencing this walkthrough use "Week 2 · Day 2 · Pre"/"...Post".

**D1 — Label defaults for ad-hoc sessions created via endpoint #15.** MOD-3
adds NOT-NULL columns (`session_type`, `display_label`, etc.) to `sessions`,
but endpoint #15 (`POST /studies/{id}/sessions`, pre-existing manual
assignment, outside the MFR-18 protocol-generation flow) has no natural
source for these values. Default: `session_type='pre'`,
`intervention_session_number=order_index`, `week_number=ceil(order_index /
sessions_per_week)`, `day_within_week=((order_index-1) mod
sessions_per_week)+1` (using the study's current `sessions_per_week`),
`display_label="Session {order_index}"`, `display_label_overridden=false`.
Researchers can immediately edit `display_label` per MFR-14. `task_type`
for these sessions continues to default to the study's `task_type` (or
`overrides.task_type`) as before MOD-3 — `task_type_onboarding/pre/post` are
used only by MFR-18.

**D2 — Migration 0003 backfill for existing rows.** Existing `sessions` rows
(created before MOD-3) get: `session_type='pre'`,
`intervention_session_number=order_index`,
`week_number=ceil(order_index/sessions_per_week)` (using each row's study's
`sessions_per_week`, which itself backfills to the new default `3` for
existing studies), `day_within_week=((order_index-1) mod
sessions_per_week)+1`, `display_label='Session ' || order_index`,
`display_label_overridden=false`. This keeps the new NOT NULL constraints
satisfiable for pre-existing data without inventing a new enum value. The
existing v1 smoke-test study (if any persists across environments) is
unaffected functionally — only these new descriptive columns gain values.

**D3 — `studies.task_type` remains and is independent of
`task_type_onboarding/pre/post`.** MOD-3 does not deprecate
`studies.task_type` (FR-9, Decision #7 in `DECISIONS_TAKEN.md` — immutable
after creation). It continues to be: (a) the default `task_type` for ad-hoc
sessions created via #15 (D1), and (b) the type used by the FR-33 preview
endpoint by default. `task_type_onboarding/pre/post` are used exclusively by
MFR-18 protocol generation and are independent fields — a study can have
`task_type='CRT4'` while `task_type_pre='SRT'`, etc. All four are validated
independently against MFR-8 wherever relevant.

**D4 — Post-generation protocol-config lock (MFR-12).** The PRD prompt does
not explicitly say whether `num_intervention_sessions`/`sessions_per_week`/
`task_type_*` remain editable after sessions exist. Decision: lock them
once any `session_type IS NOT NULL` row exists for the study (i.e. after the
first `generate-protocol` call), returning 422 on `PATCH /studies/{id}`.
Rationale: changing `sessions_per_week` after generation would silently
desync the already-computed/stored `week_number`/`day_within_week`/
`display_label` values (which are NOT recomputed per MFR-15/16), producing
inconsistent labels; locking is simpler and safer than a cascading
recompute, and mirrors the precedent of Decision #7 (`task_type`
immutability) in `DECISIONS_TAKEN.md`.

**D5 — `display_label` edit window (MFR-14).** Decision: `display_label` is
editable only while `status IN ('created','expired')`; **409** once
`activated`/`in_progress`/`completed`. Rationale: avoids relabelling a
session a participant is actively looking at or has already completed,
while still allowing pre-activation corrections and post-deactivation
relabelling for a re-opened/rescheduled session.

**D6 — Group-assignment batch semantics (MFR-24).** The build-prompt's Step
4 test list says "409 on reassignment attempt", implying a single-participant
case. For multi-participant batches, an all-or-nothing 409 would make bulk
assignment unusable once any one participant in a large cohort is already
assigned. Decision: 409 only when **every** requested participant is already
assigned (i.e., `assigned` would be empty); otherwise 200 with
per-participant `assigned`/`conflicts` lists. The literal single-participant
reassignment test (Step 4) still produces 409.

**D7 — Groups surfaced as their own dashboard tab (MFR-25).** Decision: a
new top-level "Groups" tab on `/studies/:id` (alongside Settings,
Demographics, Participants, Sessions, Dashboard), not a section embedded in
the existing Dashboard tab — mirrors how Sessions/Participants are already
separate tabs, and keeps the Dashboard tab (FR-50…FR-53, read-only
analytics) free of group-management controls (consistent with Decision #8 in
`DECISIONS_TAKEN.md`, which separates analytics from management UI).

**D8 — `group_name` CSV column position (MFR-26).** Decision: `group_name`
is appended as the **last** column of every existing row shape in #28, #29,
and all four files inside #30's ZIP — never inserted/reordered among
baseline FR-54/55/56/57 columns, so existing column-order assertions in
baseline tests remain valid unchanged, and new tests need only check the
final column.

**D9 — `locked` field retained but non-authoritative (MFR-35).** `GET
/me/sessions` keeps the existing `locked: bool` field in its response shape
(avoids a breaking removal), but the frontend's status-driven 6-state
rendering (MFR-35) is authoritative for button visibility — `locked` is
informational only post-MOD-5.

**D10 — Group-size guidance thresholds (MFR-22).** "Recommended 4–6" is
read as: show the soft-warning for member counts `0,1,2,3` or `7+`; show
nothing for `4,5,6`. Never blocks any action, per the prompt's explicit "not
a hard block" framing.

**D11 — `current_intervention_session` range (MFR-23) vs
`num_intervention_sessions` range (MFR-11).** The source prompt gives
`current_intervention_session` a range of 1–52 but `num_intervention_sessions`
a range of 1–156. These are taken as-given/independent: the group counter's
52-cap is a display-only convenience (52 weeks/year at 1/week) and is not
reconciled with the study's actual `num_intervention_sessions`; a study with
`num_intervention_sessions=156` simply cannot represent its later
intervention numbers in this counter, which is acceptable since the counter
has no functional effect (MFR-23).

**D12 — "Eligible participant" for group activate/deactivate (MFR-31/32).**
"Non-cancelled, non-completed participant" in MFR-31 is operationalized as:
a participant is eligible for activation in a given call iff they have ≥1
session with `status IN ('created','expired')`; if none remain (all
`completed`/`cancelled`), they are silently skipped (already stated in MFR-31
item 3 — this decision just clarifies there is no separate
participant-level "cancelled"/"completed" state to check beyond their
sessions' statuses).

**D13 — Scope of the "another activated/in_progress session" check
(MFR-31 precondition, MFR-33 single-activate 409).** Both checks are scoped
to "in this study" — i.e. across all of the participant's sessions belonging
to the study being activated/deactivated, not globally across all studies a
participant might (hypothetically) belong to. Consistent with the existing
data model where a participant belongs to exactly one study.

**D14 — `group_name` covers all four export-ZIP files (MFR-26).** "All CSV
exports" is read to include every file inside the `/studies/{id}/export.zip`
(#30) — i.e. all four files referenced by AC-54…AC-57/AC-15 gain a trailing
`group_name` column (empty string for any row whose participant is
unassigned), not just the two single-resource CSV endpoints (#28/#29).

**D15 — Worked `display_label` values for the MOD-3 smoke scenario.** For
`num_intervention_sessions=24, sessions_per_week=3` (the exact `smoke_v2.py`
scenario), the protocol's `order_index` 1/4/5/24 sessions have:

| order_index | session_type | intervention_session_number | week_number | day_within_week | display_label |
|---|---|---|---|---|---|
| 1 | onboarding | NULL | NULL | NULL | `"Onboarding"` |
| 4 | pre | 2 | 1 | 2 | `"Week 1 · Day 2 · Pre"` |
| 5 | post | 2 | 1 | 2 | `"Week 1 · Day 2 · Post"` |
| 24 | pre | 12 | 4 | 3 | `"Week 4 · Day 3 · Pre"` |

(Derivation: `order_index=2k→pre(k)`, `order_index=2k+1→post(k)`; for
`order_index=4`, `k=2`; for `order_index=5`, `k=2`; for `order_index=24`,
`k=12`. Then `week_number=ceil(k/3)`, `day_within_week=((k-1) mod 3)+1` per
MFR-15.) `smoke_v2.py` asserts these four values verbatim. Separately, the
`order_index=2` session (`k=1`) has `display_label="Week 1 · Day 1 · Pre"`,
used by `smoke_v2.py`'s group-activation assertion (MAC-31/MAC-37).

**D16 — `activated`/`expired` in dashboard `Record<SessionStatus,…>` maps
(MFR-9/§7.7, dashboard exhaustiveness).** Where the Dashboard tab's
status-keyed maps (e.g. `STATUS_LABELS`) must be exhaustive for `tsc
--noEmit`, `activated` and `expired` are added with labels "Activated"
("Activated"/treated as not-yet-run alongside `created`) and "Missed"
respectively, using neutral/grey styling consistent with their rarity in
completed-session-oriented charts — these statuses are expected to appear
primarily on the Sessions/Groups tabs (MFR-35/MFR-36), not the analytics
charts.

