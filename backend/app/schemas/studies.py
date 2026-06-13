from __future__ import annotations

import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import TaskParams, TaskType


class StudyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    task_type: TaskType
    params: dict[str, Any] | None = None
    # MOD-3 protocol configuration (defaults per MFR-11).
    num_intervention_sessions: int = Field(default=24, ge=1, le=156)
    sessions_per_week: int = Field(default=3, ge=1, le=7)
    task_type_onboarding: TaskType = "CRT4"
    task_type_pre: TaskType = "CRT4"
    task_type_post: TaskType = "CRT4"


class StudyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    params: dict[str, Any] | None = None
    is_archived: bool | None = None
    # MOD-3 protocol configuration (subject to the post-generation lock, MFR-12).
    num_intervention_sessions: int | None = Field(default=None, ge=1, le=156)
    sessions_per_week: int | None = Field(default=None, ge=1, le=7)
    task_type_onboarding: TaskType | None = None
    task_type_pre: TaskType | None = None
    task_type_post: TaskType | None = None


class StudyCounts(BaseModel):
    participants: int
    sessions_total: int
    sessions_completed: int
    completion_pct: float


class StudyOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    task_type: TaskType
    params: TaskParams
    # MOD-3 protocol configuration.
    num_intervention_sessions: int
    sessions_per_week: int
    task_type_onboarding: TaskType
    task_type_pre: TaskType
    task_type_post: TaskType
    protocol_locked: bool  # MFR-12: true once any protocol session exists
    created_by: uuid.UUID
    is_archived: bool
    params_locked: bool
    counts: StudyCounts
    created_at: datetime.datetime
    updated_at: datetime.datetime
