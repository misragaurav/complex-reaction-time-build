from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DbDep
from app.models import Participant
from app.models import Session as SessionModel
from app.models import Study
from app.schemas.participants import ParticipantCreate, ParticipantOut, ParticipantUpdate
from app.services.codes import generate_participant_code
from app.services.csv_export import build_csv, content_disposition, csv_filename

router = APIRouter(tags=["participants"])


def _participant_to_out(db: DbDep, participant: Participant) -> ParticipantOut:
    sessions_assigned = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.participant_id == participant.id, SessionModel.status != "cancelled")
    ).scalar_one()
    sessions_completed = db.execute(
        select(func.count())
        .select_from(SessionModel)
        .where(SessionModel.participant_id == participant.id, SessionModel.status == "completed")
    ).scalar_one()
    return ParticipantOut(
        id=participant.id,
        study_id=participant.study_id,
        code=participant.code,
        password_set=participant.password_hash is not None,
        is_active=participant.is_active,
        sessions_assigned=sessions_assigned,
        sessions_completed=sessions_completed,
        last_login_at=participant.last_login_at,
        created_at=participant.created_at,
    )


@router.get("/studies/{study_id}/participants", response_model=list[ParticipantOut])
def list_participants(
    study_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> list[ParticipantOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    participants = (
        db.execute(
            select(Participant)
            .where(Participant.study_id == study_id)
            .order_by(Participant.created_at)
        )
        .scalars()
        .all()
    )
    return [_participant_to_out(db, p) for p in participants]


@router.post(
    "/studies/{study_id}/participants",
    response_model=list[ParticipantOut],
    status_code=status.HTTP_201_CREATED,
)
def create_participants(
    study_id: uuid.UUID, payload: ParticipantCreate, user: CurrentUserDep, db: DbDep
) -> list[ParticipantOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    created: list[Participant] = []

    if payload.codes is not None:
        for code in payload.codes:
            existing = db.execute(select(Participant.id).where(Participant.code == code)).first()
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f"Code already in use: {code}"
                )
            participant = Participant(study_id=study_id, code=code, is_active=True)
            db.add(participant)
            db.flush()
            created.append(participant)
    else:
        assert payload.count is not None
        for _ in range(payload.count):
            code = generate_participant_code(db, payload.prefix)
            participant = Participant(study_id=study_id, code=code, is_active=True)
            db.add(participant)
            db.flush()
            created.append(participant)

    db.commit()
    for p in created:
        db.refresh(p)
    return [_participant_to_out(db, p) for p in created]


@router.patch("/participants/{participant_id}", response_model=ParticipantOut)
def update_participant(
    participant_id: uuid.UUID, payload: ParticipantUpdate, user: CurrentUserDep, db: DbDep
) -> ParticipantOut:
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    if payload.is_active is not None:
        participant.is_active = payload.is_active
    if payload.reset_password:
        participant.password_hash = None

    db.commit()
    db.refresh(participant)
    return _participant_to_out(db, participant)


@router.get("/studies/{study_id}/participants.csv")
def export_participants_csv(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> Response:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    participants = (
        db.execute(
            select(Participant)
            .where(Participant.study_id == study_id)
            .order_by(Participant.created_at)
        )
        .scalars()
        .all()
    )
    csv_text = build_csv(["code"], [[p.code] for p in participants])
    filename = csv_filename(study.name, "participant_codes")
    return Response(
        content=csv_text, media_type="text/csv", headers=content_disposition(filename)
    )
