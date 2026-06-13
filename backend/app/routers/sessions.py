from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import CurrentParticipantDep, CurrentUserDep, DbDep
from app.models import Participant, Study, Trial
from app.models import Session as SessionModel
from app.schemas.common import merge_and_validate_params
from app.schemas.sessions import (
    MySessionOut,
    SessionActionRequest,
    SessionCreateRequest,
    SessionOut,
)
from app.services.codes import generate_session_code
from app.services.sessions import apply_lazy_abandonment
from app.services.statistics import compute_session_summary, load_test_trials, session_stats_brief

router = APIRouter(tags=["sessions"])

VALID_STATUS_FILTERS = {"created", "in_progress", "completed", "abandoned"}


def _naive(dt: datetime.datetime | None) -> datetime.datetime:
    if dt is None:
        return datetime.datetime.min
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


SORT_KEYS: dict[str, Callable[[SessionOut], Any]] = {
    "order_index": lambda s: s.order_index,
    "participant_code": lambda s: s.participant_code,
    "status": lambda s: s.status,
    "attempt": lambda s: s.attempt,
    "started_at": lambda s: _naive(s.started_at),
    "completed_at": lambda s: _naive(s.completed_at),
    "created_at": lambda s: _naive(s.created_at),
}


def _sort_sessions(sessions: list[SessionOut], sort: str | None) -> list[SessionOut]:
    if not sort:
        return sorted(sessions, key=lambda s: (s.participant_code, s.order_index))
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    key_fn = SORT_KEYS.get(field)
    if key_fn is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"invalid sort field: {field}")
    return sorted(sessions, key=key_fn, reverse=descending)


def _sessions_to_out(db: DbDep, sessions: list[SessionModel]) -> list[SessionOut]:
    if not sessions:
        return []
    trials_by_session = load_test_trials(db, sessions)
    participant_ids = {s.participant_id for s in sessions}
    participants = db.execute(
        select(Participant).where(Participant.id.in_(participant_ids))
    ).scalars().all()
    participants_by_id = {p.id: p for p in participants}

    out: list[SessionOut] = []
    for session in sessions:
        summary = compute_session_summary(session, trials_by_session[session.id])
        participant = participants_by_id[session.participant_id]
        out.append(
            SessionOut(
                id=session.id,
                code=session.code,
                participant_id=session.participant_id,
                participant_code=participant.code,
                study_id=session.study_id,
                order_index=session.order_index,
                task_type=session.task_type,
                params=session.params,
                status=session.status,
                attempt=session.attempt,
                resume_count=session.resume_count,
                started_at=session.started_at,
                completed_at=session.completed_at,
                last_activity_at=session.last_activity_at,
                created_at=session.created_at,
                stats=session_stats_brief(summary),
            )
        )
    return out


def _session_to_out(db: DbDep, session: SessionModel) -> SessionOut:
    return _sessions_to_out(db, [session])[0]


@router.post(
    "/studies/{study_id}/sessions",
    response_model=list[SessionOut],
    status_code=status.HTTP_201_CREATED,
)
def create_sessions(
    study_id: uuid.UUID, payload: SessionCreateRequest, user: CurrentUserDep, db: DbDep
) -> list[SessionOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot create sessions in an archived study"
        )

    effective_task_type = study.task_type
    param_overrides = None
    if payload.overrides is not None:
        if payload.overrides.task_type is not None:
            effective_task_type = payload.overrides.task_type
        param_overrides = payload.overrides.params

    params = merge_and_validate_params(effective_task_type, study.params, param_overrides)  # type: ignore[arg-type]

    created: list[SessionModel] = []
    for participant_id in payload.participant_ids:
        participant = db.get(Participant, participant_id)
        if participant is None or participant.study_id != study_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Participant {participant_id} not found in this study",
            )

        max_order = db.execute(
            select(func.coalesce(func.max(SessionModel.order_index), 0)).where(
                SessionModel.participant_id == participant_id
            )
        ).scalar_one()

        for i in range(payload.count):
            session = SessionModel(
                code=generate_session_code(db),
                participant_id=participant_id,
                study_id=study_id,
                order_index=max_order + i + 1,
                task_type=effective_task_type,
                params=dict(params),
                status="created",
                attempt=1,
                resume_count=0,
            )
            db.add(session)
            db.flush()
            created.append(session)

    db.commit()
    for s in created:
        db.refresh(s)
    return _sessions_to_out(db, created)


@router.get("/studies/{study_id}/sessions", response_model=list[SessionOut])
def list_sessions(
    study_id: uuid.UUID,
    user: CurrentUserDep,
    db: DbDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    participant_id: Annotated[uuid.UUID | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
) -> list[SessionOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    if status_filter is not None and status_filter not in VALID_STATUS_FILTERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"invalid status: {status_filter}"
        )

    stmt = select(SessionModel).where(
        SessionModel.study_id == study_id, SessionModel.status != "cancelled"
    )
    if participant_id is not None:
        stmt = stmt.where(SessionModel.participant_id == participant_id)

    sessions = db.execute(stmt).scalars().all()
    for s in sessions:
        apply_lazy_abandonment(db, s)

    filtered = (
        [s for s in sessions if s.status == status_filter] if status_filter is not None else list(sessions)
    )

    out = _sessions_to_out(db, filtered)
    return _sort_sessions(out, sort)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(
    session_id: uuid.UUID, payload: SessionActionRequest, user: CurrentUserDep, db: DbDep
) -> SessionOut:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    apply_lazy_abandonment(db, session)

    if payload.action == "reset":
        if session.status not in ("completed", "abandoned", "in_progress"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reset a session with status {session.status!r}",
            )
        session.status = "created"
        session.attempt += 1
        session.started_at = None
        session.completed_at = None
        session.last_activity_at = None
        session.resume_count = 0
    else:
        if session.status != "created":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot cancel a session with status {session.status!r}",
            )
        session.status = "cancelled"

    db.commit()
    db.refresh(session)
    return _session_to_out(db, session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> None:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    trial_count = db.execute(
        select(func.count()).select_from(Trial).where(Trial.session_id == session_id)
    ).scalar_one()
    if trial_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot delete a session with trial rows"
        )

    db.delete(session)
    db.commit()


@router.get("/me/sessions", response_model=list[MySessionOut])
def list_my_sessions(participant: CurrentParticipantDep, db: DbDep) -> list[MySessionOut]:
    sessions = (
        db.execute(
            select(SessionModel)
            .where(SessionModel.participant_id == participant.id, SessionModel.status != "cancelled")
            .order_by(SessionModel.order_index)
        )
        .scalars()
        .all()
    )
    for s in sessions:
        apply_lazy_abandonment(db, s)

    out: list[MySessionOut] = []
    locked_so_far = False
    for s in sessions:
        out.append(
            MySessionOut(
                id=s.id,
                code=s.code,
                order_index=s.order_index,
                task_type=s.task_type,
                status=s.status,
                attempt=s.attempt,
                started_at=s.started_at,
                completed_at=s.completed_at,
                locked=locked_so_far,
            )
        )
        if s.status != "completed":
            locked_so_far = True
    return out
