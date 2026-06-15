# Product Requirements Document: Modifications v2

**Status:** Draft  
**Scope:** Five researcher-facing enhancements — two require backend API changes (Changes 1 and 2), two are pure frontend (Changes 3 and 4), and one is a major frontend refactor (Change 5). All are non-breaking and independently shippable.

---

## Change 1: Separate Group-Level Activation for Pre-Sessions and Post-Sessions

### Problem Statement

The "Open session" button in the Groups tab currently activates only **pre-sessions** for the entire group at the current intervention session (IS) number. There is no group-level mechanism to activate post-sessions. Researchers who need to open post-sessions for a whole group — which typically happens a day or more after pre-sessions — must navigate to the Sessions tab and activate each participant's post-session individually. This workflow scales poorly and is error-prone in groups larger than a handful of participants.

### User Stories

1. As a researcher, I want to open pre-sessions for my entire group with one click, so that all participants can complete their pre-session at the start of an intervention session.
2. As a researcher, I want to open post-sessions for my entire group with one click, so that all participants can complete their post-session after the intervention without me having to activate each one manually.
3. As a researcher, I want confirmation of how many sessions were opened and which type, so that I know the action succeeded and can account for any participants whose session was not in an activatable state.

### Functional Requirements

**FR-1.1** The Groups tab detail panel must replace the single "Open session (IS N)" button with two separate buttons:
- **"Open pre (IS N)"** — activates all pre-type sessions for the current group at `current_intervention_session = N`.
- **"Open post (IS N)"** — activates all post-type sessions for the current group at `current_intervention_session = N`.

**FR-1.2** Both buttons must be visible only when `current_intervention_session` is set on the group (not null). Both must be disabled while any async request is in flight.

**FR-1.3** The backend `POST /groups/{group_id}/activate` endpoint must accept an optional `session_type` field in the request body with allowed values `"pre"` and `"post"`. The default when omitted must remain `"pre"` to preserve backwards compatibility with any existing callers.

**FR-1.4** The backend must activate all sessions matching:
- `participant_id` is in the group's member list
- `intervention_session_number == group.current_intervention_session`
- `session_type == <requested type>`
- `status` in `{"created", "expired"}`

**FR-1.5** The success feedback message must specify the session type and the count of sessions activated. Examples:
- "Activated 6 post-session(s) for IS 4."
- "0 post-session(s) activated for IS 4 — none were in an activatable state."

**FR-1.6** The existing "Close session" and "Force close" buttons must remain unchanged. They close all activated sessions at the current IS regardless of type, which is the correct behavior and requires no modification.

**FR-1.7** The `GroupActivateResponse` schema must include a `session_type` field echoing which type was activated, so callers can confirm the operation without re-querying.

### Acceptance Criteria

| # | Scenario | Expected Result |
|---|----------|-----------------|
| AC-1.1 | Researcher clicks "Open pre (IS 3)" for a group of 6 with pre-sessions in `created` state | 6 pre-sessions → `activated`; message: "Activated 6 pre-session(s) for IS 3." |
| AC-1.2 | Researcher clicks "Open post (IS 3)" after AC-1.1 | 6 post-sessions → `activated`; message: "Activated 6 post-session(s) for IS 3." |
| AC-1.3 | Researcher clicks "Open pre (IS 3)" when all pre-sessions are already `activated` or `completed` | 0 sessions activated; message indicates 0. No error thrown. |
| AC-1.4 | Group has no `current_intervention_session` set | Neither "Open pre" nor "Open post" is rendered. |
| AC-1.5 | `POST /groups/{id}/activate` called without `session_type` | Behaves as `session_type = "pre"` (backwards-compatible default). |
| AC-1.6 | `POST /groups/{id}/activate` called with `session_type = "post"` | Only post-sessions are activated; pre-sessions are unaffected. |
| AC-1.7 | Researcher clicks "Close session" after opening both pre and post | All `activated` sessions at the current IS (pre and post) transition to `expired`. |

### Non-Goals

- Activating **onboarding** sessions at the group level. Onboarding has no IS number and continues to be managed individually.
- Adding separate close buttons for pre vs. post types.
- Any change to the deactivation (close/force-close) flow.

