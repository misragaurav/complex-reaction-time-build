"""MOD-4: participant group management (API #34-39)."""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DbDep
from app.models import Group, Participant, ParticipantGroupAssignment, Study
from app.models import Session as SessionModel
from app.schemas.groups import (
    AssignedItem,
    BlockedItem,
    BlockingItem,
    ConflictItem,
    GroupActivateRequest,
    GroupActivateResponse,
    GroupActivatedItem,
    GroupAssignRequest,
    GroupAssignResponse,
    GroupCompletionStats,
    GroupCreate,
    GroupDeactivateRequest,
    GroupDeactivateResponse,
    GroupDetailOut,
    GroupExpiredItem,
    GroupMember,
    GroupOut,
    GroupSessionsOverviewResponse,
    GroupUpdate,
    ReassignedItem,
    StageOverview,
    StageStatusCounts,
)
from app.services.protocol import compute_display_label

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
    reassigned: list[ReassignedItem] = []
    blocked: list[BlockedItem] = []
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
            current_group = db.get(Group, existing.group_id)
            current_group_name = current_group.name if current_group else ""
            started_count = db.execute(
                select(func.count()).select_from(SessionModel).where(
                    SessionModel.participant_id == pid,
                    SessionModel.status.in_(["in_progress", "completed", "abandoned"]),
                )
            ).scalar_one()
            if started_count > 0:
                blocked.append(
                    BlockedItem(
                        participant_id=pid,
                        code=participant.code,
                        current_group_name=current_group_name,
                        reason="sessions_started",
                    )
                )
            else:
                db.delete(existing)
                db.flush()
                db.add(ParticipantGroupAssignment(participant_id=pid, group_id=group_id))
                reassigned.append(
                    ReassignedItem(
                        participant_id=pid,
                        code=participant.code,
                        previous_group_name=current_group_name,
                        new_group_name=group.name,
                    )
                )
        else:
            db.add(ParticipantGroupAssignment(participant_id=pid, group_id=group_id))
            assigned.append(AssignedItem(participant_id=pid, code=participant.code))

    if not assigned and not reassigned:
        first = blocked[0] if blocked else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Participant {first.code} cannot be reassigned because sessions have already started."
                if first
                else "No participants could be assigned."
            ),
        )

    db.commit()
    return GroupAssignResponse(assigned=assigned, conflicts=[], reassigned=reassigned, blocked=blocked)


def _group_member_ids(db: DbDep, group_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        row[0]
        for row in db.execute(
            select(ParticipantGroupAssignment.participant_id).where(
                ParticipantGroupAssignment.group_id == group_id
            )
        ).all()
    ]


@router.post("/groups/{group_id}/activate", response_model=GroupActivateResponse)
def activate_group(
    group_id: uuid.UUID, payload: GroupActivateRequest, user: CurrentUserDep, db: DbDep
) -> GroupActivateResponse:
    """MOD-5/MOD-8/MOD-12: activate sessions for all group members by stage."""
    group = _get_group(db, group_id)

    member_ids = _group_member_ids(db, group_id)

    # MFR-115: global one-open-session-per-participant guard.
    if member_ids:
        blocking_sessions = db.execute(
            select(SessionModel).where(
                SessionModel.participant_id.in_(member_ids),
                SessionModel.status.in_(["activated", "in_progress"]),
            )
        ).scalars().all()
        if blocking_sessions:
            blocking: list[BlockingItem] = []
            participant_cache: dict[uuid.UUID, Participant] = {}
            for s in blocking_sessions:
                p = participant_cache.get(s.participant_id) or db.get(Participant, s.participant_id)
                if p:
                    participant_cache[s.participant_id] = p
                blocking.append(
                    BlockingItem(
                        participant_id=s.participant_id,
                        code=p.code if p else "",
                        session_id=s.id,
                        status=s.status,
                        session_type=s.session_type,
                        display_label=s.display_label,
                    )
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "One or more participants already have an open session.",
                    "blocking": [b.model_dump(mode="json") for b in blocking],
                },
            )

    now = datetime.datetime.now(datetime.timezone.utc)
    activated: list[GroupActivatedItem] = []
    participant_cache2: dict[uuid.UUID, Participant] = {}
    for pid in member_ids:
        participant = participant_cache2.get(pid) or db.get(Participant, pid)
        if participant is None:
            continue
        participant_cache2[pid] = participant

        if payload.session_type == "onboarding":
            # MFR-112: match onboarding sessions (IS IS NULL).
            sessions = db.execute(
                select(SessionModel).where(
                    SessionModel.participant_id == pid,
                    SessionModel.session_type == "onboarding",
                    SessionModel.intervention_session_number.is_(None),
                    SessionModel.status.in_(["created", "expired"]),
                )
            ).scalars().all()
        else:
            # MFR-211: use explicit IS from payload, not group counter.
            sessions = db.execute(
                select(SessionModel).where(
                    SessionModel.participant_id == pid,
                    SessionModel.intervention_session_number == payload.intervention_session_number,
                    SessionModel.session_type == payload.session_type,
                    SessionModel.status.in_(["created", "expired"]),
                )
            ).scalars().all()

        for s in sessions:
            s.status = "activated"
            s.activated_at = now
            s.activated_by = user.id
            activated.append(
                GroupActivatedItem(
                    participant_id=pid,
                    code=participant.code,
                    session_id=s.id,
                    display_label=s.display_label,
                    session_type=s.session_type,
                    order_index=s.order_index,
                )
            )

    # MFR-212: update counter as side effect on any pre/post call (D-12.5).
    if payload.session_type in ("pre", "post"):
        group.current_intervention_session = payload.intervention_session_number
    db.commit()
    return GroupActivateResponse(activated=activated, session_type=payload.session_type)


