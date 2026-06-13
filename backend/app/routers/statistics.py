"""Summary statistics endpoints (FR-47/48/49; API #25-27)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUserDep, DbDep
from app.models import Participant, Study
from app.models import Session as SessionModel
from app.schemas.statistics import ParticipantSummaryOut, SessionSummaryDetailOut, StudySummaryOut
from app.services.statistics import (
    compute_participant_summary,
    compute_study_summary,
    session_summary_detail,
    trial_to_out,
)

router = APIRouter(tags=["statistics"])


@router.get("/sessions/{session_id}/summary", response_model=SessionSummaryDetailOut)
def get_session_summary(
    session_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> SessionSummaryDetailOut:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    summary, trials = session_summary_detail(db, session)
    return SessionSummaryDetailOut(**summary.model_dump(), trials=[trial_to_out(t) for t in trials])


@router.get("/participants/{participant_id}/summary", response_model=ParticipantSummaryOut)
def get_participant_summary(
    participant_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> ParticipantSummaryOut:
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return compute_participant_summary(db, participant)


@router.get("/studies/{study_id}/summary", response_model=StudySummaryOut)
def get_study_summary(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> StudySummaryOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return compute_study_summary(db, study)
