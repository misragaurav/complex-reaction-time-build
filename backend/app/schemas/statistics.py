from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.trials import TrialOut


class RTStats(BaseModel):
    """RT distribution stats for one variant (raw or trimmed) per FR-47/D-9."""

    n: int
    mean_rt_ms: float | None
    median_rt_ms: float | None
    sd_rt_ms: float | None
    cov: float | None
    iiv_within_ms: float | None


class SessionSummaryOut(BaseModel):
    """Per-session summary (FR-47), test-block trials of the latest attempt."""

    session_id: uuid.UUID
    attempt: int
    n_trials: int
    n_correct: int
    accuracy_pct: float | None
    n_timeouts: int
    n_premature: int
    n_invalid: int
    n_outliers_flagged: int
    raw: RTStats
    trimmed: RTStats


class SessionSummaryDetailOut(SessionSummaryOut):
    """`GET /sessions/{id}/summary` response: FR-47 stats + the underlying trial rows."""

    trials: list[TrialOut]


class CrossSessionStats(BaseModel):
    """Across-session aggregates (FR-48), present only when >=2 completed sessions."""

    mean_of_session_means_ms: float | None
    iiv_between_ms: float | None
    cov_between: float | None


class ParticipantSummaryOut(BaseModel):
    """`GET /participants/{id}/summary` response (FR-48)."""

    participant_id: uuid.UUID
    participant_code: str
    n_completed_sessions: int
    sessions: list[SessionSummaryOut]
    cross_session_raw: CrossSessionStats
    cross_session_trimmed: CrossSessionStats


class GroupStats(BaseModel):
    """Group mean +/- SD of a per-session metric across the study (FR-49)."""

    mean: float | None
    sd: float | None
    n: int


class StudySummaryOut(BaseModel):
    """`GET /studies/{id}/summary` response (FR-49 + dashboard chart data for FR-50/51)."""

    study_id: uuid.UUID
    n_participants: int
    n_sessions_total: int
    n_sessions_completed: int
    completion_pct: float
    trimmed_mean_rt: GroupStats
    trimmed_sd_rt: GroupStats
    accuracy_pct: GroupStats
    participants: list[ParticipantSummaryOut]
