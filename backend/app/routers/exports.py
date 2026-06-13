"""CSV/ZIP exports (FR-54/55/56/57; API #28-30) and study preview (FR-33; API #32)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import CurrentUserDep, DbDep
from app.models import DemographicField, DemographicResponse, Participant, Study, Trial
from app.models import Session as SessionModel
from app.schemas.common import TaskParams
from app.schemas.sessions import PreviewResponse
from app.services.csv_export import build_csv, build_zip, content_disposition, csv_filename
from app.services.exports import (
    DEMOGRAPHICS_COLUMNS,
    PARTICIPANT_SUMMARY_COLUMNS,
    SESSION_SUMMARY_COLUMNS,
    TRIAL_COLUMNS,
    demographics_row,
    participant_summary_row,
    session_summary_row,
    trial_row,
    trial_sort_key,
)
from app.services.statistics import compute_participant_summary, compute_session_summary, load_test_trials

router = APIRouter(tags=["exports"])


def _session_trials(db: DbDep, session_id: uuid.UUID) -> list[Trial]:
    return list(
        db.execute(select(Trial).where(Trial.session_id == session_id)).scalars().all()
    )


@router.get("/sessions/{session_id}/export.csv")
def export_session_csv(session_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Response:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    participant = session.participant
    study = session.study
    trials = sorted(_session_trials(db, session.id), key=trial_sort_key)
    csv_text = build_csv(TRIAL_COLUMNS, [trial_row(study, participant, session, t) for t in trials])
    filename = csv_filename(study.name, f"session_{session.code}")
    return Response(content=csv_text, media_type="text/csv", headers=content_disposition(filename))


@router.get("/participants/{participant_id}/export.csv")
def export_participant_csv(participant_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Response:
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    study = participant.study
    rows = []
    for session in participant.sessions:
        for trial in sorted(_session_trials(db, session.id), key=trial_sort_key):
            rows.append(trial_row(study, participant, session, trial))

    csv_text = build_csv(TRIAL_COLUMNS, rows)
    filename = csv_filename(study.name, f"participant_{participant.code}")
    return Response(content=csv_text, media_type="text/csv", headers=content_disposition(filename))


@router.get("/studies/{study_id}/export.zip")
def export_study_zip(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Response:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    participants = (
        db.execute(select(Participant).where(Participant.study_id == study_id).order_by(Participant.created_at))
        .scalars()
        .all()
    )

    # trials.csv -- every trial row, all attempts, practice + test (FR-54).
    trial_rows = []
    for participant in participants:
        for session in participant.sessions:
            for trial in sorted(_session_trials(db, session.id), key=trial_sort_key):
                trial_rows.append(trial_row(study, participant, session, trial))
    trials_csv = build_csv(TRIAL_COLUMNS, trial_rows)

    # sessions_summary.csv -- FR-47 stats (current attempt) for every non-cancelled session.
    all_sessions = [s for p in participants for s in p.sessions if s.status != "cancelled"]
    trials_by_session = load_test_trials(db, all_sessions)
    session_rows = [
        session_summary_row(p, s, compute_session_summary(s, trials_by_session[s.id]))
        for p in participants
        for s in p.sessions
        if s.status != "cancelled"
    ]
    sessions_csv = build_csv(SESSION_SUMMARY_COLUMNS, session_rows)

    # participants_summary.csv -- FR-48 cross-session aggregates.
    participant_rows = [participant_summary_row(compute_participant_summary(db, p)) for p in participants]
    participants_csv = build_csv(PARTICIPANT_SUMMARY_COLUMNS, participant_rows)

    # demographics.csv -- FR-56, one row per answered instance.
    responses = (
        db.execute(
            select(DemographicResponse)
            .join(DemographicField, DemographicField.id == DemographicResponse.field_id)
            .where(DemographicField.study_id == study_id)
            .order_by(DemographicResponse.created_at)
        )
        .scalars()
        .all()
    )
    demographics_csv = build_csv(
        DEMOGRAPHICS_COLUMNS,
        [
            demographics_row(
                r.participant.code,
                r.session.code if r.session is not None else "",
                r.field.label,
                r.field.field_type,
                r.value,
                r.created_at,
            )
            for r in responses
        ],
    )

    zip_bytes = build_zip(
        {
            "trials.csv": trials_csv,
            "sessions_summary.csv": sessions_csv,
            "participants_summary.csv": participants_csv,
            "demographics.csv": demographics_csv,
        }
    )
    filename = csv_filename(study.name, "study", ext="zip")
    return Response(content=zip_bytes, media_type="application/zip", headers=content_disposition(filename))


@router.post("/studies/{study_id}/preview", response_model=PreviewResponse)
def preview_study(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> PreviewResponse:
    """FR-33: practice and test blocks both shortened to at most 3 trials; no DB rows created."""
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    params = dict(study.params)
    params["practice_trials"] = min(params["practice_trials"], 3)
    params["test_trials"] = min(params["test_trials"], 3)

    return PreviewResponse(params=TaskParams.model_validate(params), task_type=study.task_type)
