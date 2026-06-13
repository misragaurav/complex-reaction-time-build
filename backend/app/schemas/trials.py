from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Block = Literal["practice", "test"]
Outcome = Literal["correct", "incorrect", "timeout", "invalid"]
InvalidReason = Literal["focus_loss", "fullscreen_exit"]


class TrialIn(BaseModel):
    """One row of `TrialIn` per §8 (`POST /sessions/{id}/trials`)."""

    model_config = ConfigDict(extra="forbid")

    client_uuid: uuid.UUID
    attempt: int = Field(ge=1)
    block: Block
    trial_index: int = Field(ge=1)
    stimulus_position: int = Field(ge=0)
    foreperiod_ms: int = Field(ge=0)
    key_pressed: str | None = None
    response_position: int | None = Field(default=None, ge=0)
    outcome: Outcome
    rt_ms: float | None = None
    premature_count: int = Field(default=0, ge=0)
    extraneous_keys: int = Field(default=0, ge=0)
    invalid_reason: InvalidReason | None = None
    stimulus_onset_client_ms: float | None = None
    response_client_ms: float | None = None


class TrialBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trials: list[TrialIn] = Field(min_length=1, max_length=25)


class TrialBatchResponse(BaseModel):
    accepted: int


class TrialOut(BaseModel):
    id: int
    client_uuid: uuid.UUID
    attempt: int
    block: Block
    trial_index: int
    stimulus_position: int
    foreperiod_ms: int
    key_pressed: str | None
    response_position: int | None
    outcome: Outcome
    rt_ms: float | None
    premature_count: int
    extraneous_keys: int
    invalid_reason: str | None
    outlier_flag: bool
    stimulus_onset_client_ms: float | None
    response_client_ms: float | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ClientEnvIn(BaseModel):
    """FR-43 payload, recorded once per session start."""

    model_config = ConfigDict(extra="forbid")

    user_agent: str = Field(max_length=512)
    screen_width: int = Field(ge=0)
    screen_height: int = Field(ge=0)
    device_pixel_ratio: float = Field(gt=0)
    refresh_rate_hz: float = Field(gt=0)
    timezone: str = Field(max_length=64)