@router.post("/groups/{group_id}/deactivate", response_model=GroupDeactivateResponse)
def deactivate_group(
    group_id: uuid.UUID, payload: GroupDeactivateRequest, user: CurrentUserDep, db: DbDep
) -> GroupDeactivateResponse:
    """MOD-5/MOD-8/MOD-12: expire activated sessions for all group members by stage."""
    group = _get_group(db, group_id)

    member_ids = _group_member_ids(db, group_id)

    if payload.session_type == "onboarding":
        # MFR-112: match onboarding sessions (IS IS NULL).
        sessions = db.execute(
            select(SessionModel).where(
                SessionModel.participant_id.in_(member_ids),
                SessionModel.session_type == "onboarding",
                SessionModel.intervention_session_number.is_(None),
                SessionModel.status.in_(["activated", "in_progress"]),
            )
        ).scalars().all()
    else:
        # MFR-211: use explicit IS from payload, not group counter.
        sessions = db.execute(
            select(SessionModel).where(
                SessionModel.participant_id.in_(member_ids),
                SessionModel.intervention_session_number == payload.intervention_session_number,
                SessionModel.session_type == payload.session_type,
                SessionModel.status.in_(["activated", "in_progress"]),
            )
        ).scalars().all()

    in_progress = [s for s in sessions if s.status == "in_progress"]
    # MFR-114: require force=true when any matched session is in_progress.
    if in_progress and not payload.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"{len(in_progress)} session(s) are in_progress; use force=true to expire only activated ones",
                "in_progress_count": len(in_progress),
            },
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    expired: list[GroupExpiredItem] = []
    participant_cache: dict[uuid.UUID, Participant] = {}
    for s in sessions:
        if s.status != "activated":
            continue
        participant = participant_cache.get(s.participant_id) or db.get(Participant, s.participant_id)
        if participant:
            participant_cache[s.participant_id] = participant
        s.status = "expired"
        s.expired_at = now
        expired.append(
            GroupExpiredItem(
                participant_id=s.participant_id,
                code=participant.code if participant else "",
                session_id=s.id,
                display_label=s.display_label,
            )
        )

    # MFR-212: update counter as side effect on any pre/post call (D-12.5).
    if payload.session_type in ("pre", "post"):
        group.current_intervention_session = payload.intervention_session_number
    db.commit()
    return GroupDeactivateResponse(expired=expired, in_progress_count=len(in_progress))


@router.get("/groups/{group_id}/sessions-overview", response_model=GroupSessionsOverviewResponse)
def sessions_overview(
    group_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> GroupSessionsOverviewResponse:
    """MOD-12 (MFR-214): per-stage session status counts for the group."""
    _get_group(db, group_id)  # raises 404 if not found
    member_ids = _group_member_ids(db, group_id)

    if not member_ids:
        return GroupSessionsOverviewResponse(stages=[])

    all_sessions = db.execute(
        select(SessionModel).where(SessionModel.participant_id.in_(member_ids))
    ).scalars().all()

    if not all_sessions:
        return GroupSessionsOverviewResponse(stages=[])

    ALL_STATUSES = ("created", "expired", "activated", "in_progress", "completed", "abandoned", "cancelled")

    # Group by (session_type, intervention_session_number).
    stage_data: dict[tuple, dict] = {}
    for s in all_sessions:
        key = (s.session_type, s.intervention_session_number)
        if key not in stage_data:
            stage_data[key] = {
                "week_number": s.week_number,
                "day_within_week": s.day_within_week,
                "min_order_index": s.order_index,
                "members": set(),
                "counts": {st: 0 for st in ALL_STATUSES},
            }
        d = stage_data[key]
        d["min_order_index"] = min(d["min_order_index"], s.order_index)
        d["members"].add(s.participant_id)
        bucket = s.status if s.status in ALL_STATUSES else "cancelled"
        d["counts"][bucket] += 1

    stages: list[StageOverview] = []
    for (session_type, isn), d in sorted(stage_data.items(), key=lambda x: x[1]["min_order_index"]):
        label = compute_display_label(session_type, d["week_number"], d["day_within_week"])
        stages.append(
            StageOverview(
                session_type=session_type,
                intervention_session_number=isn,
                display_label=label,
                week_number=d["week_number"],
                day_within_week=d["day_within_week"],
                order_index=d["min_order_index"],
                member_total=len(d["members"]),
                counts=StageStatusCounts(**d["counts"]),
            )
        )

    return GroupSessionsOverviewResponse(stages=stages)
