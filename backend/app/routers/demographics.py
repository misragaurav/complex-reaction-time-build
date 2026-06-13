from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DbDep
from app.models import DemographicField, DemographicResponse, Study
from app.schemas.demographics import (
    DemographicFieldCreate,
    DemographicFieldOut,
    DemographicFieldUpdate,
)

router = APIRouter(tags=["demographic-fields"])


def _has_responses(db: DbDep, field_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(DemographicResponse.id).where(DemographicResponse.field_id == field_id).limit(1)
        ).first()
        is not None
    )


def _field_to_out(db: DbDep, field: DemographicField) -> DemographicFieldOut:
    return DemographicFieldOut(
        id=field.id,
        study_id=field.study_id,
        label=field.label,
        field_type=field.field_type,
        options=field.options,
        required=field.required,
        frequency=field.frequency,
        display_order=field.display_order,
        is_retired=field.is_retired,
        has_responses=_has_responses(db, field.id),
        created_at=field.created_at,
    )


@router.get("/studies/{study_id}/demographic-fields", response_model=list[DemographicFieldOut])
def list_demographic_fields(
    study_id: uuid.UUID, user: CurrentUserDep, db: DbDep
) -> list[DemographicFieldOut]:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    fields = (
        db.execute(
            select(DemographicField)
            .where(DemographicField.study_id == study_id)
            .order_by(DemographicField.display_order)
        )
        .scalars()
        .all()
    )
    return [_field_to_out(db, f) for f in fields]


@router.post(
    "/studies/{study_id}/demographic-fields",
    response_model=DemographicFieldOut,
    status_code=status.HTTP_201_CREATED,
)
def create_demographic_field(
    study_id: uuid.UUID, payload: DemographicFieldCreate, user: CurrentUserDep, db: DbDep
) -> DemographicFieldOut:
    study = db.get(Study, study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study not found")

    next_order = db.execute(
        select(func.coalesce(func.max(DemographicField.display_order), -1) + 1).where(
            DemographicField.study_id == study_id
        )
    ).scalar_one()

    field = DemographicField(
        study_id=study_id,
        label=payload.label,
        field_type=payload.field_type,
        options=payload.options,
        required=payload.required,
        frequency=payload.frequency,
        display_order=next_order,
        is_retired=False,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return _field_to_out(db, field)


@router.patch("/demographic-fields/{field_id}", response_model=DemographicFieldOut)
def update_demographic_field(
    field_id: uuid.UUID, payload: DemographicFieldUpdate, user: CurrentUserDep, db: DbDep
) -> DemographicFieldOut:
    field = db.get(DemographicField, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demographic field not found")

    has_responses = _has_responses(db, field.id)

    if has_responses and (payload.label is not None or payload.options is not None):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This field has been answered by at least one participant, so its label and "
                "options are read-only. Create a new field instead."
            ),
        )

    if payload.options is not None and field.field_type == "single_choice":
        if len(payload.options) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="single_choice fields require a non-empty `options` array",
            )
        if len(payload.options) > 20:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="single_choice fields support at most 20 options",
            )

    if payload.label is not None:
        field.label = payload.label
    if payload.options is not None:
        field.options = payload.options
    if payload.required is not None:
        field.required = payload.required
    if payload.frequency is not None:
        field.frequency = payload.frequency
    if payload.display_order is not None:
        field.display_order = payload.display_order

    db.commit()
    db.refresh(field)
    return _field_to_out(db, field)


@router.delete("/demographic-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_demographic_field(field_id: uuid.UUID, user: CurrentUserDep, db: DbDep) -> None:
    field = db.get(DemographicField, field_id)
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demographic field not found")

    if _has_responses(db, field.id):
        field.is_retired = True
        db.commit()
    else:
        db.delete(field)
        db.commit()
