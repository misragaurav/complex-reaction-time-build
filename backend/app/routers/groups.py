"""MOD-4: participant group management (API #34-39)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DbDep
from app.models import Group, Participant, ParticipantGroupAssignment, Study
from app.models import Session as SessionModel
from app.schemas.groups import (
    AssignedItem,
    ConflictItem,
    GroupAssignRequest,
    GroupAssignResponse,
    GroupCompletionStats,
    GroupCreate,
    GroupDetailOut,
    GroupMember,
    GroupOut,
    GroupUpdate,
)

router = APIRouter(tags=["groups"])


def _member_count(db: DbDep, group_id: uuid.UUID) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(ParticipantGroupAssignment)
            .where(ParticipantGroupAssignment.group_id == group_id)
        ).scalar_one()
    )


def _group_to_out(db: DbDep, group: Group) -> GroupOut:
    return GroupOut(
        id=group.id,
        study_id=group.study_id,
        name=group.name,
        description=group.description,
        current_intervention_session=group.current_intervention_session,
        member_count=_member_count(db, group.id),
        created_at=group.created_at,
    )


def _name_taken(db: DbDep, study_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Group.id).where(Group.study_id == study_id, Group.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Group.id != exclude_id)
    return db.execute(stmt).first() is not None


def _get_group(db: DbDep, group_id: uuid.UUID) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


@router.get("/studies/{study_id}/groups", response_model=list[GroupOut])
def list_groups(study_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> list[GroupOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    groups = (
        db.execute(select(Group).where(Group.study_id == study_id).order_by(Group.created_at))
        .scalars()
        .all()
    )
    return [_group_to_out(db, g) for g in groups]


@router.post("/studies/{study_id}/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    study_id: uuid.UUID, payload: GroupCreate, user: CurrentUserDep, db: DbDep
) -> GroupOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if _name_taken(db, study_id, payload.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A group named {payload.name!r} already exists in this study",
        )
    group = Group(study_id=study_id, name=payload.name, description=payload.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


def _completion_stats(db: DbDep, group: Group, member_ids: list[uuid.UUID]) -> GroupCompletionStats:
    total = len(member_ids)
    if not member_ids:
        return GroupCompletionStats(
            total_assigned=0,
            completed_pre_overall=0,
            completed_post_overall=0,
            completed_pre_current=0,
            completed_post_current=0,
        )

    def _count(session_type: str, only_current: bool) -> int:
        if only_current and group.current_intervention_session is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(SessionModel)
            .where(
                SessionModel.participant_id.in_(member_ids),
                SessionModel.session_type == session_type,
                SessionModel.status == "completed",
            )
        )
        if only_current:
            stmt = stmt.where(
                SessionModel.intervention_session_number == group.current_intervention_session
            )
        return int(db.execute(stmt).scalar_one())

    return GroupCompletionStats(
        total_assigned=total,
        completed_pre_overall=_count("pre", False),
        completed_post_overall=_count("post", False),
        completed_pre_current=_count("pre", True),
        completed_post_current=_count("post", True),
    )


@router.get("/groups/{group_id}", response_model=GroupDetailOut)
def get_group(group_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> GroupDetailOut:
    group = _get_group(db, group_id)
    assignments = (
        db.execute(
            select(ParticipantGroupAssignment).where(
                ParticipantGroupAssignment.group_id == group_id
            )
        )
        .scalars()
        .all()
    )
    member_ids = [a.participant_id for a in assignments]
    members: list[GroupMember] = []
    for a in assignments:
        participant = a.participant
        assigned = int(
            db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(
                    SessionModel.participant_id == participant.id,
                    SessionModel.status != "cancelled",
                )
            ).scalar_one()
        )
        completed = int(
            db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(
                    SessionModel.participant_id == participant.id,
                    SessionModel.status == "completed",
                )
            ).scalar_one()
        )
        members.append(
            GroupMember(
                participant_id=participant.id,
                code=participant.code,
                is_active=participant.is_active,
                sessions_assigned=assigned,
                sessions_completed=completed,
            )
        )
    members.sort(key=lambda m: m.code)

    out = _group_to_out(db, group)
    return GroupDetailOut(
        **out.model_dump(),
        members=members,
        completion=_completion_stats(db, group, member_ids),
    )


@router.patch("/groups/{group_id}", response_model=GroupOut)
def update_group(
    group_id: uuid.UUID, payload: GroupUpdate, user: CurrentUserDep, db: DbDep
) -> GroupOut:
    group = _get_group(db, group_id)
    if payload.name is not None and payload.name != group.name:
        if _name_taken(db, group.study_id, payload.name, exclude_id=group.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A group named {payload.name!r} already exists in this study",
            )
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    if payload.current_intervention_session is not None:
        group.current_intervention_session = payload.current_intervention_session
    db.commit()
    db.refresh(group)
    return _group_to_out(db, group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> None:
    group = _get_group(db, group_id)
    if _member_count(db, group.id) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group has assigned participants and cannot be deleted.",
        )
    db.delete(group)
    db.commit()


@router.post("/groups/{group_id}/assign", response_model=GroupAssignResponse)
def assign_participants(
    group_id: uuid.UUID, payload: GroupAssignRequest, user: CurrentUserDep, db: DbDep
) -> GroupAssignResponse:
    group = _get_group(db, group_id)

    assigned: list[AssignedItem] = []
    conflicts: list[ConflictItem] = []
    seen: set[uuid.UUID] = set()
    for pid in payload.participant_ids:
        if pid in seen:
            continue
        seen.add(pid)
        participant = db.get(Participant, pid)
        if participant is None or participant.study_id != group.study_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Participant {pid} not found in this study",
            )
        existing = participant.group_assignment
        if existing is not None:
            current = db.get(Group, existing.group_id)
            conflicts.append(
                ConflictItem(
                    participant_id=pid,
                    code=participant.code,
                    current_group_name=current.name if current else "",
                )
            )
        else:
            db.add(ParticipantGroupAssignment(participant_id=pid, group_id=group_id))
            assigned.append(AssignedItem(participant_id=pid, code=participant.code))

    if not assigned and conflicts:
        # MFR-24: every requested participant was already assigned.
        first = conflicts[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Participant {first.code} is already assigned to group "
                f"{first.current_group_name}. Assignments cannot be changed."
            ),
        )

    db.commit()
    return GroupAssignResponse(assigned=assigned, conflicts=conflicts)
