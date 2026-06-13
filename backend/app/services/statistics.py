"""Summary statistics (FR-47/48/49, D-9, D-10).

All statistics are computed server-side on test-block trials of the
**latest attempt** of each session, in two variants:

- raw: all `correct` trials
- trimmed: `correct` trials with `outlier_flag = false`

SD is the *sample* standard deviation (`statistics.stdev`, n-1 denominator);
undefined (None) for n < 2. CoV = SD / mean. IIV(within) is numerically
identical to SD (D-9), surfaced under its own label.
"""

from __future__ import annotations

import statistics
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession

from app.models import Participant, Study
from app.models import Session as SessionModel
from app.models import Trial
from app.schemas.sessions import SessionStatsBrief
from app.schemas.statistics import (
    CrossSessionStats,
    GroupStats,
    ParticipantSummaryOut,
    RTStats,
    SessionSummaryOut,
    StudySummaryOut,
)
from app.schemas.trials import TrialOut

ROUND_NDIGITS = 4


def _to_float_list(values: Iterable[Any]) -> list[float]:
    return [float(v) for v in values if v is not None]


def _round(value: float | None) -> float | None:
    return round(value, ROUND_NDIGITS) if value is not None else None


def _rt_stats(rts: list[float]) -> RTStats:
    n = len(rts)
    if n == 0:
        return RTStats(n=0, mean_rt_ms=None, median_rt_ms=None, sd_rt_ms=None, cov=None, iiv_within_ms=None)

    mean = statistics.mean(rts)
    median = statistics.median(rts)
    if n >= 2:
        sd = statistics.stdev(rts)
        cov: float | None = (sd / mean) if mean else None
    else:
        sd = None
        cov = None

    return RTStats(
        n=n,
        mean_rt_ms=_round(mean),
        median_rt_ms=_round(median),
        sd_rt_ms=_round(sd),
        cov=_round(cov),
        iiv_within_ms=_round(sd),
    )


def compute_session_summary(session: SessionModel, test_trials: list[Trial]) -> SessionSummaryOut:
    """FR-47: per-session summary from the test-block trials of `session.attempt`."""
    n_trials = len(test_trials)
    n_correct = sum(1 for t in test_trials if t.outcome == "correct")
    n_timeouts = sum(1 for t in test_trials if t.outcome == "timeout")
    n_invalid = sum(1 for t in test_trials if t.outcome == "invalid")
    n_premature = sum(t.premature_count for t in test_trials)
    n_outliers = sum(1 for t in test_trials if t.outlier_flag)

    denom = n_trials - n_invalid
    accuracy_pct = _round(n_correct / denom * 100) if denom > 0 else None

    raw_rts = _to_float_list(t.rt_ms for t in test_trials if t.outcome == "correct")
    trimmed_rts = _to_float_list(
        t.rt_ms for t in test_trials if t.outcome == "correct" and not t.outlier_flag
    )

    return SessionSummaryOut(
        session_id=session.id,
        attempt=session.attempt,
        n_trials=n_trials,
        n_correct=n_correct,
        accuracy_pct=accuracy_pct,
        n_timeouts=n_timeouts,
        n_premature=n_premature,
        n_invalid=n_invalid,
        n_outliers_flagged=n_outliers,
        raw=_rt_stats(raw_rts),
        trimmed=_rt_stats(trimmed_rts),
    )


def session_stats_brief(summary: SessionSummaryOut) -> SessionStatsBrief:
    """FR-50 row stats for the sessions table."""
    return SessionStatsBrief(
        trimmed_mean_rt_ms=summary.trimmed.mean_rt_ms,
        accuracy_pct=summary.accuracy_pct,
        n_outliers_flagged=summary.n_outliers_flagged,
    )