---

## Change 2: Allow Group Reassignment When Sessions Have Not Been Started

### Problem Statement

Group assignment is currently permanent once set. The `POST /groups/{group_id}/assign` endpoint returns `409 Conflict` for any participant already in a group, with the message "Assignments cannot be changed." In practice, researchers occasionally assign participants to the wrong group or need to rebalance groups before the study begins — before any participant has submitted trial data. The blanket prohibition forces workarounds such as deleting and recreating participants, causing code gaps in the participant roster.

### User Stories

1. As a researcher, I want to move a participant from one group to another before they have started any sessions, so that I can correct assignment mistakes made during study setup.
2. As a researcher, I want the system to prevent me from moving a participant who has already submitted trial data, so that I cannot corrupt the group-level statistical record.
3. As a researcher, I want clear feedback distinguishing between participants who were newly assigned, successfully reassigned, and blocked (because they have started sessions), so that I can act on each case individually.

### Functional Requirements

**FR-2.1** A session is "started" if its status is `in_progress`, `completed`, or `abandoned`. Sessions with status `created`, `activated`, `expired`, or `cancelled` are not started (no trial data has been submitted for these statuses).

**FR-2.2** When `POST /groups/{group_id}/assign` is called and a requested participant already has a group assignment, the endpoint must:
- Query whether the participant has any sessions with status in `{in_progress, completed, abandoned}`.
- **If no started sessions exist:** delete the existing `ParticipantGroupAssignment` row, flush the transaction, then insert a new row assigning the participant to the new group. Record the participant in a `reassigned` list.
- **If started sessions exist:** leave the assignment unchanged. Record the participant in a `blocked` list with reason `"sessions_started"`.

**FR-2.3** The `GroupAssignResponse` schema must be extended to include:
- `reassigned: list[ReassignedItem]` — participants moved from one group to another. Each item includes `participant_id`, `code`, `previous_group_name`, and `new_group_name`.
- `blocked: list[BlockedItem]` — participants whose assignment could not be changed. Each item includes `participant_id`, `code`, `current_group_name`, and `reason`.

**FR-2.4** HTTP response codes:
- `200 OK` when at least one participant was successfully assigned or reassigned (even if others were blocked).
- `409 Conflict` only when every requested participant was blocked (no assignments were changed at all).

**FR-2.5** The frontend success message in the Participants tab "Assign to group" flow must reflect all three categories. Example: "Assigned 2, reassigned 1; 1 participant blocked (sessions already started)."

**FR-2.6** The `db.flush()` between the delete and insert of `ParticipantGroupAssignment` rows is mandatory to avoid violating the `UNIQUE(participant_id)` database constraint within the same transaction.

**FR-2.7** No structural change is required in the Participants tab UI. The existing checkbox multi-select + group dropdown + "Assign to group (N)" button workflow is sufficient to perform reassignments.

### Acceptance Criteria

| # | Scenario | Expected Result |
|---|----------|-----------------|
| AC-2.1 | Participant in Group A with all sessions in `created`; researcher assigns to Group B | Moved to Group B; in `reassigned` list; `200 OK`. |
| AC-2.2 | Participant in Group A with one session `in_progress`; researcher assigns to Group B | Assignment unchanged; in `blocked` list; `409` if all participants in request were blocked. |
| AC-2.3 | Participant in Group A with all sessions in `activated` state | Treated as AC-2.1; `activated` is not started. Reassignment allowed. |
| AC-2.4 | Participant in Group A with one `completed` session and other `created` sessions | Blocked. Even one completed session prevents reassignment. |
| AC-2.5 | Batch of 3: 2 unassigned + 1 in Group A with no started sessions | All 3 succeed; 2 in `assigned`, 1 in `reassigned`; `200 OK`. |
| AC-2.6 | Batch of 2: both already assigned, both have started sessions | `409 Conflict`; no assignments changed. |
| AC-2.7 | Participant moved from Group A to Group B | Group A member count decrements; Group B member count increments; visible in both group detail panels. |

### Non-Goals

- Reassigning participants who have any started session. This is a hard block by design.
- Bulk-unassigning participants from a group without assigning them to a new one.
- Any UI change to the Groups tab for reassignment.
- Re-generating or re-labelling sessions when a participant is reassigned. Sessions are unchanged.

