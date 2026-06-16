"""MOD-4: participant group schemas (API #34-39)."""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

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


class ReassignedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    previous_group_name: str
    new_group_name: str


class BlockedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    current_group_name: str
    reason: str


class GroupAssignResponse(BaseModel):
    assigned: list[AssignedItem]
    conflicts: list[ConflictItem]
    reassigned: list[ReassignedItem]
    blocked: list[BlockedItem]


# MOD-5: group activation/deactivation schemas (MFR-31/32).
# MOD-8: session_type extended to include "onboarding" (MFR-110).

class GroupActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_type: Literal["onboarding", "pre", "post"] = "pre"


class GroupActivatedItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    display_label: str
    session_type: str
    order_index: int


class GroupActivateResponse(BaseModel):
    activated: list[GroupActivatedItem]
    session_type: str


class BlockingItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    status: str
    session_type: str
    display_label: str


class GroupDeactivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # MOD-8: session_type mirrors GroupActivateRequest (MFR-110).
    session_type: Literal["onboarding", "pre", "post"] = "pre"
    force: bool = False


class GroupExpiredItem(BaseModel):
    participant_id: uuid.UUID
    code: str
    session_id: uuid.UUID
    display_label: str


class GroupDeactivateResponse(BaseModel):
    expired: list[GroupExpiredItem]
    in_progress_count: int
