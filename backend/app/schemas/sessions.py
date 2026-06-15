from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator

from app.schemas.common import TaskParams, TaskType
from app.schemas.demographics import DemographicFieldPublic

SessionStatus = Literal["created", "activated", "in_progress", "completed", "abandoned", "expired", "cancelled"]  # MOD-5
SessionType = Literal["onboarding", "pre", "post"]  # MOD-3



class SessionStatsBrief(BaseModel):
    """FR-50 row stats: trimmed mean RT, accuracy, and outlier-flag count."""

    trimmed_mean_rt_ms: float | None
    accuracy_pct: float | None
    n_outliers_flagged: int


class SessionOut(BaseModel):
    id: uuid.UUID
    code: str
    participant_id: uuid.UUID
    participant_code: str
    study_id: uuid.UUID
    order_index: int
    task_type: TaskType
    params: TaskParams
    status: SessionStatus
    attempt: int
    resume_count: int
    # MOD-3 labelling fields.
    session_type: SessionType
    intervention_session_number: int | None
    week_number: int | None
    day_within_week: int | None
    display_label: str
    display_label_overridden: bool
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    last_activity_at: datetime.datetime | None
    activated_at: datetime.datetime | None  # MOD-5
    expired_at: datetime.datetime | None  # MOD-5
    created_at: datetime.datetime
    stats: SessionStatsBrief
    # MOD-11: group membership at query time (null when unassigned).
    group_id: uuid.UUID | None = None
    group_name: str | None = None


class SessionActionRequest(BaseModel):
    """`{action: "reset" | "cancel"}` per API #17 (FR-22/23), extended by MOD-3
    to also accept `{display_label: "..."}` to relabel a session (MFR-14)."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["reset", "cancel"] | None = None
    display_label: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def _exactly_one(self) -> "SessionActionRequest":
        provided = [self.action is not None, self.display_label is not None]
        if sum(provided) != 1:
            raise ValueError("provide exactly one of 'action' or 'display_label'")
        return self


class MySessionOut(BaseModel):
    """Participant's own session list (API #19)."""

    id: uuid.UUID
    code: str
    order_index: int
    task_type: TaskType
    status: SessionStatus
    attempt: int
    # MOD-3 labelling (MFR-19).
    session_type: SessionType
    display_label: str
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    activated_at: datetime.datetime | None  # MOD-5
    expired_at: datetime.datetime | None  # MOD-5
    locked: bool


class GenerateProtocolRequest(BaseModel):
    """`POST /studies/{id}/generate-protocol` (API #33, MFR-18)."""

    model_config = ConfigDict(extra="forbid")

    participant_ids: list[uuid.UUID] | None = None
    num_intervention_sessions: int | None = Field(default=None, ge=1, le=156)
    week_start: int = Field(default=1, ge=1, le=52)


class ProtocolCreatedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_count: int


class ProtocolSkippedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    reason: str


class GenerateProtocolResponse(BaseModel):
    created: list[ProtocolCreatedItem]
    skipped: list[ProtocolSkippedItem]


class StoredTrials(BaseModel):
    practice: list[int]
    test: list[int]


class SessionStartResponse(BaseModel):
    """Response of `POST /sessions/{id}/start` (API #20)."""

    params: TaskParams
    task_type: TaskType
    attempt: int
    demographics_due: list[DemographicFieldPublic]
    stored_trials: StoredTrials


class PreviewResponse(BaseModel):
    """Response of `POST /studies/{id}/preview` (API #32, FR-33)."""

    params: TaskParams
    task_type: TaskType
