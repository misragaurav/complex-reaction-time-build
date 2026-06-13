from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DbDep
from app.models import Participant, Session as SessionModel, Study
from app.schemas.common import merge_and_validate_params
from app.schemas.studies import StudyCounts, StudyCreate, StudyOut, StudyUpdate

router = APIRouter(prefix="/studies", tags=["studies"])


def _study_counts(db: DbDep, study_id: uuid.UUID) -> StudyCounts:
    participants = db.execute(
        select(func.count()).select_from(Participant).where(Participant.study_id == study_id)
    ).scalar_one()
    sessions_total = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.study_id == study_id, SessionModel.status != "cancelled")
    ).scalar_one()
    sessions_completed = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.study_id == study_id, SessionModel.status == "completed")
    ).scalar_one()
    completion_pct = (sessions_completed / sessions_total * 100) if sessions_total else 0.0
    return StudyCounts(
        participants=participants,
        sessions_total=sessions_total,
        sessions_completed=sessions_completed,
        completion_pct=round(completion_pct, 1),
    )


def _params_locked(db: DbDep, study_id: uuid.UUID) -> bool:
    started = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.study_id == study_id, SessionModel.started_at.is_not(None))
    ).scalar_one()
    return bool(started > 0)


def _protocol_locked(db: DbDep, study_id: uuid.UUID) -> bool:
    """True once the protocol has been generated (an onboarding session exists).

    MFR-12: protocol-config fields become read-only after generation. Ad-hoc
    sessions created via API #15 are always typed 'pre' (D1), so the presence of
    an 'onboarding' session uniquely indicates protocol generation has run.
    """
    n = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.study_id == study_id, SessionModel.session_type == "onboarding")
    ).scalar_one()
    return bool(n > 0)


def _validate_multiple_of(num_intervention_sessions: int, sessions_per_week: int) -> None:
    if num_intervention_sessions % sessions_per_week != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="num_intervention_sessions must be a multiple of sessions_per_week",
        )


def _study_to_out(db: DbDep, study: Study) -> StudyOut:
    return StudyOut(
        id=study.id,
        name=study.name,
        description=study.description,
        task_type=study.task_type,
        params=study.params,
        num_intervention_sessions=study.num_intervention_sessions,
        sessions_per_week=study.sessions_per_week,
        task_type_onboarding=study.task_type_onboarding,
        task_type_pre=study.task_type_pre,
        task_type_post=study.task_type_post,
        protocol_locked=_protocol_locked(db, study.id),
        created_by=study.created_by,
        is_archived=study.is_archived,
        params_locked=_params_locked(db, study.id),
        counts=_study_counts(db, study.id),
        created_at=study.created_at,
        updated_at=study.updated_at,
    )


@router.get("", response_model=list[StudyOut])
def list_studies(
    user: CurrentUserDep,
    db: DbDep,
    archived: Annotated[bool | None, Query()] = None,
) -> list[StudyOut]:
    stmt = select(Study)
    if archived is True:
        stmt = stmt.where(Study.is_archived.is_(True))
    else:
        stmt = stmt.where(Study.is_archived.is_(False))
    stmt = stmt.order_by(Study.created_at.desc())
    studies = db.execute(stmt).scalars().all()
    return [_study_to_out(db, s) for s in studies]


@router.post("", response_model=StudyOut, status_code=status.HTTP_201_CREATED)
def create_study(payload: StudyCreate, user: CurrentUserDep, db: DbDep) -> StudyOut:
    params = merge_and_validate_params(payload.task_type, None, payload.params)
    # MFR-12: num_intervention_sessions must be a multiple of sessions_per_week.
    _validate_multiple_of(payload.num_intervention_sessions, payload.sessions_per_week)
    study = Study(
        name=payload.name,
        description=payload.description,
        task_type=payload.task_type,
        params=params,
        num_intervention_sessions=payload.num_intervention_sessions,
        sessions_per_week=payload.sessions_per_week,
        task_type_onboarding=payload.task_type_onboarding,
        task_type_pre=payload.task_type_pre,
        task_type_post=payload.task_type_post,
        created_by=user.id,
        is_archived=False,
    )
    db.add(study)
    db.commit()
    db.refresh(study)
    return _study_to_out(db, study)


@router.get("/{study_id}", response_model=StudyOut)
def get_study(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> StudyOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    return _study_to_out(db, study)


@router.patch("/{study_id}", response_model=StudyOut)
def update_study(
    study_id: uuid.UUID, payload: StudyUpdate, user: CurrentUserDep, db: DbDep
) -> StudyOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    if payload.name is not None:
        study.name = payload.name
    if payload.description is not None:
        study.description = payload.description

    if payload.params is not None:
        if _params_locked(db, study.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Study parameters are locked because at least one session has started",
            )
        # task_type is immutable after creation; ignore any task_type key in overrides.
        overrides = {k: v for k, v in payload.params.items() if k != "task_type"}
        study.params = merge_and_validate_params(study.task_type, study.params, overrides)  # type: ignore[arg-type]

    if payload.is_archived is not None:
        study.is_archived = payload.is_archived

    # MOD-3: protocol configuration fields (MFR-11/12).
    requested = {
        k: v
        for k, v in (
            ("num_intervention_sessions", payload.num_intervention_sessions),
            ("sessions_per_week", payload.sessions_per_week),
            ("task_type_onboarding", payload.task_type_onboarding),
            ("task_type_pre", payload.task_type_pre),
            ("task_type_post", payload.task_type_post),
        )
        if v is not None
    }
    if requested:
        changed = {k: v for k, v in requested.items() if getattr(study, k) != v}
        if changed and _protocol_locked(db, study.id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="protocol configuration is locked after sessions have been generated",
            )
        for k, v in requested.items():
            setattr(study, k, v)
        _validate_multiple_of(study.num_intervention_sessions, study.sessions_per_week)

    db.commit()
    db.refresh(study)
    return _study_to_out(db, study)
