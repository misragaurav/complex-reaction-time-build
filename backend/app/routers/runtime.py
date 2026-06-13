"""Participant-facing session runtime endpoints (FR-20/21/29-35/41-46; API #20-24)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.deps import CurrentParticipantDep, DbDep
from app.models import DemographicField, DemographicResponse
from app.models import Session as SessionModel
from app.models import Trial
from app.schemas.common import TaskParams
from app.schemas.demographics import DemographicAnswersRequest, DemographicFieldPublic
from app.schemas.sessions import SessionStartResponse, StoredTrials
from app.schemas.trials import ClientEnvIn, TrialBatchRequest, TrialBatchResponse, TrialIn
from app.services.sessions import (
    demographics_due_for_session,
    get_owned_session,
    resume_state,
)

router = APIRouter(prefix="/sessions", tags=["runtime"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _require_in_progress(session: SessionModel) -> None:
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session is not in progress (status={session.status!r})",
        )


@router.post("/{session_id}/start", response_model=SessionStartResponse)
def start_session(
    session_id: uuid.UUID, participant: CurrentParticipantDep, db: DbDep
) -> SessionStartResponse:
    session = get_owned_session(db, participant, session_id)

    # MOD-5: initial start requires activated; in_progress allows resume (page refresh).
    if session.status == "activated":
        now = _now()
        session.status = "in_progress"
        session.started_at = now
        session.last_activity_at = now
    elif session.status == "in_progress":
        # Resume after page refresh — bump counter but leave started_at unchanged.
        session.resume_count += 1
        session.last_activity_at = _now()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Session is not activated (status={session.status!r})",
        )
    db.commit()
    db.refresh(session)

    return SessionStartResponse(
        params=TaskParams.model_validate(session.params),
        task_type=session.task_type,
        attempt=session.attempt,
        demographics_due=[
            DemographicFieldPublic.model_validate(f) for f in demographics_due_for_session(db, session)
        ],
        stored_trials=StoredTrials(**resume_state(db, session)),
    )


def _validate_answer_value(field: DemographicField, value: str) -> None:
    if field.field_type == "number":
        try:
            float(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Field {field.label!r} requires a numeric value",
            ) from exc
    elif field.field_type == "boolean":
        if value.lower() not in ("true", "false"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Field {field.label!r} requires a boolean value ('true' or 'false')",
            )
    elif field.field_type == "single_choice":
        if field.options is None or value not in field.options:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Field {field.label!r} requires one of {field.options}",
            )


@router.post("/{session_id}/demographics", status_code=status.HTTP_204_NO_CONTENT)
def submit_demographics(
    session_id: uuid.UUID,
    payload: DemographicAnswersRequest,
    participant: CurrentParticipantDep,
    db: DbDep,
) -> None:
    session = get_owned_session(db, participant, session_id)
    _require_in_progress(session)

    fields_by_id: dict[uuid.UUID, DemographicField] = {}
    for answer in payload.answers:
        field = fields_by_id.get(answer.field_id)
        if field is None:
            field = db.get(DemographicField, answer.field_id)
            if field is None or field.study_id != session.study_id or field.is_retired:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Demographic field {answer.field_id} not found",
                )
            fields_by_id[answer.field_id] = field
        _validate_answer_value(field, answer.value)

    due = demographics_due_for_session(db, session)
    submitted_ids = {a.field_id for a in payload.answers}
    for field in due:
        if field.required and field.id not in submitted_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Required demographic field {field.label!r} is missing",
            )

    for answer in payload.answers:
        field = fields_by_id[answer.field_id]
        target_session_id = session.id if field.frequency == "every_session" else None

        stmt = select(DemographicResponse).where(
            DemographicResponse.participant_id == participant.id,
            DemographicResponse.field_id == field.id,
        )
        stmt = (
            stmt.where(DemographicResponse.session_id == target_session_id)
            if target_session_id is not None
            else stmt.where(DemographicResponse.session_id.is_(None))
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            existing.value = answer.value
        else:
            db.add(
                DemographicResponse(
                    participant_id=participant.id,
                    field_id=field.id,
                    session_id=target_session_id,
                    value=answer.value,
                )
            )

    db.commit()


def _to_decimal(value: float | None, ndigits: int = 1) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, ndigits)))


def _upsert_trial(
    db: OrmSession,
    session: SessionModel,
    trial_in: TrialIn,
    key_map: list[str],
    outlier_low: int,
    outlier_high: int,
) -> None:
    """Recompute `outcome`/`response_position`/`outlier_flag` server-side and
    idempotently upsert by `client_uuid` (FR-34, §8 row 22)."""
    if trial_in.outcome == "invalid":
        outcome = "invalid"
        response_position = (
            key_map.index(trial_in.key_pressed) if trial_in.key_pressed in key_map else None
        )
    elif trial_in.key_pressed is None:
        outcome = "timeout"
        response_position = None
    elif trial_in.key_pressed in key_map:
        response_position = key_map.index(trial_in.key_pressed)
        outcome = "correct" if response_position == trial_in.stimulus_position else "incorrect"
    else:
        response_position = None
        outcome = "incorrect"

    if outcome == "correct" and trial_in.rt_ms is not None:
        outlier_flag = trial_in.rt_ms < outlier_low or trial_in.rt_ms > outlier_high
    else:
        outlier_flag = False

    rt_ms = _to_decimal(trial_in.rt_ms) if outcome in ("correct", "incorrect") else None

    existing = db.execute(
        select(Trial).where(Trial.client_uuid == trial_in.client_uuid)
    ).scalar_one_or_none()

    if existing is not None and existing.session_id != session.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="client_uuid is already used by a trial in another session",
        )

    if existing is None:
        conflict = db.execute(
            select(Trial.id).where(
                Trial.session_id == session.id,
                Trial.attempt == session.attempt,
                Trial.block == trial_in.block,
                Trial.trial_index == trial_in.trial_index,
            )
        ).first()
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Trial {trial_in.trial_index} of block {trial_in.block!r} already exists "
                    "for this attempt with a different client_uuid"
                ),
            )
        existing = Trial(client_uuid=trial_in.client_uuid, session_id=session.id)
        db.add(existing)

    existing.attempt = session.attempt
    existing.block = trial_in.block
    existing.trial_index = trial_in.trial_index
    existing.stimulus_position = trial_in.stimulus_position
    existing.foreperiod_ms = trial_in.foreperiod_ms
    existing.key_pressed = trial_in.key_pressed
    existing.response_position = response_position
    existing.outcome = outcome
    existing.rt_ms = rt_ms
    existing.premature_count = trial_in.premature_count
    existing.extraneous_keys = trial_in.extraneous_keys
    existing.invalid_reason = trial_in.invalid_reason
    existing.outlier_flag = outlier_flag
    existing.stimulus_onset_client_ms = _to_decimal(trial_in.stimulus_onset_client_ms)
    existing.response_client_ms = _to_decimal(trial_in.response_client_ms)
    db.flush()


@router.post("/{session_id}/trials", response_model=TrialBatchResponse)
def submit_trials(
    session_id: uuid.UUID,
    payload: TrialBatchRequest,
    participant: CurrentParticipantDep,
    db: DbDep,
) -> TrialBatchResponse:
    session = get_owned_session(db, participant, session_id)
    _require_in_progress(session)

    key_map: list[str] = session.params["key_map"]
    outlier_low: int = session.params["outlier_low_ms"]
    outlier_high: int = session.params["outlier_high_ms"]

    accepted = 0
    for trial_in in payload.trials:
        _upsert_trial(db, session, trial_in, key_map, outlier_low, outlier_high)
        accepted += 1

    session.last_activity_at = _now()
    db.commit()
    return TrialBatchResponse(accepted=accepted)


@router.post("/{session_id}/complete", status_code=status.HTTP_204_NO_CONTENT)
def complete_session(session_id: uuid.UUID, participant: CurrentParticipantDep, db: DbDep) -> None:
    session = get_owned_session(db, participant, session_id)
    _require_in_progress(session)

    test_trials = (
        db.execute(
            select(Trial).where(
                Trial.session_id == session.id,
                Trial.attempt == session.attempt,
                Trial.block == "test",
            )
        )
        .scalars()
        .all()
    )

    k = sum(1 for t in test_trials if t.outcome == "invalid")
    expected_rows = session.params["test_trials"] + min(k, 5)
    expected_indices = list(range(1, expected_rows + 1))
    actual_indices = sorted({t.trial_index for t in test_trials})

    if actual_indices != expected_indices:
        missing = sorted(set(expected_indices) - set(actual_indices))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Test block is incomplete",
                "expected_rows": expected_rows,
                "missing_trial_indices": missing,
            },
        )

    now = _now()
    session.status = "completed"
    session.completed_at = now
    session.last_activity_at = now
    db.commit()


@router.post("/{session_id}/client-env", status_code=status.HTTP_204_NO_CONTENT)
def submit_client_env(
    session_id: uuid.UUID,
    payload: ClientEnvIn,
    participant: CurrentParticipantDep,
    db: DbDep,
) -> None:
    session = get_owned_session(db, participant, session_id)
    _require_in_progress(session)

    session.client_env = payload.model_dump()
    session.last_activity_at = _now()
    db.commit()
