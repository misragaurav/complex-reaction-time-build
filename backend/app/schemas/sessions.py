from __future__ import annotations

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import TaskParams, TaskType
from app.schemas.demographics import DemographicFieldPublic

SessionStatus = Literal["created", "in_progress", "completed", "abandoned", "cancelled"]


class SessionOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType | None = None
    params: dict[str, Any] | None = None


class SessionCreateRequest(BaseModel):
    """`{participant_ids:[...], count, overrides?:{task_type?, params?}}` per API #15."""

    model_config = ConfigDict(extra="forbid")

    participant_ids: list[uuid.UUID] = Field(min_length=1)
    count: int = Field(ge=1, le=50)
    overrides: SessionOverrides | None = None


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
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    last_activity_at: datetime.datetime | None
    created_at: datetime.datetime
    stats: SessionStatsBrief


class SessionActionRequest(BaseModel):
    """`{action: "reset" | "cancel"}` per API #17 (FR-22/23)."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["reset", "cancel"]


class MySessionOut(BaseModel):
    """Participant's own session list (API #19)."""

    id: uuid.UUID
    code: str
    order_index: int
    task_type: TaskType
    status: SessionStatus
    attempt: int
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    locked: bool


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
