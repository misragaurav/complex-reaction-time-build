from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import CurrentParticipantDep, CurrentUserDep, DbDep
from app.models import Participant, Study, Trial, User
from app.models import Session as SessionModel
from app.schemas.common import merge_and_validate_params
from app.schemas.sessions import (
    GenerateProtocolRequest,
    GenerateProtocolResponse,
    MySessionOut,
    ProtocolCreatedItem,
    ProtocolSkippedItem,
    SessionActionRequest,
    SessionCreateRequest,
    SessionOut,
)
from app.services.codes import generate_session_code
from app.services.protocol import ad_hoc_label_fields, build_protocol_specs
from app.services.sessions import apply_lazy_abandonment
from app.services.statistics import compute_session_summary, load_test_trials, session_stats_brief
from app.task_defaults import default_params

router = APIRouter(tags=["sessions"])

VALID_STATUS_FILTERS = {"created", "activated", "in_progress", "completed", "abandoned", "expired"}  # MOD-5


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
                session_type=session.session_type,
                intervention_session_number=session.intervention_session_number,
                week_number=session.week_number,
                day_within_week=session.day_within_week,
                display_label=session.display_label,
                display_label_overridden=session.display_label_overridden,
                started_at=session.started_at,
                completed_at=session.completed_at,
                last_activity_at=session.last_activity_at,
                activated_at=session.activated_at,
                expired_at=session.expired_at,
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
            order_index = max_order + i + 1
            # MOD-3 / D1: ad-hoc sessions get default label fields (researcher
            # can relabel afterwards). Protocol sessions go via #33 instead.
            label_fields = ad_hoc_label_fields(order_index, study.sessions_per_week)
            session = SessionModel(
                code=generate_session_code(db),
                participant_id=participant_id,
                study_id=study_id,
                order_index=order_index,
                task_type=effective_task_type,
                params=dict(params),
                status="created",
                attempt=1,
                resume_count=0,
                **label_fields,
            )
            db.add(session)
            db.flush()
            created.append(session)

    db.commit()
    for s in created:
        db.refresh(s)
    return _sessions_to_out(db, created)


def _params_for_task_type(study: Study, task_type: str) -> dict[str, Any]:
    """Snapshot the study's params but for a possibly different task type
    (swapping in that type's default key_map). Raises 422 on any invalid combo
    (e.g. an SRT key_map of the wrong length), per MFR-8/MFR-18."""
    if study.params.get("task_type") == task_type:
        return merge_and_validate_params(task_type, study.params, None)  # type: ignore[arg-type]
    overrides = {"task_type": task_type, "key_map": default_params(task_type)["key_map"]}
    return merge_and_validate_params(task_type, study.params, overrides)  # type: ignore[arg-type]


