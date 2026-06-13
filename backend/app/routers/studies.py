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


def _study_to_out(db: DbDep, study: Study) -> StudyOut:
    return StudyOut(
        id=study.id,
        name=study.name,
        description=study.description,
        task_type=study.task_type,
        params=study.params,
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
    study = Study(
        name=payload.name,
        description=payload.description,
        task_type=payload.task_type,
        params=params,
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

    db.commit()
    db.refresh(study)
    return _study_to_out(db, study)
