"""Shared session state-machine helpers (FR-20, FR-21, FR-35; D-11)."""

from __future__ import annotations

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.models import DemographicField, DemographicResponse, Participant
from app.models import Session as SessionModel
from app.models import Trial

ABANDON_THRESHOLD = datetime.timedelta(minutes=30)


def _as_aware(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def apply_lazy_abandonment(db: OrmSession, session: SessionModel) -> None:
    """Mark an `in_progress` session `abandoned` if idle > 30 min (FR-21)."""
    if session.status != "in_progress" or session.last_activity_at is None:
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    if now - _as_aware(session.last_activity_at) > ABANDON_THRESHOLD:
        session.status = "abandoned"
        db.commit()
        db.refresh(session)


def get_owned_session(
    db: OrmSession, participant: Participant, session_id: uuid.UUID
) -> SessionModel:
    """Fetch a session owned by `participant`, applying lazy abandonment.

    Cancelled sessions are treated as not-found since they "disappear from
    the participant's list" (FR-23).
    """
    session = db.get(SessionModel, session_id)
    if (
        session is None
        or session.participant_id != participant.id
        or session.status == "cancelled"
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    apply_lazy_abandonment(db, session)
    return session


def earlier_incomplete_session(
    db: OrmSession, participant_id: uuid.UUID, order_index: int
) -> SessionModel | None:
    """Return the first non-cancelled, non-completed session before `order_index` (FR-20)."""
    stmt = (
        select(SessionModel)
        .where(
            SessionModel.participant_id == participant_id,
            SessionModel.order_index < order_index,
            SessionModel.status != "cancelled",
        )
        .order_by(SessionModel.order_index)
    )
    for earlier in db.execute(stmt).scalars().all():
        apply_lazy_abandonment(db, earlier)
        if earlier.status != "completed":
            return earlier
    return None


def demographics_due_for_session(
    db: OrmSession, session: SessionModel
) -> list[DemographicField]:
    """Demographic fields due now: `every_session` always, `once` only if unanswered (D-11)."""
    fields = (
        db.execute(
            select(DemographicField)
            .where(
                DemographicField.study_id == session.study_id,
                DemographicField.is_retired.is_(False),
            )
            .order_by(DemographicField.display_order)
        )
        .scalars()
        .all()
    )
    due: list[DemographicField] = []
    for field in fields:
        if field.frequency == "every_session":
            due.append(field)
        else:
            answered = db.execute(
                select(DemographicResponse.id).where(
                    DemographicResponse.participant_id == session.participant_id,
                    DemographicResponse.field_id == field.id,
                    DemographicResponse.session_id.is_(None),
                )
            ).first()
            if answered is None:
                due.append(field)
    return due


def resume_state(db: OrmSession, session: SessionModel) -> dict[str, list[int]]:
    """Stored trial indices per block for the session's current attempt (FR-35)."""
    rows = db.execute(
        select(Trial.block, Trial.trial_index).where(
            Trial.session_id == session.id,
            Trial.attempt == session.attempt,
        )
    ).all()
    return {
        "practice": sorted(r.trial_index for r in rows if r.block == "practice"),
        "test": sorted(r.trial_index for r in rows if r.block == "test"),
    }
