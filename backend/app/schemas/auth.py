from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    user: UserPublic


class AccessTokenResponse(BaseModel):
    access_token: str


class ParticipantLoginRequest(BaseModel):
    code: str
    password: str


class ParticipantPublic(BaseModel):
    id: uuid.UUID
    code: str
    study_name: str


class ParticipantTokenResponse(BaseModel):
    access_token: str
    participant: ParticipantPublic


class ParticipantCheckRequest(BaseModel):
    code: str


class ParticipantCheckResponse(BaseModel):
    password_set: bool


class ParticipantSetPasswordRequest(BaseModel):
    code: str
    password: str = Field(min_length=6)