---

## Change 3: Rename "Code" Column to "Session Code" in the Sessions Tab

### Problem Statement

The Sessions table has a column labeled "Code" displaying the session's unique alphanumeric identifier (e.g., `A7F3X2PQ`). The Participants table also has a column labeled "Code" displaying the participant's identifier (e.g., `PILOT-001`). In verbal discussion, documentation, and support conversations, "code" is ambiguous between the two. Researchers and staff must stop to clarify which code is meant, creating unnecessary friction.

### User Stories

1. As a researcher, I want the session code column to be clearly labeled "Session code" so that it is immediately distinguishable from the participant code, both in the UI and in everyday speech.

### Functional Requirements

**FR-3.1** In `StudySessionsTab.tsx`, the `<th>` element currently reading "Code" must be changed to "Session code".

**FR-3.2** The `<td>` cell rendering `session.code` is unchanged — only the header label changes.

**FR-3.3** No other column labels, API fields, export file headers, or other UI locations are modified.

### Acceptance Criteria

| # | Scenario | Expected Result |
|---|----------|-----------------|
| AC-3.1 | Researcher opens the Sessions tab | Column header reads "Session code". |
| AC-3.2 | Session code values in cells | Values unchanged. |
| AC-3.3 | All other tabs and pages | No label changes anywhere else. |

### Non-Goals

- Renaming any API response field (`session.code` stays `code`).
- Renaming the "Code" column in the Participants table or any export file.

---

## Change 4: Unified Task Type Selection

### Problem Statement

Both the Protocol settings form (Settings tab) and the Generate Protocol form (Participants tab) present three separate task type dropdowns: one each for Onboarding, Pre, and Post sessions. All three must always be set to the same value — there is no operational or scientific rationale for using different task types across session phases within a study. The three-dropdown arrangement requires the researcher to make three redundant selections per form and creates a risk of accidentally setting mismatched types (e.g., CRT4 for onboarding, SRT for pre), which the UI does not catch and which would compromise data comparability.

### User Stories

1. As a researcher setting up a study, I want to select the task type once and have it apply to all session phases automatically, so that I cannot accidentally create mismatched configurations.
2. As a researcher opening a legacy study where the three types were configured differently, I want to see a clear warning before saving, so that I know a normalization is about to occur and can verify the unified value is correct.

### Functional Requirements

**FR-4.1** In `StudySettingsTab.tsx — ProtocolConfigForm`: Replace the three `<Field>` blocks for "Onboarding task type", "Pre task type", and "Post task type" with a single `<Field label="Task type">` dropdown. The local state variables `ttOnboarding`, `ttPre`, `ttPost` are merged into a single `taskType` variable.

**FR-4.2** In `StudyParticipantsTab.tsx — GenerateProtocolForm`: Apply the same consolidation. Single `taskType` state replaces the three separate variables.

**FR-4.3** The initial value of `taskType` must be read from `study.task_type_pre`. (All three values should be equal in any correctly-configured study; `task_type_pre` is the canonical source.)

**FR-4.4** On save (Settings tab) or on generate (Participants tab), the unified value must be sent for all three API fields: `task_type_onboarding`, `task_type_pre`, and `task_type_post`. The API payload structure is unchanged.

**FR-4.5** Legacy inconsistency detection: On form mount, if `study.task_type_onboarding`, `study.task_type_pre`, and `study.task_type_post` are not all equal, display an informational banner reading: *"This study's task types were previously configured differently across session phases. The value shown below will be applied to all phases when you save."* The banner is dismissible. No automatic normalization occurs on mount — the researcher must click Save to commit it.

**FR-4.6** When the protocol is locked (`study.protocol_locked === true`), the unified selector must be disabled with the existing amber "read-only" banner. The legacy inconsistency banner (FR-4.5) must not appear when the form is locked — the lock state takes precedence.

**FR-4.7** No backend schema changes. The backend continues to store and expose three separate fields. No migration is required.

### Acceptance Criteria

