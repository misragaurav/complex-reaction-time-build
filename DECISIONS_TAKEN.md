# Decisions Taken

Small implementation decisions made where the PRD (incl. Appendix A) was
silent or under-specified. Each follows the "smallest reasonable choice
consistent with Appendix A" rule.

## Task engine / participant client

1. **FR-29 "Too soon!" is practice-gated, not feedback-gated.** The premature
   warning shows whenever the current block is `practice`, independent of the
   `practice_feedback` flag. Rationale: FR-29 carries its own "in practice
   block only" condition, while `practice_feedback` belongs to FR-32's
   error/timeout feedback. (`frontend/src/task/trialEngine.ts`)

2. **Resume state restarts sequencing bookkeeping.** On resume (FR-35),
   the position history used for the `max_consecutive_repeats` constraint and
   the per-block invalidation count start fresh from what the stored trial
   indices imply; the server-stored trials are the source of truth for which
   indices remain. (`frontend/src/task/sessionRunner.ts::computeResumeState`)

3. **Unload flush uses `fetch(…, {keepalive: true})` instead of
   `navigator.sendBeacon`** (FR-34 names sendBeacon). `sendBeacon` cannot
   carry the `Authorization: Bearer` header this app's auth requires — the
   access token lives only in memory, and the refresh cookie is path-scoped to
   `/api/v1/auth`, so a beacon to `/sessions/{id}/trials` would always arrive
   unauthenticated. `fetch` with `keepalive` is the modern functional
   equivalent with identical survival semantics on `pagehide`.
   (`frontend/src/task/uploadQueue.ts::flushOnUnload`)

4. **`crypto.randomUUID()` fallback.** `randomUUID` requires a secure context
   (https or localhost); a standard RFC 4122 v4 generator is used as fallback
   so trial uploads (keyed on `client_uuid`) also work on plain-http LAN
   deployments. (`frontend/src/task/useTaskRunner.ts`)

5. **Trial-upload buffer warning fires once.** §5.7's non-fatal warning when
   the unsent buffer exceeds 50 trials is shown once per session rather than
   toggling; it is purely diagnostic. (`frontend/src/task/uploadQueue.ts`)

## Preview mode

6. **The preview (FR-33) skips the FR-44 device gate.** FR-44 protects data
   quality for participants; a researcher previewing from the desktop-only
   researcher UI gains nothing from being blocked. Fullscreen, focus-loss and
   fullscreen-exit handling run identically to the real task so behaviour can
   be previewed faithfully. (`frontend/src/pages/StudyPreviewPage.tsx`)

## Researcher UI

7. **Study `task_type` is immutable after creation.** FR-9 allows editing
   parameters before the first session, but changing the task type would
   silently invalidate the key map and the meaning of recorded positions, so
   the API ignores `task_type` inside params updates and the UI shows it
   read-only. Per-session overrides (FR-18) can still choose a different task
   type at assignment time. (`backend/app/routers/studies.py`)

8. **Dashboard sessions table is read-only.** FR-50's table (with filters and
   CSV) lives on the Dashboard tab; management actions (reset / cancel /
   delete / export) live on the Sessions tab, which shows the same rows. This
   keeps FR-22/23 actions in one place without duplicating destructive
   controls. (`frontend/src/pages/StudyDashboardTab.tsx`, `StudySessionsTab.tsx`)

9. **FR-53 "last activity" is computed client-side** as the maximum of
   `last_activity_at`/`completed_at`/`started_at` across the study's sessions
   (the study summary endpoint has no such field, and the dashboard already
   loads the sessions). (`frontend/src/pages/StudyDashboardTab.tsx`)

10. **FR-51(b) "box/strip plot" is rendered as a strip plot.** Recharts has no
    box-plot primitive; a categorical scatter (one point per completed session
    per participant) shows the same distribution and its CSV download contains
    exactly the plotted points. (`frontend/src/pages/StudyDashboardTab.tsx`)