def load_test_trials(
    db: OrmSession, sessions: list[SessionModel]
) -> dict[uuid.UUID, list[Trial]]:
    """Load test-block trials of each session's *current* attempt, grouped by session id."""
    grouped: dict[uuid.UUID, list[Trial]] = {s.id: [] for s in sessions}
    if not sessions:
        return grouped

    session_ids = [s.id for s in sessions]
    rows = (
        db.execute(
            select(Trial)
            .join(SessionModel, SessionModel.id == Trial.session_id)
            .where(
                Trial.session_id.in_(session_ids),
                Trial.block == "test",
                Trial.attempt == SessionModel.attempt,
            )
            .order_by(Trial.trial_index)
        )
        .scalars()
        .all()
    )
    for t in rows:
        grouped[t.session_id].append(t)
    return grouped


def session_summary_detail(db: OrmSession, session: SessionModel) -> tuple[SessionSummaryOut, list[Trial]]:
    """Returns (FR-47 summary, test-block trials of the current attempt)."""
    trials = load_test_trials(db, [session])[session.id]
    return compute_session_summary(session, trials), trials


def trial_to_out(trial: Trial) -> TrialOut:
    return TrialOut.model_validate(trial)


def _cross_session_stats(means: list[float]) -> CrossSessionStats:
    if len(means) < 2:
        return CrossSessionStats(mean_of_session_means_ms=None, iiv_between_ms=None, cov_between=None)
    mean_of_means = statistics.mean(means)
    sd = statistics.stdev(means)
    cov = (sd / mean_of_means) if mean_of_means else None
    return CrossSessionStats(
        mean_of_session_means_ms=_round(mean_of_means),
        iiv_between_ms=_round(sd),
        cov_between=_round(cov),
    )


def compute_participant_summary(db: OrmSession, participant: Participant) -> ParticipantSummaryOut:
    """FR-48: per-session FR-47 stats for completed sessions + cross-session aggregates."""
    completed = [s for s in participant.sessions if s.status == "completed"]
    trials_by_session = load_test_trials(db, completed)
    summaries = [compute_session_summary(s, trials_by_session[s.id]) for s in completed]

    raw_means = _to_float_list(s.raw.mean_rt_ms for s in summaries)
    trimmed_means = _to_float_list(s.trimmed.mean_rt_ms for s in summaries)

    return ParticipantSummaryOut(
        participant_id=participant.id,
        participant_code=participant.code,
        n_completed_sessions=len(completed),
        sessions=summaries,
        cross_session_raw=_cross_session_stats(raw_means),
        cross_session_trimmed=_cross_session_stats(trimmed_means),
    )


def _group_stats(values: list[float]) -> GroupStats:
    n = len(values)
    if n == 0:
        return GroupStats(mean=None, sd=None, n=0)
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if n >= 2 else None
    return GroupStats(mean=_round(mean), sd=_round(sd), n=n)


def compute_study_summary(db: OrmSession, study: Study) -> StudySummaryOut:
    """FR-49: distribution of per-session trimmed stats across the study, plus FR-51 chart data."""
    participants = (
        db.execute(
            select(Participant)
            .where(Participant.study_id == study.id)
            .order_by(Participant.created_at)
        )
        .scalars()
        .all()
    )

    participant_summaries = [compute_participant_summary(db, p) for p in participants]
    all_session_summaries = [s for ps in participant_summaries for s in ps.sessions]

    trimmed_means = _to_float_list(s.trimmed.mean_rt_ms for s in all_session_summaries)
    trimmed_sds = _to_float_list(s.trimmed.sd_rt_ms for s in all_session_summaries)
    accuracies = _to_float_list(s.accuracy_pct for s in all_session_summaries)

    n_sessions_total = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.study_id == study.id, SessionModel.status != "cancelled")
    ).scalar_one()
    n_sessions_completed = len(all_session_summaries)
    completion_pct = round(n_sessions_completed / n_sessions_total * 100, 1) if n_sessions_total else 0.0

    return StudySummaryOut(
        study_id=study.id,
        n_participants=len(participants),
        n_sessions_total=n_sessions_total,
        n_sessions_completed=n_sessions_completed,
        completion_pct=completion_pct,
        trimmed_mean_rt=_group_stats(trimmed_means),
        trimmed_sd_rt=_group_stats(trimmed_sds),
        accuracy_pct=_group_stats(accuracies),
        participants=participant_summaries,
    )
