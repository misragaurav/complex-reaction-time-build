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


class StudyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    params: dict[str, Any] | None = None
    is_archived: bool | None = None


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
    created_by: uuid.UUID
    is_archived: bool
    params_locked: bool
    counts: StudyCounts
    created_at: datetime.datetime
    updated_at: datetime.datetime
