from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FieldType = Literal["text", "number", "single_choice", "boolean"]
Frequency = Literal["once", "every_session"]


class DemographicFieldCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    field_type: FieldType
    options: list[str] | None = None
    required: bool = False
    frequency: Frequency

    @model_validator(mode="after")
    def _check_options(self) -> "DemographicFieldCreate":
        if self.field_type == "single_choice":
            if not self.options or len(self.options) == 0:
                raise ValueError("single_choice fields require a non-empty `options` array")
            if len(self.options) > 20:
                raise ValueError("single_choice fields support at most 20 options")
        return self


class DemographicFieldUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    options: list[str] | None = None
    required: bool | None = None
    frequency: Frequency | None = None
    display_order: int | None = None


class DemographicFieldOut(BaseModel):
    id: uuid.UUID
    study_id: uuid.UUID
    label: str
    field_type: FieldType
    options: list[str] | None
    required: bool
    frequency: Frequency
    display_order: int
    is_retired: bool
    has_responses: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class DemographicFieldPublic(BaseModel):
    """Participant-facing view of a due demographic field (API #20)."""

    id: uuid.UUID
    label: str
    field_type: FieldType
    options: list[str] | None
    required: bool

    model_config = {"from_attributes": True}


class DemographicAnswerIn(BaseModel):
    field_id: uuid.UUID
    value: str = Field(max_length=2000)


class DemographicAnswersRequest(BaseModel):
    answers: list[DemographicAnswerIn]


class DemographicResponseOut(BaseModel):
    participant_code: str
    session_code: str | None
    field_label: str
    field_type: FieldType
    value: str
    answered_at_iso: str
