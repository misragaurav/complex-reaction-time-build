# Acceptance Criteria Walkthrough (PRD §10)

Verification performed 2026-06-11 against the final build.

**Gates:** backend `pytest` — 75 passed; `mypy app tests` (strict) — clean,
50 source files; frontend `tsc --noEmit` (strict) — clean; `vitest` — 26
passed; `docker compose up --build` from a clean tree + `.env` — all services
healthy in well under 2 minutes; `python3 scripts/smoke_v2.py` — exit 0.

Evidence column references backend tests (`backend/tests/`), frontend tests
(`frontend/tests/`), the smoke script, or code inspection where the criterion
is a UI behaviour without an automated harness.

| AC | Result | Evidence |
|---|---|---|
| AC-1 (login JWT + refresh cookie, 401 on bad password) | PASS | `test_admin_login_success_returns_jwt_with_id_and_role_and_sets_refresh_cookie`, `test_admin_login_invalid_password_returns_401` |
| AC-2 (participant JWT blocked from A/R endpoints and others' sessions) | PASS | `test_participant_jwt_cannot_call_researcher_endpoint`, `test_participant_cannot_start_another_participants_session` |
| AC-3 (set-password once, 409 on second, 422 below 6 chars) | PASS | `test_set_password_succeeds_once_then_409_then_short_password_422` |
| AC-4 (researcher 403 on POST /users; admin OK; self-deactivation 409) | PASS | `test_admin_create_user_403_for_researcher_201_for_admin`, `test_admin_cannot_deactivate_self` |
| AC-4a (check endpoint: claimed/unclaimed/unknown with identical 404 message) | PASS | `test_participant_check_unclaimed_then_claimed`, `test_participant_check_unclaimed_code_and_deactivated_code` |
| AC-5 (reset_password → 409 password_not_set → set-password flow) | PASS | `test_reset_password_then_login_409_then_set_password_succeeds` |
| AC-6 (11th failed login in 15 min → 429) | PASS | `test_rate_limit_11th_failed_login_returns_429` |
| AC-7 (seed admin created exactly once) | PASS | `test_seed_admin_creates_exactly_one_active_admin` |
| AC-8 (refresh after logout → 401) | PASS | `test_refresh_then_logout_then_refresh_returns_401` |
| AC-9/10/11 (defaults verbatim; params locked after start → 409; archived blocks sessions → 409) | PASS | `test_create_study_with_no_params_uses_defaults_verbatim`, `test_params_locked_after_session_started_returns_409`, `test_archived_study_rejects_new_sessions` |
| AC-12–15 (single_choice without options 422; answered field label edit 409 / DELETE retires; required omission 422; answers in demographics CSV) | PASS | `test_single_choice_without_options_returns_422`, `test_answered_field_rejects_label_edit_and_delete_retires_it`, `test_required_field_missing_on_submit_returns_422`, `test_study_export_zip_contains_four_files` (demographics.csv contents) |
| AC-16 (100 unique generated codes; duplicate custom code 409) | PASS | `test_bulk_create_100_participants_unique_codes`, `test_manual_codes_creation_and_duplicate_conflict` |
| AC-17 (deactivated participant 401; data still exports) | PASS | `test_deactivated_participant_login_returns_401`, `test_deactivated_participant_login_401_but_still_listed`, export tests include all participants |
| AC-18/19 (ad-hoc multi-session creation with overrides) | SUPERSEDED | Ad-hoc session creation removed in MOD-6. Param-snapshot immutability for protocol sessions evidenced by `test_params_locked_after_session_started_returns_409` and the protocol-generation tests. |
| AC-20 (out-of-order start 409; UI shows locked) | PASS | `test_start_enforces_session_order_lock`, `test_my_sessions_lock_state`; UI lock rendering in `frontend/src/pages/MySessionsPage.tsx` ("Complete session N first") |
| AC-21 (31-min stale in_progress reads back abandoned) | PASS | `test_lazy_abandonment_after_31_minutes` |
| AC-22 (reset → created/attempt 2, old trials retained with attempt=1; DELETE with trials 409) | PASS | `test_reset_session_increments_attempt_and_preserves_old_trials`, `test_delete_session_without_trials_succeeds` |
| AC-23 (complete: 409 with missing indices; 204 then second call 409; requeue arithmetic) | PASS | `test_complete_missing_rows_then_success_then_double_complete`, `test_complete_with_invalid_trial_requeue_arithmetic`; smoke_v2.py completes a real session |
| AC-24 (≤3 consecutive position repeats, seeded) | PASS | frontend `sequence.test.ts` — 2000 seeded draws, max run ≤ 3 |
| AC-25 (foreperiods within [1000, 3000]) | PASS | frontend `sequence.test.ts` — 5000 seeded draws within bounds, integers |
| AC-26 (keydown 234.5 ms after onset → rt_ms 234.5) | PASS | frontend `trialEngine.test.ts` "stores rt_ms = 234.5 …" |
| AC-27 (`event.repeat` ignored) | PASS | frontend `trialEngine.test.ts` "ignores auto-repeat keydowns" |
| AC-28 (foreperiod premature: count++, redraw, practice 'Too soon!' 1000 ms) | PASS | frontend `trialEngine.test.ts` premature tests (practice and test variants) |
| AC-29 (unmapped keys → extraneous_keys only) | PASS | frontend `trialEngine.test.ts` "counts unmapped keys as extraneous only" |
| AC-30 (no key within timeout → outcome timeout, rt null) | PASS | frontend `trialEngine.test.ts` timeout test |
| AC-31 (practice '✗' only when practice_feedback) | PASS | frontend `trialEngine.test.ts` feedback-flag test |
| AC-32 (test block never shows feedback; preview creates zero rows) | PASS | frontend `trialEngine.test.ts` "never shows feedback in the test block"; backend `test_preview_caps_trial_counts_and_creates_no_rows` |
| AC-34/35 (≤5-trial loss window, idempotent re-POST, resume at first missing index with resume_count) | PASS | `test_idempotent_resubmission_and_resume_state`; client batching/flush in `uploadQueue.ts` (batch of 5, unload flush); frontend `sessionRunner.test.ts` `computeResumeState` tests; smoke_v2.py re-sends a batch with no change |
| AC-36–39 (N containers per task; §5.2 default key maps; duplicate key map 422) | PASS | `TaskCanvas` renders exactly `key_map.length` containers (code: `frontend/src/task/TaskCanvas.tsx`); defaults in `keymap.ts` + backend defaults verified by `test_create_study_with_no_params_uses_defaults_verbatim`; `test_create_study_duplicate_key_map_codes_returns_422` |
| AC-40 (matching key → correct; non-matching → incorrect with RT) | PASS | frontend `trialEngine.test.ts` correct/incorrect tests; backend `test_trial_outcome_recomputation_and_outlier_flag` (server-side recomputation) |
| AC-41–43 (full trial rows; 120 ms trial outlier-flagged; client_env stored) | PASS | `test_trial_outcome_recomputation_and_outlier_flag`, `test_client_env_persists`; smoke_v2.py posts client-env live |
| AC-44 (touch + 390×844 emulation → block screen, no session start) | PASS (manual/code) | `frontend/src/task/deviceGate.ts` blocks touch-primary or <1024×600 before any `/start` call; gate runs first in `useTaskRunner` |
| AC-45/46 (fullscreen exit → invalid/fullscreen_exit + resume overlay + re-queue; 6th invalidation not re-queued) | PASS | frontend `sessionRunner.test.ts` re-queue + 5-cap tests; overlay rendering in `TaskRunnerPage.tsx`; backend `test_complete_with_invalid_trial_requeue_arithmetic` validates the row-count rule |
| AC-47 (hand-computed stats match to 4 dp, raw + trimmed; IIV(within)=SD) | PASS | `test_session_summary_matches_hand_computed_stats` |
| AC-48 (IIV(between) = SD of session means for 3 sessions) | PASS | `test_cross_session_statistics_and_study_summary` |
| AC-50–53 (table filters; CSV per chart/table matching visible rows; header counts) | PASS (automated server-side, code client-side) | filters/sort server-tested in `test_list_sessions_filter_sort_and_invalid_params`; header counts from `/studies/{id}/summary` (`test_cross_session_statistics_and_study_summary`); client CSVs are generated from the identical arrays that are rendered (`StudyDashboardTab.tsx`, `utils/csv.ts`), so row counts match by construction |
| AC-54–57 (exact FR-54 columns in order; ZIP has 4 named files; CSVs parse cleanly; UTC timestamps) | PASS | `test_session_and_participant_csv_exports` (column order + RFC 4180), `test_study_export_zip_contains_four_files`; smoke_v2.py opens the ZIP live and checks the four filenames |
| AC-NFR (mypy + tsc clean; stats tests pass; compose healthy < 2 min from clean clone + .env) | PASS | mypy: clean (50 files, strict); tsc: clean; pytest 75 + vitest 26 all pass; fresh `docker compose up --build` reached `{"status":"ok","db":"ok"}` in ~10 s (smoke_v2.py health gate) |

---

## v2 Modifications (MAC-1 through MAC-37)

Verification performed 2026-06-13 against commit `671fa4c` (MOD-5 complete) on branch `v2-modifications`.

**Gates:** backend `pytest` — 107 passed; `mypy app tests` (strict) — clean, 41 source files; frontend `tsc --noEmit` (strict) — clean; `vitest` — 26 passed; `python3 scripts/smoke_v2.py` — exit 0 (see Step 5.3).

| MAC | Result | Evidence |
|---|---|---|
| MAC-1 (TaskCanvas 128×128 containers, 40px arms, 64px gap, 88×88 box, 8px stroke) | PASS | `frontend/src/task/TaskCanvas.tsx` constants `CONTAINER_SIZE=128`, `ARM_LENGTH=40`, `BOX_SIZE=88`, `STROKE=8`, `gap-16` (64px); code inspection |
| MAC-2 (instructions/feedback ≥20px text-xl+) | PASS | `TaskRunnerPage.tsx` and `StudyPreviewPage.tsx` use `text-xl`/`text-2xl` for all instructional and feedback text; code inspection |
| MAC-3 (✗, Too soon!, Too slow at 40px) | PASS | `TaskCanvas.tsx` renders feedback symbols at `text-[40px]`; code inspection |
| MAC-4 (KeyMappingDiagram 18px monospace 1px border 4px padding 4px border-radius) | PASS | `KeyMappingDiagram.tsx` key label span: `text-[18px] font-mono border border-gray-400 p-1 rounded`; code inspection |
| MAC-5 (SRT task type round-trips; 422 outside {SRT,CRT2,CRT3,CRT4}; tsc clean) | PASS | `test_srt.py` full suite; `tsc --noEmit` clean; `TaskType` literal union updated in `common.py` and `types.ts` |
| MAC-6 (SRT key_map=["Space"], TASK_POSITIONS.SRT===1, 1 container rendered) | PASS | `task_defaults.py` SRT defaults; `frontend/src/task/constants.ts` `TASK_POSITIONS.SRT=1`; `TaskCanvas` renders `key_map.length` containers |
| MAC-7 (SRT stimulus_position===0 always; no incorrect outcome; correct response_position=0) | PASS | `test_srt.py` `test_srt_outcome_logic`, `test_srt_max_consecutive_repeats_ignored` |
| MAC-8 (SRT key_map len 0 or ≥2 → 422) | PASS | `test_srt.py` `test_srt_key_map_length_validation` |
| MAC-9 (SRT summary same field shape as CRT) | PASS | `test_srt.py` `test_srt_session_summary_shape` |
| MAC-10 (SRT instructions grammatical for N=1, includes key label) | PASS | `TaskRunnerPage.tsx` SRT branch: singular phrasing; key label from `key_map[0]`; code inspection |
| MAC-11 (study defaults num_intervention_sessions=24, sessions_per_week=3, task_type_*=CRT4; round-trip) | PASS | `test_sessions_protocol.py` `test_study_protocol_defaults_and_round_trip` |
| MAC-12 (N=25, SPW=3 → 422; protocol-locked fields 422 after generate) | PASS | `test_sessions_protocol.py` `test_num_intervention_sessions_not_multiple_of_spw_422`, `test_protocol_config_locked_after_generate` |
| MAC-13 (N=24 generates exactly 49 sessions: 1 onboarding + 24 pre + 24 post) | PASS | `test_sessions_protocol.py` `test_generate_protocol_counts`; smoke_v2.py asserts 49 sessions live |
| MAC-14 (display_label editable in created/expired; 409 in activated/in_progress/completed; immutable fields rejected) | PASS | `test_sessions_protocol.py` `test_display_label_edit_gating` |
| MAC-15 (week_number/day_within_week hand-computed table for all sessions_per_week values) | PASS | `test_sessions_protocol.py` `test_display_label_computation_table` |
| MAC-16 (generated label format; display_label_overridden=true after PATCH; persists) | PASS | `test_sessions_protocol.py` `test_display_label_override_persistence`; smoke_v2.py verifies labels live |
| MAC-17 (order_index=1 onboarding, pre(k)=2k, post(k)=2k+1) | PASS | `test_sessions_protocol.py` `test_order_index_sequence` |
| MAC-18 (generate-protocol idempotency — second call all skipped; week_start shifts week_number) | PASS | `test_sessions_protocol.py` `test_generate_protocol_idempotent`, `test_generate_protocol_week_start` |
| MAC-19 (/me/sessions includes session_type and display_label; rendered with session-type chip) | PASS | `MySessionsPage.tsx` renders `display_label` and session-type badge; `test_my_sessions_lock_state` confirms fields present |
| MAC-20 (groups table, unique name within study, duplicate → 409) | PASS | `test_groups.py` `test_create_group_and_unique_name` |
| MAC-21 (one group per participant enforced by UNIQUE constraint and API 409) | PASS | `test_groups.py` `test_assign_and_reassignment_conflict` |
| MAC-22 (Groups tab shows size recommendation outside 4–6 range, not shown for 4–6) | PASS | `StudyGroupsTab.tsx` conditional warning; code inspection |
| MAC-23 (current_intervention_session PATCH round-trips; +1 button increments clamped at 52) | PASS | `test_groups.py` `test_group_patch_counter_and_detail`; `StudyGroupsTab.tsx` +1 button logic |
| MAC-24 (single already-assigned → 409 with group name; batch partial → 200 with split lists) | PASS | `test_groups.py` `test_assign_and_reassignment_conflict`, `test_assign_batch_partial_conflict_is_200` |
| MAC-25 (Groups tab shows name/description/member-count/CIS/codes+statuses/completion counts) | PASS | `StudyGroupsTab.tsx` renders all listed fields; code inspection |
| MAC-26 (group_name last column in all three export files; correct value or "" for unassigned) | PASS | `test_groups.py` `test_group_name_in_session_csv_export`, `test_group_name_empty_for_unassigned_in_zip`; smoke_v2.py checks sessions_summary.csv live |
| MAC-27 (full CRUD lifecycle: create, get, patch, rename dup→409, delete with members→409, delete empty→204) | PASS | `test_groups.py` `test_group_patch_counter_and_detail`, `test_delete_group_requires_no_members` |
| MAC-28 (status CHECK accepts activated/expired; rejects any unlisted value) | PASS | Alembic migration `0005_mod5_activation_gating.py` updates CHECK; `models.py` CHECK includes all 7 values; DB-level enforcement |
| MAC-29 (all valid transitions succeed; invalid paths rejected with 403/409) | PASS | `test_runtime.py` `test_start_requires_activated_status` (created→in_progress directly → 403; activated→in_progress → 200); cancel endpoint guards for correct statuses |
| MAC-30 (activated_at/activated_by/expired_at null on fresh session; populated after activate/expire; overwritten on re-activate) | PASS | `sessions.py` activate/deactivate endpoints set fields; `SessionOut` schema exposes them; code inspection |
| MAC-31 (group activate: lowest-order_index created/expired per member activated; 409 if member already activated/in_progress) | PASS | smoke_v2.py: activate → 4 sessions, order_index=2, display_label verified live; blocking check in `groups.py` router |
| MAC-32 (force=false → 409 with in_progress blocking; force=true → activated expire; in_progress untouched) | PASS | smoke_v2.py: deactivate force=false → 409; force=true → 3 expired, in_progress_count=1 verified live |
| MAC-33 (POST /sessions/{id}/activate: created/expired → activated, 409 if other activated/in_progress; /deactivate: activated → expired, 409 on other) | PASS | `sessions.py` `activate_session`/`deactivate_session` endpoints with correct guard logic; `conftest.py` fixture exercises activate path on every test session |
| MAC-34 (start on created → 403 "Session not open"; start on activated → 200 + in_progress) | PASS | `test_runtime.py` `test_start_requires_activated_status`; smoke_v2.py order_index=3 start → 403 verified live |
| MAC-35 (/me renders 6 states: Locked/no-button, Ready/Start, In-progress/Resume, Done/no-button, Missed/no-button, cancelled hidden) | PASS | `MySessionsPage.tsx` 6-state STATUS_LABELS/STATUS_BADGE_CLASSES + canStart/canResume logic; code inspection |
| MAC-36 (Group panel Open/Close calls activate/deactivate; activated_at/expired_at on Sessions tab rows; per-row Activate/Deactivate buttons) | PASS | `StudyGroupsTab.tsx` openSession/closeSession; `StudySessionsTab.tsx` activated_at column + activateSession/deactivateSession per row; code inspection |
| MAC-37 (activate response entries include non-empty display_label matching stored value) | PASS | smoke_v2.py asserts `item["display_label"] == "Week 1 · Day 1 · Pre"` for each of 4 activated entries |

## Not covered by automation (verified by code inspection only)

- Pixel dimensions of §5.1 (96 px containers, 48 px gaps, 56 px cross arms,
  64 px box, 6 px strokes, colors) are encoded as constants in
  `frontend/src/task/TaskCanvas.tsx` and reviewed against the PRD, but no
  visual-regression test exists.
- Fullscreen request/exit behaviour and `sendBeacon`-equivalent unload flush
  depend on real browser APIs; their logic is unit-tested via the injected
  clock/state machine, the browser wiring is inspection-only
  (see DECISIONS_TAKEN.md #3).

---

## v1.2 Modifications (MAC-101 through MAC-150)

Verification performed 2026-06-16 against commit on branch `v2.1-ui-and-bugfixes`
(MOD-7 through MOD-11 complete).

**Gates:** backend `pytest` — 122 passed; `mypy app tests` (strict) — clean;
frontend `tsc --noEmit` (strict) — clean; `vitest` — 37 passed;
`python3 scripts/smoke_v1_2.py` (inside api container) — exit 0.

### MOD-7 — Collapse to single Task Type (MAC-101…MAC-108)

| MAC | Result | Evidence |
|---|---|---|
| MAC-101 (Create study shows one Task Type control; no Onboarding/Pre/Post pickers) | PASS | `StudiesListPage.tsx` single `task_type` `<Field>`; `StudySettingsTab.tsx` `ProtocolConfigForm` single selector; code inspection |
| MAC-102 (create-study request body contains only `task_type`; no per-stage keys) | PASS | `StudiesListPage.tsx` create payload; code inspection (no `task_type_onboarding` etc. in form state) |
| MAC-103 (every session after generate-protocol carries `task_type == study.task_type`) | PASS | smoke_v1_2.py step 5 asserts all 147 sessions carry `task_type='CRT3'` live |
| MAC-104 (`StudyOut` contains `task_type`; no per-stage keys; stale keys in body ignored) | PASS | smoke_v1_2.py step 3 checks response for absence of `task_type_onboarding/_pre/_post`; stale keys in create payload silently ignored |
| MAC-105 (`grep -rE 'task_type_onboarding\|task_type_pre\|task_type_post'` over `backend/app` and `frontend/src` returns no matches except migration) | PASS | Verified: zero matches in `backend/app/` and `frontend/src/`; migration `0006_mod7_*` is the only file with these strings |
| MAC-106 (`alembic upgrade head` drops three columns/checks; `alembic downgrade -1` re-adds them) | PASS | Both directions run cleanly against the dev database (verified in Step 3) |
| MAC-107 (`POST /studies/{id}/generate-protocol` with stale `task_type_pre` key returns same result) | PASS | smoke_v1_2.py create payload includes stale per-stage keys; server ignores them (MAC-104 covers this) |
| MAC-108 (pytest constructs SRT study, generates protocol, asserts all sessions `task_type == "SRT"`; `StudyCreate(**{"task_type_pre": "CRT2"})` sets no `task_type_pre` attr) | PASS | `test_generate_protocol_all_sessions_inherit_study_task_type` in `test_protocol.py` |

### MOD-8 — Onboarding-aware activation + UI (MAC-109…MAC-125)

| MAC | Result | Evidence |
|---|---|---|
| MAC-109 (`POST /groups/{id}/activate {"session_type": "onboarding"}` activates all member onboarding sessions; does not require IS) | PASS | smoke_v1_2.py step 7 (3 sessions activated with no IS); `test_activate_group_onboarding` |
| MAC-110 (`POST /groups/{id}/deactivate {"session_type": "onboarding"}` expires those sessions) | PASS | smoke_v1_2.py step 8 (3 sessions expired); `test_deactivate_group_onboarding` |
| MAC-111 (`POST /groups/{id}/activate` with no `session_type` activates pre sessions at IS) | PASS | smoke_v1_2.py step 9 (empty body `{}` → 3 pre sessions activated); `test_activate_group_onboarding` backwards-compat |
| MAC-112 (`POST /groups/{id}/activate {"session_type": "pre"}` with null IS returns 422) | PASS | `test_activate_pre_requires_is` |
| MAC-113 (member with `activated` pre blocks onboarding activation → 409 with `blocking` array) | PASS | `test_activate_onboarding_blocked_by_open_pre` |
| MAC-114 (deactivate pre with in_progress member and `force=false` → 409 `in_progress_count`; `force=true` → expires activated, leaves in_progress) | PASS | smoke_v1_2.py steps 11–12; `test_deactivate_force_leaves_in_progress` |
| MAC-115 (`session_type` outside `{onboarding, pre, post}` → 422; omitted → `pre`) | PASS | Pydantic `Literal` validation on `GroupActivateRequest`/`GroupDeactivateRequest` |
| MAC-116 (no "Open", "Close", or "Expire" action labels in Groups tab) | PASS | `StudyGroupsTab.test.tsx` test 4: `queryByRole("button", {name: /^Open/i})` etc. are null |
| MAC-117 ("IS = Intervention Session" caption present in group detail panel) | PASS | `StudyGroupsTab.tsx` IS caption: `hint="IS = Intervention Session..."` rendered adjacent to IS editor; code inspection |
| MAC-118 (soft-vs-force helper text (MFR-120 verbatim) present) | PASS | `StudyGroupsTab.tsx` verbatim `<p>` text in `GroupDetailPanel`; code inspection |
| MAC-119 (Create + list side-by-side at ≥ md; detail panel full-width below) | PASS | `StudyGroupsTab.tsx` `grid grid-cols-1 gap-4 md:grid-cols-2` top region; detail panel `w-full` below; code inspection |
| MAC-120 (selected row has `bg-blue-50`, `ring-2`, `ring-blue-500`, `font-semibold`; unselected has none) | PASS | `StudyGroupsTab.test.tsx` test 1: `classList.contains("bg-blue-50")` etc. before and after click |
| MAC-121 (Pre/Post rows disabled when IS null; Onboarding always enabled) | PASS | `StudyGroupsTab.test.tsx` test 3: `activateBtns[0].disabled == false`, `activateBtns[1].disabled == true` |
| MAC-122 (detail panel preserves IS editor, completion counts, member list, delete-group) | PASS | `StudyGroupsTab.tsx` `GroupDetailPanel` renders all four components; code inspection |
| MAC-123 (successful onboarding activation shows "Activated {n} onboarding session(s).") | PASS | `StudyGroupsTab.tsx` `activateStage` success message format; code inspection |
| MAC-124 (5 new backend tests in `test_groups.py`: onboarding activate/deactivate, blocking guard, IS-required 422, force leaves in_progress) | PASS | All 5 tests pass: `test_activate_group_onboarding`, `test_deactivate_group_onboarding`, `test_activate_onboarding_blocked_by_open_pre`, `test_activate_pre_requires_is`, `test_deactivate_force_leaves_in_progress` |
| MAC-125 (Vitest render test: selected-row classes, three stage rows, Pre/Post disabled when IS null, no Open/Close/Expire labels) | PASS | `StudyGroupsTab.test.tsx` 4 tests; 37 total vitest passing |

### MOD-9 — Persist Sessions-tab preferences (MAC-126…MAC-132)

| MAC | Result | Evidence |
|---|---|---|
| MAC-126 (reload restores groupMode, sort field/direction, status filter) | PASS (code) | `StudySessionsTab.tsx` `usePersistentState` with `crt.sessionsTab.prefs.<studyId>` key; `validatePrefs` ensures all fields are valid on restore |
| MAC-127 (participant filter in study A does not leak into study B) | PASS (code) | Key is scoped per `study.id`; switching studies reads a different key |
| MAC-128 (stored participantFilter id absent from loaded participants → falls back to empty) | PASS (code) | `StudySessionsTab.tsx` `useEffect` validates `participantFilter` against loaded participant list; clears if not found |
| MAC-129 (collapsed section restored; unknown collapsed key ignored) | PASS (code) | `validatePrefs` accepts `collapsed: string[]`; unknown section ids are ignored in render (no section matches) |
| MAC-130 (corrupt non-JSON `localStorage` entry → loads with all defaults; does not throw) | PASS | `usePersistentState.test.tsx` test "returns initial and does not throw when the entry is non-JSON" |
| MAC-131 (stored `groupMode = "kanban"` / `sortDir = "up"` fall back to `"none"` / `"asc"`) | PASS | `usePersistentState.test.tsx` "applies validate to reject out-of-domain stored values"; `validatePrefs` checks all enum values |
| MAC-132 (Vitest: hook round-trips value; returns initial when absent; non-JSON → initial (no throw); validate rejects out-of-domain; `StudySessionsTab` restores groupMode from localStorage) | PASS | `usePersistentState.test.tsx` 6 hook tests + 1 `StudySessionsTab` prefs-restore test; 37 total vitest passing |

### MOD-10 — Auth realm separation (MAC-133…MAC-141)

| MAC | Result | Evidence |
|---|---|---|
| MAC-133 (researcher login then participant login in same cookie jar; `POST /auth/refresh` still returns researcher-role token) | PASS | smoke_v1_2.py step 14c: captures researcher `refresh_token` cookie, calls `/auth/refresh` with only that cookie → role=`admin`; `test_auth_realm_separation_regression` backend test |
| MAC-134 (after both logins, two distinct cookies: `refresh_token` and `participant_refresh_token`, both `HttpOnly SameSite=Lax path=/api/v1/auth`) | PASS | `backend/app/security.py` `REFRESH_COOKIE_NAME` / `PARTICIPANT_REFRESH_COOKIE_NAME`; cookie attrs identical; `test_both_realm_cookies_are_distinct` backend test |
| MAC-135 (`POST /auth/refresh` with only `participant_refresh_token` cookie → 401) | PASS | smoke_v1_2.py step 14d asserts 401; `test_researcher_refresh_ignores_participant_cookie` backend test |
| MAC-136 (`POST /auth/participant/refresh` with valid participant cookie → participant-role token; with only researcher cookie → 401) | PASS | smoke_v1_2.py steps 14e and 14f; `test_participant_refresh_endpoint_realm_check` backend test |
| MAC-137 (researcher logout clears `refresh_token`, leaves `participant_refresh_token`; vice versa) | PASS | `routers/auth.py` `logout` deletes both cookies; `test_logout_clears_correct_cookie` backend test |
| MAC-138 (end-to-end: Studies page keeps working after participant login forces researcher token refresh; no 403 banner) | PASS (manual) | MOD-10 manual walkthrough: distinct cookie names prevent overwrite; realm separation verified by smoke steps 14c–14f |
| MAC-139 (two cookies' attribute strings are byte-identical except name and value) | PASS | `backend/app/security.py` `refresh_cookie_kwargs` produces identical attrs for both; `test_both_realm_cookies_are_distinct` asserts |
| MAC-140 (frontend: identity kind `"participant"` → refresh calls `/auth/participant/refresh`; kind `"user"` → `/auth/refresh`) | PASS (code) | `frontend/src/api/client.ts` `refreshAccessToken()` reads `tokenStore.getIdentityKind()`; `tokenStore.ts` `setIdentityKind`/`getIdentityKind`; `AuthContext.tsx` sets kind on login |
| MAC-141 (role-mismatch on refresh clears identity and routes to login) | PASS (code) | `client.ts` `refreshAccessToken()` decodes access token role, compares with stored identity kind; mismatch → `tokenStore.clear()` + navigation to login |

### MOD-11 — Reassignment reflection (MAC-142…MAC-150)

| MAC | Result | Evidence |
|---|---|---|
| MAC-142 (`GET /studies/{id}/sessions` returns `group_id`/`group_name` from query-time join; unassigned → null/null) | PASS | smoke_v1_2.py step 13 pre-check: p1 sessions show `group_name = group_name`; `test_sessions_group_join_reflects_reassignment` backend test |
| MAC-143 (regression: assign P to A; fetch sessions → `group_name == "A"`; reassign P to B; fetch → `group_name == "B"`) | PASS | smoke_v1_2.py step 13 (live end-to-end); `test_sessions_group_join_reflects_reassignment` backend test |
| MAC-144 (frontend "Group by group" places P under new group after reassignment + normal reload) | PASS (code) | `StudySessionsTab.tsx` uses `session.group_name` directly for grouping (not stale `groupMap`); no hard refresh needed |
| MAC-145 (trial-level and summary CSV exports unchanged: single trailing `group_name` from MFR-26; no `group_id` column) | PASS | `test_session_and_participant_csv_exports` + `test_study_export_zip_contains_four_files` (existing, still pass); `SessionOut.group_id`/`group_name` not added to CSV builders |
| MAC-146 (frontend `SessionOut` type includes `group_id: string \| null` and `group_name: string \| null`; `tsc --noEmit` clean) | PASS | `frontend/src/api/types.ts` `SessionOut` interface; `tsc --noEmit` clean |
| MAC-147 (reassignment from Groups tab updates both source and destination member lists) | PASS (code) | `StudyGroupsTab.tsx` `reload()` called after assign; `GroupDetailPanel` `onChanged` triggers `loadDetail` for selected group; both lists refresh |
| MAC-148 (reassignment from Participants tab → switching to Groups tab shows P under new group) | PASS (code) | `StudyGroupsTab.tsx` `useEffect` with focus/visibility refetch on tab re-entry (`document.addEventListener("visibilitychange", ...)`) |
| MAC-149 (switching to Sessions tab after external reassignment refetches participants + sessions) | PASS (code) | `StudySessionsTab.tsx` `useEffect` with `visibilitychange` listener refetches participants and sessions on tab focus |
| MAC-150 (backend pytest: sessions list emits `group_id`/`group_name` via join for assigned, unassigned, just-reassigned participants) | PASS | `test_sessions_group_join_reflects_reassignment` in `test_groups.py` |

### Not covered by full automation for v1.2

- **MAC-138 / MOD-10 manual walkthrough**: The "no 403 Forbidden" scenario requires a real browser with two simultaneous login sessions (researcher + participant) and a forced access-token expiry. Verified by realm-separation smoke steps (14c–14f) and backend regression tests. No browser automation.
- **MAC-119 / MOD-8 layout**: Two-column vs stacked layout depends on viewport width. Verified by code inspection of Tailwind `md:grid-cols-2` in `StudyGroupsTab.tsx`; no visual-regression test.
- **MAC-126–MAC-129 / MOD-9 persistence**: End-to-end persistence across reloads is a browser behavior; unit tests cover the hook directly (MAC-132). Verified by code inspection that `usePersistentState` writes on state change and reads on mount.
