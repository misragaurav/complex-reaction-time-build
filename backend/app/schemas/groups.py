"""MOD-4: participant group schemas (API #34-39)."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200)


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200)
    current_intervention_session: int | None = Field(default=None, ge=1, le=52)


class GroupOut(BaseModel):
    id: uuid.UUID
    study_id: uuid.UUID
    name: str
    description: str | None
    current_intervention_session: int | None
    member_count: int
    created_at: datetime.datetime


class GroupMember(BaseModel):
    participant_id: uuid.UUID
    code: str
    is_active: bool
    sessions_assigned: int
    sessions_completed: int


class GroupCompletionStats(BaseModel):
    total_assigned: int
    completed_pre_overall: int
    completed_post_overall: int
    completed_pre_current: int
    completed_post_current: int


class GroupDetailOut(GroupOut):
    members: list[GroupMember]
    completion: GroupCompletionStats


class GroupAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_ids: list[uuid.UUID] = Field(min_length=1)


class AssignedItem(BaseModel):
    participant_id: uuid.UUID
    code: str


class ConflictItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    current_group_name: str


class GroupAssignResponse(BaseModel):
    assigned: list[AssignedItem]
    conflicts: list[ConflictItem]


# MOD-5: group activation/deactivation schemas (MFR-31/32).

class GroupActivatedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    display_label: str
    session_type: str
    order_index: int


class GroupActivateResponse(BaseModel):
    activated: list[GroupActivatedItem]


class BlockingItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    status: str
    display_label: str


class GroupDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force: bool = False


class GroupExpiredItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    display_label: str


class GroupDeactivateResponse(BaseModel):
    expired: list[GroupExpiredItem]
    in_progress_count: int
