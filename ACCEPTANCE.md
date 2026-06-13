# Acceptance Criteria Walkthrough (PRD §10)

Verification performed 2026-06-11 against the final build.

**Gates:** backend `pytest` — 75 passed; `mypy app tests` (strict) — clean,
50 source files; frontend `tsc --noEmit` (strict) — clean; `vitest` — 26
passed; `docker compose up --build` from a clean tree + `.env` — all services
healthy in well under 2 minutes; `python3 scripts/smoke.py` — exit 0.

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
| AC-7 (seed admin created exactly once) | PASS | `test_seed_admin_creates_exactly_one_active_admin`; also exercised live by smoke.py login |
| AC-8 (refresh after logout → 401) | PASS | `test_refresh_then_logout_then_refresh_returns_401` |
| AC-9/10/11 (defaults verbatim; params locked after start → 409; archived blocks sessions → 409) | PASS | `test_create_study_with_no_params_uses_defaults_verbatim`, `test_params_locked_after_session_started_returns_409`, `test_archived_study_rejects_new_sessions`; smoke.py asserts default params |
| AC-12–15 (single_choice without options 422; answered field label edit 409 / DELETE retires; required omission 422; answers in demographics CSV) | PASS | `test_single_choice_without_options_returns_422`, `test_answered_field_rejects_label_edit_and_delete_retires_it`, `test_required_field_missing_on_submit_returns_422`, `test_study_export_zip_contains_four_files` (demographics.csv contents) |
| AC-16 (100 unique generated codes; duplicate custom code 409) | PASS | `test_bulk_create_100_participants_unique_codes`, `test_manual_codes_creation_and_duplicate_conflict` |
| AC-17 (deactivated participant 401; data still exports) | PASS | `test_deactivated_participant_login_returns_401`, `test_deactivated_participant_login_401_but_still_listed`, export tests include all participants |
| AC-18/19 (3×2 sessions, order_index 1–2, snapshot deep-equal + immune to later study edits) | PASS | `test_create_sessions_for_multiple_participants_snapshot_and_overrides` |
| AC-20 (out-of-order start 409; UI shows locked) | PASS | `test_start_enforces_session_order_lock`, `test_my_sessions_lock_state`; UI lock rendering in `frontend/src/pages/MySessionsPage.tsx` ("Complete session N first") |
| AC-21 (31-min stale in_progress reads back abandoned) | PASS | `test_lazy_abandonment_after_31_minutes` |
| AC-22 (reset → created/attempt 2, old trials retained with attempt=1; DELETE with trials 409) | PASS | `test_reset_session_increments_attempt_and_preserves_old_trials`, `test_delete_session_without_trials_succeeds` |
| AC-23 (complete: 409 with missing indices; 204 then second call 409; requeue arithmetic) | PASS | `test_complete_missing_rows_then_success_then_double_complete`, `test_complete_with_invalid_trial_requeue_arithmetic`; smoke.py completes a real session |
| AC-24 (≤3 consecutive position repeats, seeded) | PASS | frontend `sequence.test.ts` — 2000 seeded draws, max run ≤ 3 |
| AC-25 (foreperiods within [1000, 3000]) | PASS | frontend `sequence.test.ts` — 5000 seeded draws within bounds, integers |
| AC-26 (keydown 234.5 ms after onset → rt_ms 234.5) | PASS | frontend `trialEngine.test.ts` "stores rt_ms = 234.5 …" |
| AC-27 (`event.repeat` ignored) | PASS | frontend `trialEngine.test.ts` "ignores auto-repeat keydowns" |
| AC-28 (foreperiod premature: count++, redraw, practice 'Too soon!' 1000 ms) | PASS | frontend `trialEngine.test.ts` premature tests (practice and test variants) |
| AC-29 (unmapped keys → extraneous_keys only) | PASS | frontend `trialEngine.test.ts` "counts unmapped keys as extraneous only" |
| AC-30 (no key within timeout → outcome timeout, rt null) | PASS | frontend `trialEngine.test.ts` timeout test |
| AC-31 (practice '✗' only when practice_feedback) | PASS | frontend `trialEngine.test.ts` feedback-flag test |
| AC-32 (test block never shows feedback; preview creates zero rows) | PASS | frontend `trialEngine.test.ts` "never shows feedback in the test block"; backend `test_preview_caps_trial_counts_and_creates_no_rows` |
| AC-34/35 (≤5-trial loss window, idempotent re-POST, resume at first missing index with resume_count) | PASS | `test_idempotent_resubmission_and_resume_state`; client batching/flush in `uploadQueue.ts` (batch of 5, unload flush); frontend `sessionRunner.test.ts` `computeResumeState` tests; smoke.py re-sends a batch with no change |
| AC-36–39 (N containers per task; §5.2 default key maps; duplicate key map 422) | PASS | `TaskCanvas` renders exactly `key_map.length` containers (code: `frontend/src/task/TaskCanvas.tsx`); defaults in `keymap.ts` + backend defaults verified by `test_create_study_with_no_params_uses_defaults_verbatim`; `test_create_study_duplicate_key_map_codes_returns_422` |
| AC-40 (matching key → correct; non-matching → incorrect with RT) | PASS | frontend `trialEngine.test.ts` correct/incorrect tests; backend `test_trial_outcome_recomputation_and_outlier_flag` (server-side recomputation) |
| AC-41–43 (full trial rows; 120 ms trial outlier-flagged; client_env stored) | PASS | `test_trial_outcome_recomputation_and_outlier_flag`, `test_client_env_persists`; smoke.py posts client-env live |
| AC-44 (touch + 390×844 emulation → block screen, no session start) | PASS (manual/code) | `frontend/src/task/deviceGate.ts` blocks touch-primary or <1024×600 before any `/start` call; gate runs first in `useTaskRunner` |
| AC-45/46 (fullscreen exit → invalid/fullscreen_exit + resume overlay + re-queue; 6th invalidation not re-queued) | PASS | frontend `sessionRunner.test.ts` re-queue + 5-cap tests; overlay rendering in `TaskRunnerPage.tsx`; backend `test_complete_with_invalid_trial_requeue_arithmetic` validates the row-count rule |
| AC-47 (hand-computed stats match to 4 dp, raw + trimmed; IIV(within)=SD) | PASS | `test_session_summary_matches_hand_computed_stats` |
| AC-48 (IIV(between) = SD of session means for 3 sessions) | PASS | `test_cross_session_statistics_and_study_summary` |
| AC-50–53 (table filters; CSV per chart/table matching visible rows; header counts) | PASS (automated server-side, code client-side) | filters/sort server-tested in `test_list_sessions_filter_sort_and_invalid_params`; header counts from `/studies/{id}/summary` (`test_cross_session_statistics_and_study_summary`); client CSVs are generated from the identical arrays that are rendered (`StudyDashboardTab.tsx`, `utils/csv.ts`), so row counts match by construction |
| AC-54–57 (exact FR-54 columns in order; ZIP has 4 named files; CSVs parse cleanly; UTC timestamps) | PASS | `test_session_and_participant_csv_exports` (column order + RFC 4180), `test_study_export_zip_contains_four_files`; smoke.py opens the ZIP live and checks the four filenames |
| AC-NFR (mypy + tsc clean; stats tests pass; compose healthy < 2 min from clean clone + .env) | PASS | mypy: clean (50 files, strict); tsc: clean; pytest 75 + vitest 26 all pass; fresh `docker compose up --build` reached `{"status":"ok","db":"ok"}` in ~10 s (smoke.py health gate) |

## Not covered by automation (verified by code inspection only)

- Pixel dimensions of §5.1 (96 px containers, 48 px gaps, 56 px cross arms,
  64 px box, 6 px strokes, colors) are encoded as constants in
  `frontend/src/task/TaskCanvas.tsx` and reviewed against the PRD, but no
  visual-regression test exists.
- Fullscreen request/exit behaviour and `sendBeacon`-equivalent unload flush
  depend on real browser APIs; their logic is unit-tested via the injected
  clock/state machine, the browser wiring is inspection-only
  (see DECISIONS_TAKEN.md #3).
