from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.db_types import GUID, BigIntegerVariant, JSONVariant


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    """Admin and researcher accounts (§7 `users`)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin','researcher')", name="ck_users_role"),
        Index("ux_users_email_lower", func.lower(email), unique=True),
    )

    studies: Mapped[list["Study"]] = relationship(back_populates="creator")


class Study(Base):
    """§7 `studies`."""

    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    task_type: Mapped[str] = mapped_column(String(10), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("task_type IN ('CRT2','CRT3','CRT4')", name="ck_studies_task_type"),
    )

    creator: Mapped["User"] = relationship(back_populates="studies")
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="study", cascade="all, delete-orphan"
    )
    demographic_fields: Mapped[list["DemographicField"]] = relationship(
        back_populates="study",
        cascade="all, delete-orphan",
        order_by="DemographicField.display_order",
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="study")


class Participant(Base):
    """§7 `participants`."""

    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    study_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("studies.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    study: Mapped["Study"] = relationship(back_populates="participants")
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="participant", order_by="Session.order_index"
    )
    demographic_responses: Mapped[list["DemographicResponse"]] = relationship(
        back_populates="participant"
    )


class DemographicField(Base):
    """§7 `demographic_fields`."""

    __tablename__ = "demographic_fields"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    study_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("studies.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONVariant, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_retired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "field_type IN ('text','number','single_choice','boolean')",
            name="ck_demo_fields_field_type",
        ),
        CheckConstraint(
            "frequency IN ('once','every_session')", name="ck_demo_fields_frequency"
        ),
    )

    study: Mapped["Study"] = relationship(back_populates="demographic_fields")
    responses: Mapped[list["DemographicResponse"]] = relationship(
        back_populates="field", cascade="all, delete-orphan"
    )


class DemographicResponse(Base):
    """§7 `demographic_responses`."""

    __tablename__ = "demographic_responses"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("participants.id"), nullable=False
    )
    field_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("demographic_fields.id"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sessions.id"), nullable=True
    )
    value: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ux_demo_resp_once",
            "participant_id",
            "field_id",
            unique=True,
            postgresql_where=text("session_id IS NULL"),
            sqlite_where=text("session_id IS NULL"),
        ),
        Index(
            "ux_demo_resp_session",
            "participant_id",
            "field_id",
            "session_id",
            unique=True,
            postgresql_where=text("session_id IS NOT NULL"),
            sqlite_where=text("session_id IS NOT NULL"),
        ),
    )

    participant: Mapped["Participant"] = relationship(back_populates="demographic_responses")
    field: Mapped["DemographicField"] = relationship(back_populates="responses")
    session: Mapped["Session | None"] = relationship(back_populates="demographic_responses")


class Session(Base):
    """§7 `sessions`."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("participants.id"), nullable=False
    )
    study_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("studies.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(10), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resume_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    client_env: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("task_type IN ('CRT2','CRT3','CRT4')", name="ck_sessions_task_type"),
        CheckConstraint(
            "status IN ('created','in_progress','completed','abandoned','cancelled')",
            name="ck_sessions_status",
        ),
        UniqueConstraint("participant_id", "order_index", name="uq_sessions_participant_order"),
    )

    participant: Mapped["Participant"] = relationship(back_populates="sessions")
    study: Mapped["Study"] = relationship(back_populates="sessions")
    trials: Mapped[list["Trial"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    demographic_responses: Mapped[list["DemographicResponse"]] = relationship(
        back_populates="session"
    )


class Trial(Base):
    """§7 `trials`."""

    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(BigIntegerVariant, primary_key=True, autoincrement=True)
    client_uuid: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, unique=True)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sessions.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    block: Mapped[str] = mapped_column(String(10), nullable=False)
    trial_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stimulus_position: Mapped[int] = mapped_column(Integer, nullable=False)
    foreperiod_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    key_pressed: Mapped[str | None] = mapped_column(String(20), nullable=True)
    response_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    rt_ms: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    premature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraneous_keys: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outlier_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stimulus_onset_client_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 1), nullable=True)
    response_client_ms: Mapped[Decimal | None] = mapped_column(Numeric(12, 1), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("block IN ('practice','test')", name="ck_trials_block"),
        CheckConstraint(
            "outcome IN ('correct','incorrect','timeout','invalid')", name="ck_trials_outcome"
        ),
        UniqueConstraint(
            "session_id", "attempt", "block", "trial_index", name="uq_trials_session_attempt_index"
        ),
        Index("ix_trials_session_attempt_block", "session_id", "attempt", "block"),
    )

    session: Mapped["Session"] = relationship(back_populates="trials")