11. **Per-scope trial CSV buttons placement.** FR-54's three export scopes are
    surfaced as: *Export CSV* on each Sessions-tab row (session scope), *Export
    CSV* on each Participants-tab row (participant scope), and *Export study
    data (ZIP)* in the study header (study scope, FR-55).

12. **Demographic field ordering UI.** FR-12's "ordered list" is managed with
    Move up / Move down buttons that swap the two fields' `display_order`
    values via the PATCH endpoint. (`frontend/src/pages/StudyDemographicsTab.tsx`)

## Accounts

13. **Researcher/admin password minimum is 8 characters.** The PRD fixes the
    participant minimum at 6 (FR-3) but is silent for staff accounts; 8 was
    chosen and is enforced by the API and both account forms.

## v2 Modifications (MOD-1 … MOD-5)

These continue the numbering and record assumptions made while implementing
`04_Modifications_PRD.md`. Each also appears in that PRD's "Decisions &
Defaults" appendix; the cross-reference (Dn / D-MOD6) is given.

14. **SRT uses a dedicated singular instructions template (MOD-2, MFR-10).**
    The §5.3 template ("you will see {N} crosses … press the key that matches
    the position") is ungrammatical/meaningless for N=1, so `default_params`
    swaps in a singular template ("you will see a cross … press {KEYS} as
    quickly as you can when the box appears") for `task_type='SRT'`.
    (`backend/app/task_defaults.py`)

15. **SRT key-map cardinality reuses the existing length check (MOD-2,
    MFR-8).** `TaskParams` already enforces `len(key_map) == TASK_POSITIONS[
    task_type]`; adding `TASK_POSITIONS['SRT'] = 1` makes "exactly one key for
    SRT, else 422" fall out with no new branch. The single-key map also makes
    `outcome='incorrect'` structurally impossible, so no change to the trial
    outcome recomputation was needed. (`backend/app/schemas/common.py`)

16. **Protocol-config lock keyed on onboarding-session existence (MOD-3,
    MFR-12 / PRD D4).** The five protocol fields lock once
    `generate-protocol` has run. Since ad-hoc sessions (API #15) are always
    typed `'pre'` (decision 17), the presence of an `'onboarding'` session is
    a clean, unambiguous signal that generation has occurred.
    (`backend/app/routers/studies.py::_protocol_locked`)

17. **Ad-hoc sessions (#15) default to `session_type='pre'` with a derived
    label (MOD-3, PRD D1).** MOD-3 makes `session_type`/`display_label` NOT
    NULL, but the pre-existing manual session-assignment endpoint has no
    protocol position. It sets `session_type='pre'`,
    `intervention_session_number=order_index`, derives week/day from
    `order_index`, and labels them `"Session {order_index}"` — all
    researcher-editable afterwards.
    (`backend/app/services/protocol.py::ad_hoc_label_fields`)

18. **`display_label` editing reuses `PATCH /sessions/{id}` (MOD-3, PRD D5).**
    The action body now accepts exactly one of `{action}` or
    `{display_label}`. Relabel is permitted only while status is
    `created`/`expired`; otherwise 409. Setting it flips
    `display_label_overridden=true`. (`backend/app/routers/sessions.py`)

19. **MOD-3 migration emits CHECK constraints on PostgreSQL only.** SQLite
    cannot `ALTER ADD CONSTRAINT` without a full table rebuild, and SQLite
    dev/test schemas are built from the models via `create_all` (which include
    the constraints). The production target (Postgres) gets the full set.
    (`backend/alembic/versions/0003_mod3_protocol_and_labels.py`)

20. **`week_number` is constrained `>= 1` with no upper bound (MOD-3).** The
    source PRD lists `week_number` as 1–52 but also allows
    `num_intervention_sessions` up to 156 with `sessions_per_week` as low as 1
    — which generates week numbers far above 52. The lower-bound-only CHECK
    resolves that inconsistency without rejecting valid generated protocols.
    (`backend/app/models.py`)