@router.post(
    "/studies/{study_id}/generate-protocol",
    response_model=GenerateProtocolResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_protocol(
    study_id: uuid.UUID, payload: GenerateProtocolRequest, user: CurrentUserDep, db: DbDep
) -> GenerateProtocolResponse:
    """MOD-3 / MFR-18: generate the 1+2N protocol sessions for participants."""
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")
    if study.is_archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot generate sessions in an archived study",
        )

    num = payload.num_intervention_sessions or study.num_intervention_sessions
    if num % study.sessions_per_week != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="num_intervention_sessions must be a multiple of sessions_per_week",
        )
    tt_onboarding = payload.task_type_onboarding or study.task_type_onboarding
    tt_pre = payload.task_type_pre or study.task_type_pre
    tt_post = payload.task_type_post or study.task_type_post

    # MFR-18: validate every task-type/params combo BEFORE creating any session.
    params_by_tt = {tt: _params_for_task_type(study, tt) for tt in {tt_onboarding, tt_pre, tt_post}}

    # Resolve target participants: explicit list, or all who have no sessions yet.
    if payload.participant_ids is not None:
        targets: list[Participant] = []
        for pid in payload.participant_ids:
            participant = db.get(Participant, pid)
            if participant is None or participant.study_id != study_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Participant {pid} not found in this study",
                )
            targets.append(participant)
    else:
        targets = list(
            db.execute(
                select(Participant)
                .where(Participant.study_id == study_id, Participant.is_active.is_(True))
                .order_by(Participant.created_at)
            )
            .scalars()
            .all()
        )

    specs = build_protocol_specs(
        num_intervention_sessions=num,
        sessions_per_week=study.sessions_per_week,
        week_start=payload.week_start,
        task_type_onboarding=tt_onboarding,
        task_type_pre=tt_pre,
        task_type_post=tt_post,
    )

    created_items: list[ProtocolCreatedItem] = []
    skipped_items: list[ProtocolSkippedItem] = []
    for participant in targets:
        existing = db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.participant_id == participant.id)
        ).scalar_one()
        if existing > 0:
            # Idempotent per participant (MFR-18): skip anyone who already has
            # sessions (a generated protocol or ad-hoc sessions).
            skipped_items.append(
                ProtocolSkippedItem(
                    participant_id=participant.id, code=participant.code, reason="already_generated"
                )
            )
            continue
        for spec in specs:
            session = SessionModel(
                code=generate_session_code(db),
                participant_id=participant.id,
                study_id=study_id,
                order_index=spec["order_index"],
                task_type=spec["task_type"],
                params=dict(params_by_tt[spec["task_type"]]),
                status="created",
                attempt=1,
                resume_count=0,
                session_type=spec["session_type"],
                intervention_session_number=spec["intervention_session_number"],
                week_number=spec["week_number"],
                day_within_week=spec["day_within_week"],
                display_label=spec["display_label"],
                display_label_overridden=False,
            )
            db.add(session)
        db.flush()
        created_items.append(
            ProtocolCreatedItem(
                participant_id=participant.id, code=participant.code, session_count=len(specs)
            )
        )

    db.commit()
    return GenerateProtocolResponse(created=created_items, skipped=skipped_items)


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

    if payload.display_label is not None:
        # MOD-3 / MFR-14: relabel, allowed only before activation / after expiry.
        if session.status not in ("created", "expired"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="display_label cannot be changed once a session has been activated",
            )
        session.display_label = payload.display_label
        session.display_label_overridden = True
        db.commit()
        db.refresh(session)
        return _session_to_out(db, session)

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
        # MOD-5: allow cancelling created, activated, or expired sessions.
        if session.status not in ("created", "activated", "expired"):
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


@router.post("/sessions/{session_id}/activate", response_model=SessionOut)
def activate_session(session_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> SessionOut:
    """MOD-5 / MFR-33: activate a single session (created → activated or expired → activated)."""
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status not in ("created", "expired"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot activate a session with status {session.status!r}",
        )
    now = datetime.datetime.now(datetime.timezone.utc)
    session.status = "activated"
    session.activated_at = now
    session.activated_by = user.id
    db.commit()
    db.refresh(session)
    return _session_to_out(db, session)


@router.post("/sessions/{session_id}/deactivate", response_model=SessionOut)
def deactivate_session(session_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> SessionOut:
    """MOD-5 / MFR-33: deactivate a single session (activated → expired)."""
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status != "activated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot deactivate a session with status {session.status!r}",
        )
    now = datetime.datetime.now(datetime.timezone.utc)
    session.status = "expired"
    session.expired_at = now
    db.commit()
    db.refresh(session)
    return _session_to_out(db, session)


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

    # MOD-5: status drives gating; locked is kept for schema compat but always False.
    out: list[MySessionOut] = []
    for s in sessions:
        out.append(
            MySessionOut(
                id=s.id,
                code=s.code,
                order_index=s.order_index,
                task_type=s.task_type,
                status=s.status,
                attempt=s.attempt,
                session_type=s.session_type,
                display_label=s.display_label,
                started_at=s.started_at,
                completed_at=s.completed_at,
                activated_at=s.activated_at,
                expired_at=s.expired_at,
                locked=False,
            )
        )
    return out
