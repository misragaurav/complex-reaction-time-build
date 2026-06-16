// Mirrors backend/app/schemas/*.py. Keep field names/shapes in sync with the
// Pydantic models -- they are the source of truth.

// ---- common.py --------------------------------------------------------------

export type TaskType = "SRT" | "CRT2" | "CRT3" | "CRT4"; // MOD-2: SRT added

export interface TaskParams {
  task_type: TaskType;
  practice_trials: number;
  test_trials: number;
  foreperiod_min_ms: number;
  foreperiod_max_ms: number;
  response_timeout_ms: number;
  iti_ms: number;
  key_map: string[];
  practice_feedback: boolean;
  feedback_duration_ms: number;
  max_consecutive_repeats: number;
  outlier_low_ms: number;
  outlier_high_ms: number;
  show_progress: boolean;
  instructions_text: string;
}

export type TaskParamsInput = Partial<TaskParams>;

// ---- auth.py -----------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  user: UserPublic;
}

export interface AccessTokenResponse {
  access_token: string;
}

export interface ParticipantLoginRequest {
  code: string;
  password: string;
}

export interface ParticipantPublic {
  id: string;
  code: string;
  study_name: string;
}

export interface ParticipantTokenResponse {
  access_token: string;
  participant: ParticipantPublic;
}

export interface ParticipantCheckRequest {
  code: string;
}

export interface ParticipantCheckResponse {
  password_set: boolean;
}

export interface ParticipantSetPasswordRequest {
  code: string;
  password: string;
}

// ---- users.py -----------------------------------------------------------------

export type UserRole = "admin" | "researcher";

export interface UserCreate {
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
}