| # | Scenario | Expected Result |
|---|----------|-----------------|
| AC-4.1 | Settings tab opened; all three stored types are CRT4 | Single "Task type" dropdown shows CRT4; no warning banner. |
| AC-4.2 | Researcher changes unified dropdown to SRT and saves | Backend receives `task_type_onboarding: "SRT"`, `task_type_pre: "SRT"`, `task_type_post: "SRT"`. |
| AC-4.3 | Settings tab opened; stored values are onboarding=SRT, pre=CRT4, post=CRT4 | Warning banner displayed; dropdown shows CRT4 (from `task_type_pre`). |
| AC-4.4 | Researcher saves the form from AC-4.3 without changing the dropdown | All three fields saved as CRT4; warning banner absent on reload. |
| AC-4.5 | Protocol is locked | Unified dropdown is disabled; amber read-only banner shown; no inconsistency warning shown. |
| AC-4.6 | Generate Protocol form in Participants tab | Same single-dropdown behavior; same value sent for all three fields on submit. |

### Non-Goals

- Enforcing at the backend that all three fields must be equal. The backend continues to accept three independent values.
- Modifying the top-level `study.task_type` field, which is managed separately in the Study Details form.
- Changing export file headers or any API response shape.

---

## Change 5: Grouping, Collapsible Sections, and Column-Header Sorting in the Sessions Tab

### Problem Statement

The Sessions tab renders a single flat table of every session across all participants. A study with 30 participants × 49 sessions each yields 1,470 rows — the table scrolls endlessly with no way to focus. Researchers cannot review one participant's complete protocol without manually filtering by that participant, and they have no way to see collective group progress in a single view. Additionally, the only sorting mechanism is a fixed six-option dropdown offering a limited set of server-side sort fields, with no visual indication of the active sort in the table itself and no ability to sort by session type, task type, activation time, or performance metrics.

### User Stories

1. As a researcher, I want to collapse all sessions except one participant's, so that I can review that participant's complete protocol without distraction.
2. As a researcher, I want to view all sessions organized by group, so that I can see the collective progress of each group at a glance.
3. As a researcher, I want to sort the sessions table by clicking any column header, so that I can quickly find the most recently activated sessions, or rank participants by mean reaction time.
4. As a researcher, I want to collapse groups or participants I am not currently reviewing, so that the table stays manageable even in a large study.

### Functional Requirements

#### FR-5.1 — Group-by Control

A "Group by" control must be added to the filter/control bar above the sessions table. It must offer three options:

- **None** — flat list, existing behavior, default on page load.
- **Participant** — sessions partitioned into one collapsible section per participant.
- **Group** — sessions partitioned into one collapsible section per group.

The control must be implemented as radio buttons or a segmented button control. The selected mode is local state and resets to "None" on page navigation.

#### FR-5.2 — Group by Participant Mode

When "Participant" is selected:

- Sessions are partitioned into one collapsible section per unique `participant_code` visible in the current filtered result set.
- Each section has a **section header row** spanning all columns showing: participant code (bold), total session count for that participant, and count of completed sessions. Example: "PILOT-001 — 12 sessions, 4 completed".
- Clicking the section header toggles that participant's session rows visible/hidden.
- All sections are expanded by default when the mode is first selected.
- Sections are ordered alphabetically by participant code.

#### FR-5.3 — Group by Group Mode

When "Group" is selected:

- Sessions are partitioned by the group of each session's participant.
- Each section has a **section header row** showing: group name (bold), count of distinct members visible in the current filter, and count of completed sessions across those members. Example: "Group A — 6 members, 23 sessions completed".
- Participants not assigned to any group are collected into a single **"Unassigned"** section placed at the bottom of the list.
- Sections are ordered alphabetically by group name, with "Unassigned" always last.
- All sections are expanded by default when the mode is first selected.
- Within each group section, session rows are rendered flat (not sub-grouped by participant). The Participant column in each row provides participant identity.

#### FR-5.4 — Collapse / Expand Controls

- When any grouping mode is active, a "Collapse all" button and an "Expand all" button must appear above the table.
- "Collapse all" collapses every section. "Expand all" expands every section.
- These controls are hidden when grouping mode is "None".

#### FR-5.5 — Filter Interaction with Grouping

