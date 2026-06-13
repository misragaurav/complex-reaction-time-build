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
