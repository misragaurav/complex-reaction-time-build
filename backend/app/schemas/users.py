from __future__ import annotations

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

UserRole = Literal["admin", "researcher"]

# Minimum password length for admin/researcher accounts. Not specified by
# the PRD (which only mandates >=6 chars for participants, FR-3); chosen as
# a stronger default for privileged accounts. See DECISIONS_TAKEN.md.
USER_PASSWORD_MIN_LENGTH = 8


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    password: str = Field(min_length=USER_PASSWORD_MIN_LENGTH)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=USER_PASSWORD_MIN_LENGTH)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