- The existing Status filter and Participant filter continue to work in all grouping modes. Applying a filter does not reset the grouping mode.
- If a filter results in no sessions for a given participant or group, that section is hidden entirely.
- When the Participant filter is set to a single participant under "Group by Group" mode, only that participant's group section appears, containing only that participant's rows. This is correct by construction and requires no special handling.

#### FR-5.6 — Column-Header Sorting

The existing "Sort by" dropdown is removed. Every column header except the Actions column becomes a clickable sort control.

- Clicking a column header that is not the active sort field: sorts ascending by that field.
- Clicking the already-active column header: toggles direction between ascending and descending.
- A directional indicator (**▲** for ascending, **▼** for descending) is rendered inside the active sort column header.
- Non-active column headers show no indicator (or a neutral ⇅ on hover).

**Sortable columns and their sort keys:**

| Column | Sort key | Notes |
|--------|----------|-------|
| Participant | `participant_code` | String, case-insensitive |
| # | `order_index` | Integer |
| Label | `display_label` | String, case-insensitive |
| Type | `session_type` | Logical order: onboarding < pre < post |
| Session code | `code` | String |
| Task | `task_type` | String |
| Status | `status` | String |
| Attempt | `attempt` | Integer |
| Activated | `activated_at` | Datetime; nulls last in both directions |
| Completed | `completed_at` | Datetime; nulls last in both directions |
| Trimmed mean RT | `stats.trimmed_mean_rt_ms` | Number; nulls last |
| Accuracy | `stats.accuracy_pct` | Number; nulls last |

**Default sort on page load:** participant code ascending, then `order_index` ascending as a tiebreaker.

#### FR-5.7 — Sort Interaction with Grouping

- When grouping is active, column-header sorting applies to session rows **within each section**. It does not reorder the sections themselves.
- Sections remain in their defined order (alphabetical by participant code or group name; "Unassigned" last).
- The sort indicator in the column header is always visible regardless of grouping mode.

#### FR-5.8 — Client-Side Sorting

- All sorting is performed client-side on the already-fetched `SessionOut[]` array. The existing server-side `sort` query parameter must be removed from the `sessionsApi.list()` call.
- Null datetime and numeric values sort last in both ascending and descending order.

#### FR-5.9 — Group Membership Derivation

- `SessionOut` does not carry `group_name` or `group_id`. The Sessions tab already fetches `ParticipantOut[]` (for the Participant filter dropdown). `ParticipantOut` includes `group_id` and `group_name`.
- Group membership for each session must be derived client-side by building a `Map<participant_id, group_name | null>` from the loaded participants array and looking up each session's `participant_id`. A null value means "Unassigned".
- No backend changes are required for grouping.

### Acceptance Criteria

| # | Scenario | Expected Result |
|---|----------|-----------------|
| AC-5.1 | Page loads with default settings | Flat table; sorted by participant code then order index; no sort dropdown; no group-by control active. |
| AC-5.2 | Researcher selects "Group by Participant" | Sessions partitioned into per-participant sections, all expanded, alphabetical. Section headers show code and counts. |
| AC-5.3 | Researcher clicks a participant section header | That section collapses; other sections unaffected. Clicking again expands it. |
| AC-5.4 | Researcher clicks "Collapse all" | All sections collapse. "Expand all" restores all. |
| AC-5.5 | Researcher selects "Group by Group" | Sections per group, alphabetical; "Unassigned" at bottom. Section headers show group name and counts. |
| AC-5.6 | Researcher applies Status=Completed filter in Group-by-Group mode | Only completed sessions shown; sections with no completed sessions hidden; remaining sections show only completed rows. |
| AC-5.7 | Researcher clicks "Completed" column header | Sessions sorted by `completed_at` ascending; ▲ appears on Completed header. |
| AC-5.8 | Researcher clicks "Completed" header again | Sessions sorted descending; ▼ appears. |
| AC-5.9 | Active sort is Accuracy ascending; researcher switches to Group-by-Group mode | Sessions within each group section sorted by accuracy ascending; sections in alphabetical order. |
| AC-5.10 | Session with null `completed_at`; sort by Completed ascending | Null-date sessions appear after all dated sessions. |
| AC-5.11 | "Group by Group" selected; all participants unassigned | Single "Unassigned" section containing all sessions. |
| AC-5.12 | "Group by Participant" active; researcher switches to "None" | Flat table restored; collapse state discarded. |
| AC-5.13 | Sort by "Type" column | Onboarding rows first, then pre, then post. |
| AC-5.14 | Participant filter set to a single participant in "Group by Group" mode | Only that participant's group section shown, containing only that participant's rows. |

