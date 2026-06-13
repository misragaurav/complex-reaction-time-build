from __future__ import annotations

import datetime
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]{1,20}$")


class ParticipantCreate(BaseModel):
    """Either bulk (`count`[, `prefix`]) or manual (`codes`) creation, per FR-16."""

    model_config = ConfigDict(extra="forbid")

    count: int | None = Field(default=None, ge=1, le=500)
    prefix: str | None = None
    codes: list[str] | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _validate(self) -> "ParticipantCreate":
        if self.codes is not None:
            if self.count is not None or self.prefix is not None:
                raise ValueError("provide either `codes` or `count`/`prefix`, not both")
            cleaned = []
            seen: set[str] = set()
            for code in self.codes:
                if not CODE_RE.fullmatch(code):
                    raise ValueError(
                        f"invalid code {code!r}: must be 3-32 chars from [A-Za-z0-9_-]"
                    )
                upper = code.upper()
                if upper in seen:
                    raise ValueError(f"duplicate code in request: {upper!r}")
                seen.add(upper)
                cleaned.append(upper)
            self.codes = cleaned
        else:
            if self.count is None:
                raise ValueError("provide either `count` or `codes`")
            if self.prefix is not None:
                if not PREFIX_RE.fullmatch(self.prefix):
                    raise ValueError("prefix must be 1-20 chars from [A-Za-z0-9_-]")
                self.prefix = self.prefix.upper()
        return self


class ParticipantOut(BaseModel):
    id: uuid.UUID
    study_id: uuid.UUID
    code: str
    password_set: bool
    is_active: bool
    sessions_assigned: int
    sessions_completed: int
    last_login_at: datetime.datetime | None
    created_at: datetime.datetime


class ParticipantUpdate(BaseModel):
    """`{is_active?, reset_password?:true}` per API #13."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    reset_password: bool | None = None

    @model_validator(mode="after")
    def _validate(self) -> "ParticipantUpdate":
        if self.reset_password is False:
            raise ValueError("reset_password, if provided, must be true")
        if self.is_active is None and self.reset_password is None:
            raise ValueError("provide at least one of `is_active` or `reset_password`")
        return self
