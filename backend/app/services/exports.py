"""Row builders for CSV/ZIP exports (FR-54/55/56)."""

from __future__ import annotations

import datetime

from app.models import Participant, Study, Trial
from app.models import Session as SessionModel
from app.schemas.statistics import ParticipantSummaryOut, SessionSummaryOut
from app.services.csv_export import iso_utc

TRIAL_COLUMNS = [
    "study_name",
    "study_id",
    "task_type",
    "participant_code",
    "session_code",
    "session_order",
    "attempt",
    "block",
    "trial_index",
    "stimulus_position",
    "foreperiod_ms",
    "key_pressed",
    "response_position",
    "outcome",
    "rt_ms",
    "premature_count",
    "extraneous_keys",
    "invalid_reason",
    "outlier_flag",
    "stimulus_onset_client_ms",
    "session_started_at_iso",
    "session_completed_at_iso",
    "group_name",  # MOD-4 / MFR-26 (trailing column)
]


def trial_sort_key(trial: Trial) -> tuple[int, int, int]:
    """Practice before test, then by trial index, within each attempt."""
    return (trial.attempt, 0 if trial.block == "practice" else 1, trial.trial_index)


def trial_row(
    study: Study,
    participant: Participant,
    session: SessionModel,
    trial: Trial,
    group_name: str = "",
) -> list[object]:
    return [
        study.name,
        str(study.id),
        session.task_type,
        participant.code,
        session.code,
        session.order_index,
        trial.attempt,
        trial.block,
        trial.trial_index,
        trial.stimulus_position,
        trial.foreperiod_ms,
        trial.key_pressed,
        trial.response_position,
        trial.outcome,
        trial.rt_ms,
        trial.premature_count,
        trial.extraneous_keys,
        trial.invalid_reason,
        trial.outlier_flag,
        trial.stimulus_onset_client_ms,
        iso_utc(session.started_at),
        iso_utc(session.completed_at),
        group_name,
    ]


SESSION_SUMMARY_COLUMNS = [
    "participant_code",
    "session_code",
    "session_order",
    "attempt",
    "status",
    "n_trials",
    "n_correct",
    "accuracy_pct",
    "n_timeouts",
    "n_premature",
    "n_invalid",
    "n_outliers_flagged",
    "mean_rt_ms_raw",
    "median_rt_ms_raw",
    "sd_rt_ms_raw",
    "cov_raw",
    "iiv_within_ms_raw",
    "mean_rt_ms_trim",
    "median_rt_ms_trim",
    "sd_rt_ms_trim",
    "cov_trim",
    "iiv_within_ms_trim",
    "started_at_iso",
    "completed_at_iso",
    "group_name",  # MOD-4 / MFR-26 (trailing column)
]


def session_summary_row(
    participant: Participant,
    session: SessionModel,
    summary: SessionSummaryOut,
    group_name: str = "",
) -> list[object]:
    raw, trimmed = summary.raw, summary.trimmed
    return [
        participant.code,
        session.code,
        session.order_index,
        session.attempt,
        session.status,
        summary.n_trials,
        summary.n_correct,
        summary.accuracy_pct,
        summary.n_timeouts,
        summary.n_premature,
        summary.n_invalid,
        summary.n_outliers_flagged,
        raw.mean_rt_ms,
        raw.median_rt_ms,
        raw.sd_rt_ms,
        raw.cov,
        raw.iiv_within_ms,
        trimmed.mean_rt_ms,
        trimmed.median_rt_ms,
        trimmed.sd_rt_ms,
        trimmed.cov,
        trimmed.iiv_within_ms,
        iso_utc(session.started_at),
        iso_utc(session.completed_at),
        group_name,
    ]


PARTICIPANT_SUMMARY_COLUMNS = [
    "participant_code",
    "n_completed_sessions",
    "mean_of_session_means_ms_raw",
    "iiv_between_ms_raw",
    "cov_between_raw",
    "mean_of_session_means_ms_trim",
    "iiv_between_ms_trim",
    "cov_between_trim",
    "group_name",  # MOD-4 / MFR-26 (trailing column)
]


def participant_summary_row(
    summary: ParticipantSummaryOut, group_name: str = ""
) -> list[object]:
    raw, trimmed = summary.cross_session_raw, summary.cross_session_trimmed
    return [
        summary.participant_code,
        summary.n_completed_sessions,
        raw.mean_of_session_means_ms,
        raw.iiv_between_ms,
        raw.cov_between,
        trimmed.mean_of_session_means_ms,
        trimmed.iiv_between_ms,
        trimmed.cov_between,
        group_name,
    ]


DEMOGRAPHICS_COLUMNS = [
    "participant_code",
    "session_code",
    "field_label",
    "field_type",
    "value",
    "answered_at_iso",
]


def demographics_row(
    participant_code: str,
    session_code: str,
    field_label: str,
    field_type: str,
    value: str,
    answered_at: datetime.datetime,
) -> list[object]:
    return [participant_code, session_code, field_label, field_type, value, iso_utc(answered_at)]