### Non-Goals

- Persisting grouping mode or sort state across page loads or tab switches.
- Sub-grouping by participant within Group-by-Group mode (participant identity is visible in each row's Participant column).
- Adding a Group filter to the filter bar.
- Server-side grouping or aggregation.
- Paginating the sessions table.

---

## Implementation Notes

### Change 1 — Backend

**File:** `backend/app/routers/groups.py`

Create or update a `GroupActivateRequest` Pydantic schema in `backend/app/schemas/groups.py` with field `session_type: Literal["pre", "post"] = "pre"`. Update the `activate_group()` endpoint to accept this request body. Replace the hardcoded `SessionModel.session_type == "pre"` filter (currently line 309) with `SessionModel.session_type == payload.session_type`. Add `session_type: str` to `GroupActivateResponse`.

**File:** `frontend/src/api/groups.ts`

Update `groupsApi.activate()` to accept `{ session_type: "pre" | "post" }` and include it in the POST body.

**File:** `frontend/src/api/types.ts`

Add `session_type: string` to `GroupActivateResponse`. Add a `GroupActivateRequest` interface if not already present.

**File:** `frontend/src/pages/StudyGroupsTab.tsx`

Replace the single `openSession()` handler with `openPreSession()` and `openPostSession()`, each calling `groupsApi.activate()` with the appropriate type. Replace the single "Open session" button with "Open pre (IS N)" and "Open post (IS N)" buttons. Update the success message to include the session type.

**Tests:** Add cases to `backend/tests/test_groups.py`:
- `test_activate_group_pre` — verifies only pre-sessions are activated.
- `test_activate_group_post` — verifies only post-sessions are activated.
- `test_activate_group_default_is_pre` — verifies omitting `session_type` activates pre sessions.
- `test_activate_group_no_activatable_sessions` — returns empty activated list without error.

---

### Change 2 — Backend

**File:** `backend/app/routers/groups.py — assign_participants()`

When `existing = participant.group_assignment` is not None, query:
```python
started_count = db.execute(
    select(func.count()).select_from(SessionModel).where(
        SessionModel.participant_id == pid,
        SessionModel.status.in_(["in_progress", "completed", "abandoned"])
    )
).scalar_one()
```
- If `started_count > 0`: append to `blocked` list (no DB change).
- If `started_count == 0`: `db.delete(existing)`, `db.flush()`, then `db.add(ParticipantGroupAssignment(...))` and append to `reassigned` list. The `flush()` between delete and insert is mandatory to avoid violating the `UNIQUE(participant_id)` constraint within the same transaction.

Raise `409` only if `not assigned and not reassigned` (all participants were blocked).

**File:** `backend/app/schemas/groups.py`

Add `ReassignedItem` schema: `{ participant_id, code, previous_group_name, new_group_name }`. Add `BlockedItem` schema: `{ participant_id, code, current_group_name, reason }`. Extend `GroupAssignResponse` with `reassigned: list[ReassignedItem]` and `blocked: list[BlockedItem]`.

**File:** `frontend/src/api/types.ts`

Add `ReassignedItem` and `BlockedItem` interfaces to `GroupAssignResponse`.

**File:** `frontend/src/pages/StudyParticipantsTab.tsx — assignToGroup()`

Update the success message construction to include all three categories.

**Tests:** Add cases to `backend/tests/test_groups.py`:
- `test_reassign_participant_no_started_sessions` — moves participant to new group.
- `test_reassign_blocked_by_completed_session` — blocks when completed session exists.
- `test_reassign_blocked_by_in_progress_session` — blocks when in_progress session exists.
- `test_reassign_allowed_with_activated_sessions` — activated sessions do not block reassignment.
- `test_reassign_mixed_batch` — some reassigned, some blocked, returns 200.
- `test_reassign_all_blocked_returns_409` — all blocked returns 409.

---

### Change 3 — Frontend

**File:** `frontend/src/pages/StudySessionsTab.tsx`

Single change: line 338, `<th className="px-4 py-3">Code</th>` → `<th className="px-4 py-3">Session code</th>`.

No backend, API, schema, or test changes required.

---

### Change 4 — Frontend

**File:** `frontend/src/pages/StudySettingsTab.tsx — ProtocolConfigForm`

Remove `ttOnboarding`, `ttPre`, `ttPost` state. Add `taskType` state initialized from `study.task_type_pre`. Add a derived constant `hasInconsistentTypes = study.task_type_onboarding !== study.task_type_pre || study.task_type_pre !== study.task_type_post` computed once on mount (or as a memo). When `hasInconsistentTypes` is true and the form is not locked, render the informational warning banner. Replace the three `selectFor(...)` `<Field>` blocks with a single `<Field label="Task type">`. In `handleSubmit`, send `{ task_type_onboarding: taskType, task_type_pre: taskType, task_type_post: taskType }`.

**File:** `frontend/src/pages/StudyParticipantsTab.tsx — GenerateProtocolForm`

Apply the same consolidation: remove `ttOnboarding`, `ttPre`, `ttPost`; add `taskType` from `study.task_type_pre`; replace three selectors with one; pass the same value for all three fields in `generateProtocol(...)`.

No backend or API type changes required.

---

### Change 5 — Frontend

**File:** `frontend/src/pages/StudySessionsTab.tsx`

**New state:**
- `groupMode: "none" | "participant" | "group"` — default `"none"`.
- `sortField: SortField` — default `"participant_code"`.
- `sortDir: "asc" | "desc"` — default `"asc"`.
- `collapsed: Set<string>` — keys of collapsed sections, default empty.

**Remove:** `sort` state variable, `SORT_OPTIONS` array, the `<Field label="Sort by">` dropdown from JSX, and the `sort` argument from the `sessionsApi.list()` call.

**Participant group map:** When `participants` state is set, build `Map<participant_id, group_name | null>` for O(1) group lookup per session during render. A null value maps to the "Unassigned" bucket.

**Utility functions (extract to a separate file or inline):**

`sortSessions(sessions, field, dir)`: Pure function. Handle nulls by sorting them after all non-null values in both `asc` and `desc` directions. For `session_type`, use the custom order `{onboarding: 0, pre: 1, post: 2}`. Apply `order_index` as a tiebreaker when sorting by `participant_code` or `group_name` context.

`groupSessions(sessions, mode, groupMap)`: Returns `Array<{ key: string; label: string; headerStats: { total: number; completed: number }; sessions: SessionOut[] }>`. Sorts the resulting groups alphabetically by `key`, with the key `"__unassigned__"` always placed last.

**Column header rendering:** Each sortable `<th>` element gets an `onClick` that sets `sortField` and toggles `sortDir`. Pass `sortField` and `sortDir` as props (or via context) to the header row component so the active column can render its directional indicator.

**Section rendering:** When `groupMode !== "none"`, call `groupSessions()` and `sortSessions()` (per-section), render a `<tr>` section header (with `colSpan` covering all columns) followed by the section's `SessionRow` components (hidden when `collapsed.has(key)`). When `groupMode === "none"`, sort the flat `sessions` array and render the existing `SessionRow` list.

**Test notes (Vitest):** Add unit tests for:
- `sortSessions`: null handling for datetime/numeric fields, `session_type` custom order, direction toggle.
- `groupSessions`: "Unassigned" bucket populated correctly, sections alphabetically ordered, empty-section omission, Participant filter interaction.

No backend tests required for Change 5.

---

## Shipping Order (Recommended)

The five changes are independently shippable. To minimize review risk, the recommended order is:

1. **Change 3** — trivial rename, no review burden.
2. **Change 4** — UI consolidation, no API change, low risk.
3. **Change 1** — additive backend change with backwards-compatible default.
4. **Change 2** — most complex backend change; should follow Change 1 so groups are stable before reassignment is introduced.
5. **Change 5** — largest frontend refactor; deferred last so the Sessions tab is not in flux during the backend work.