export interface UserUpdate {
  full_name?: string;
  email?: string;
  role?: UserRole;
  is_active?: boolean;
  password?: string;
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ---- studies.py ---------------------------------------------------------------

export interface StudyCreate {
  name: string;
  description?: string | null;
  task_type: TaskType;
  params?: TaskParamsInput | null;
  // MOD-3 (optional; server-defaulted to 24 / 3).
  num_intervention_sessions?: number;
  sessions_per_week?: number;
}

export interface StudyUpdate {
  name?: string;
  description?: string | null;
  params?: TaskParamsInput | null;
  is_archived?: boolean;
  // MOD-3 (subject to the post-generation lock).
  num_intervention_sessions?: number;
  sessions_per_week?: number;
}

export interface StudyCounts {
  participants: number;
  sessions_total: number;
  sessions_completed: number;
  completion_pct: number;
}

export interface StudyOut {
  id: string;
  name: string;
  description: string | null;
  task_type: TaskType;
  params: TaskParams;
  // MOD-3 protocol configuration.
  num_intervention_sessions: number;
  sessions_per_week: number;
  protocol_locked: boolean;
  created_by: string;
  is_archived: boolean;
  params_locked: boolean;
  counts: StudyCounts;
  created_at: string;
  updated_at: string;
}

// MOD-3 protocol generation (API #33).
export interface GenerateProtocolRequest {
  participant_ids?: string[];
  num_intervention_sessions?: number;
  week_start?: number;
}

export interface ProtocolCreatedItem {
  participant_id: string;
  code: string;
  session_count: number;
}

export interface ProtocolSkippedItem {
  participant_id: string;
  code: string;
  reason: string;
}

export interface GenerateProtocolResponse {
  created: ProtocolCreatedItem[];
  skipped: ProtocolSkippedItem[];
}

// ---- demographics.py -----------------------------------------------------------

export type DemographicFieldType = "text" | "number" | "single_choice" | "boolean";
export type DemographicFrequency = "once" | "every_session";

export interface DemographicFieldCreate {
  label: string;
  field_type: DemographicFieldType;
  options?: string[] | null;
  required?: boolean;
  frequency: DemographicFrequency;
}

export interface DemographicFieldUpdate {
  label?: string;
  options?: string[] | null;
  required?: boolean;
  frequency?: DemographicFrequency;
  display_order?: number;
}

export interface DemographicFieldOut {
  id: string;
  study_id: string;
  label: string;
  field_type: DemographicFieldType;
  options: string[] | null;
  required: boolean;
  frequency: DemographicFrequency;
  display_order: number;
  is_retired: boolean;
  has_responses: boolean;
  created_at: string;
}

/** Participant-facing view of a due demographic field (API #20). */
export interface DemographicFieldPublic {
  id: string;
  label: string;
  field_type: DemographicFieldType;
  options: string[] | null;
  required: boolean;
}

export interface DemographicAnswerIn {
  field_id: string;
  value: string;
}

export interface DemographicAnswersRequest {
  answers: DemographicAnswerIn[];
}

export interface DemographicResponseOut {
  participant_code: string;
  session_code: string | null;
  field_label: string;
  field_type: DemographicFieldType;
  value: string;
  answered_at_iso: string;
}

// ---- participants.py -----------------------------------------------------------

export interface ParticipantCreateByCount {
  count: number;
  prefix?: string;
}

export interface ParticipantCreateByCodes {
  codes: string[];
}

export type ParticipantCreate = ParticipantCreateByCount | ParticipantCreateByCodes;

export interface ParticipantOut {
  id: string;
  study_id: string;
  code: string;
  password_set: boolean;
  is_active: boolean;
  sessions_assigned: number;
  sessions_completed: number;
  // MOD-4: group assignment (null if unassigned).
  group_id: string | null;
  group_name: string | null;
  last_login_at: string | null;
  created_at: string;
}

// ---- groups.py (MOD-4) -------------------------------------------------------

export interface GroupCreate {
  name: string;
  description?: string | null;
}

export interface GroupUpdate {
  name?: string;
  description?: string | null;
  current_intervention_session?: number | null;
}

export interface GroupOut {
  id: string;
  study_id: string;
  name: string;
  description: string | null;
  current_intervention_session: number | null;
  member_count: number;
  created_at: string;
}

export interface GroupMember {
  participant_id: string;
  code: string;
  is_active: boolean;
  sessions_assigned: number;
  sessions_completed: number;
}

export interface GroupCompletionStats {
  total_assigned: number;
  completed_pre_overall: number;
  completed_post_overall: number;
  completed_pre_current: number;
  completed_post_current: number;
}

export interface GroupDetailOut extends GroupOut {
  members: GroupMember[];
  completion: GroupCompletionStats;
}

export interface GroupAssignRequest {
  participant_ids: string[];
}

export interface ReassignedItem {
  participant_id: string;
  code: string;
  previous_group_name: string;
  new_group_name: string;
}

export interface BlockedItem {
  participant_id: string;
  code: string;
  current_group_name: string;
  reason: string;
}

export interface GroupAssignResponse {
  assigned: { participant_id: string; code: string }[];
  conflicts: { participant_id: string; code: string; current_group_name: string }[];
  reassigned: ReassignedItem[];
  blocked: BlockedItem[];
}

// MOD-5: group activation/deactivation types (MFR-31/32).
export interface GroupActivateRequest {
  // MOD-8: extended to include "onboarding" (MFR-110).
  session_type?: "onboarding" | "pre" | "post";
}

export interface GroupActivatedItem {
  participant_id: string;
  code: string;
  session_id: string;
  display_label: string;
  session_type: string;
  order_index: number;
}

export interface GroupActivateResponse {
  activated: GroupActivatedItem[];
  session_type: string;
}

export interface BlockingItem {
  participant_id: string;
  code: string;
  session_id: string;
  status: string;
  session_type: string;
  display_label: string;
}

export interface GroupDeactivateRequest {
  // MOD-8: session_type mirrors GroupActivateRequest (MFR-110).
  session_type?: "onboarding" | "pre" | "post";
  force?: boolean;
}

export interface GroupExpiredItem {
  participant_id: string;
  code: string;
  session_id: string;
  display_label: string;
}

export interface GroupDeactivateResponse {
  expired: GroupExpiredItem[];
  in_progress_count: number;
}

/** `{is_active?, reset_password?:true}` per API #13. */
export interface ParticipantUpdate {
  is_active?: boolean;
  reset_password?: true;
}

// ---- sessions.py ----------------------------------------------------------------

export type SessionStatus = "created" | "activated" | "in_progress" | "completed" | "abandoned" | "expired" | "cancelled"; // MOD-5

/** FR-50 row stats: trimmed mean RT, accuracy, and outlier-flag count. */
export interface SessionStatsBrief {
  trimmed_mean_rt_ms: number | null;
  accuracy_pct: number | null;
  n_outliers_flagged: number;
}

export type SessionType = "onboarding" | "pre" | "post"; // MOD-3

export interface SessionOut {
  id: string;
  code: string;
  participant_id: string;
  participant_code: string;
  study_id: string;
  order_index: number;
  task_type: TaskType;
  params: TaskParams;
  status: SessionStatus;
  attempt: number;
  resume_count: number;
  // MOD-3 labelling fields.
  session_type: SessionType;
  intervention_session_number: number | null;
  week_number: number | null;
  day_within_week: number | null;
  display_label: string;
  display_label_overridden: boolean;
  started_at: string | null;
  completed_at: string | null;
  last_activity_at: string | null;
  activated_at: string | null; // MOD-5
  expired_at: string | null; // MOD-5
  created_at: string;
  stats: SessionStatsBrief;
  // MOD-11: group membership at query time (null when unassigned).
  group_id: string | null;
  group_name: string | null;
}

/** `{action: "reset" | "cancel"}` per API #17 (FR-22/23); MOD-3 adds the
 * `{display_label}` relabel variant. */
export interface SessionActionRequest {
  action?: "reset" | "cancel";
  display_label?: string;
}

export type SessionSortField =
  | "order_index"
  | "participant_code"
  | "status"
  | "attempt"
  | "started_at"
  | "completed_at"
  | "created_at";

export type SessionSort = SessionSortField | `-${SessionSortField}`;

/** Participant's own session list (API #19). */
export interface MySessionOut {
  id: string;
  code: string;
  order_index: number;
  task_type: TaskType;
  status: SessionStatus;
  attempt: number;
  // MOD-3 labelling (MFR-19).
  session_type: SessionType;
  display_label: string;
  started_at: string | null;
  completed_at: string | null;
  activated_at: string | null; // MOD-5
  expired_at: string | null; // MOD-5
  locked: boolean;
}

export interface StoredTrials {
  practice: number[];
  test: number[];
}

/** Response of `POST /sessions/{id}/start` (API #20). */
export interface SessionStartResponse {
  params: TaskParams;
  task_type: TaskType;
  attempt: number;
  demographics_due: DemographicFieldPublic[];
  stored_trials: StoredTrials;
}

/** Response of `POST /studies/{id}/preview` (API #32, FR-33). */
export interface PreviewResponse {
  params: TaskParams;
  task_type: TaskType;
}

// ---- trials.py ---------------------------------------------------------------------

export type Block = "practice" | "test";
export type Outcome = "correct" | "incorrect" | "timeout" | "invalid";
export type InvalidReason = "focus_loss" | "fullscreen_exit";

/** One row of `TrialIn` per §8 (`POST /sessions/{id}/trials`). */
export interface TrialIn {
  client_uuid: string;
  attempt: number;
  block: Block;
  trial_index: number;
  stimulus_position: number;
  foreperiod_ms: number;
  key_pressed: string | null;
  response_position?: number | null;
  outcome: Outcome;
  rt_ms?: number | null;
  premature_count?: number;
  extraneous_keys?: number;
  invalid_reason?: InvalidReason | null;
  stimulus_onset_client_ms?: number | null;
  response_client_ms?: number | null;
}

export interface TrialBatchRequest {
  trials: TrialIn[];
}

export interface TrialBatchResponse {
  accepted: number;
}

export interface TrialOut {
  id: number;
  client_uuid: string;
  attempt: number;
  block: Block;
  trial_index: number;
  stimulus_position: number;
  foreperiod_ms: number;
  key_pressed: string | null;
  response_position: number | null;
  outcome: Outcome;
  rt_ms: number | null;
  premature_count: number;
  extraneous_keys: number;
  invalid_reason: string | null;
  outlier_flag: boolean;
  stimulus_onset_client_ms: number | null;
  response_client_ms: number | null;
  created_at: string;
}

/** FR-43 payload, recorded once per session start. */
export interface ClientEnvIn {
  user_agent: string;
  screen_width: number;
  screen_height: number;
  device_pixel_ratio: number;
  refresh_rate_hz: number;
  timezone: string;
}

// ---- statistics.py ------------------------------------------------------------------

/** RT distribution stats for one variant (raw or trimmed) per FR-47/D-9. */
export interface RTStats {
  n: number;
  mean_rt_ms: number | null;
  median_rt_ms: number | null;
  sd_rt_ms: number | null;
  cov: number | null;
  iiv_within_ms: number | null;
}

/** Per-session summary (FR-47), test-block trials of the latest attempt. */
export interface SessionSummaryOut {
  session_id: string;
  attempt: number;
  n_trials: number;
  n_correct: number;
  accuracy_pct: number | null;
  n_timeouts: number;
  n_premature: number;
  n_invalid: number;
  n_outliers_flagged: number;
  raw: RTStats;
  trimmed: RTStats;
}

/** `GET /sessions/{id}/summary` response: FR-47 stats + the underlying trial rows. */
export interface SessionSummaryDetailOut extends SessionSummaryOut {
  trials: TrialOut[];
}

/** Across-session aggregates (FR-48), present only when >=2 completed sessions. */
export interface CrossSessionStats {
  mean_of_session_means_ms: number | null;
  iiv_between_ms: number | null;
  cov_between: number | null;
}

/** `GET /participants/{id}/summary` response (FR-48). */
export interface ParticipantSummaryOut {
  participant_id: string;
  participant_code: string;
  n_completed_sessions: number;
  sessions: SessionSummaryOut[];
  cross_session_raw: CrossSessionStats;
  cross_session_trimmed: CrossSessionStats;
}

/** Group mean +/- SD of a per-session metric across the study (FR-49). */
export interface GroupStats {
  mean: number | null;
  sd: number | null;
  n: number;
}

/** `GET /studies/{id}/summary` response (FR-49 + dashboard chart data for FR-50/51). */
export interface StudySummaryOut {
  study_id: string;
  n_participants: number;
  n_sessions_total: number;
  n_sessions_completed: number;
  completion_pct: number;
  trimmed_mean_rt: GroupStats;
  trimmed_sd_rt: GroupStats;
  accuracy_pct: GroupStats;
  participants: ParticipantSummaryOut[];
}

// ---- misc API error shapes ------------------------------------------------------------

/** `detail` shape of the 409 raised by `POST /sessions/{id}/complete` when the
 * test block is incomplete. */
export interface SessionIncompleteDetail {
  message: string;
  expected_rows: number;
  missing_trial_indices: number[];
}
