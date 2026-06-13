"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-10 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db_types import GUID, BigIntegerVariant, JSONVariant

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role IN ('admin','researcher')", name="ck_users_role"),
    )
    op.create_index("ux_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "studies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(10), nullable=False),
        sa.Column("params", JSONVariant, nullable=False),
        sa.Column("created_by", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("task_type IN ('CRT2','CRT3','CRT4')", name="ck_studies_task_type"),
    )

    op.create_table(
        "participants",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("study_id", GUID(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "demographic_fields",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("study_id", GUID(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("options", JSONVariant, nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_retired", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "field_type IN ('text','number','single_choice','boolean')",
            name="ck_demo_fields_field_type",
        ),
        sa.CheckConstraint(
            "frequency IN ('once','every_session')", name="ck_demo_fields_frequency"
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("participant_id", GUID(), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("study_id", GUID(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(10), nullable=False),
        sa.Column("params", JSONVariant, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("resume_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_env", JSONVariant, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("task_type IN ('CRT2','CRT3','CRT4')", name="ck_sessions_task_type"),
        sa.CheckConstraint(
            "status IN ('created','in_progress','completed','abandoned','cancelled')",
            name="ck_sessions_status",
        ),
        sa.UniqueConstraint("participant_id", "order_index", name="uq_sessions_participant_order"),
    )

    op.create_table(
        "demographic_responses",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("participant_id", GUID(), sa.ForeignKey("participants.id"), nullable=False),
        sa.Column("field_id", GUID(), sa.ForeignKey("demographic_fields.id"), nullable=False),
        sa.Column("session_id", GUID(), sa.ForeignKey("sessions.id"), nullable=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ux_demo_resp_once",
        "demographic_responses",
        ["participant_id", "field_id"],
        unique=True,
        sqlite_where=sa.text("session_id IS NULL"),
        postgresql_where=sa.text("session_id IS NULL"),
    )
    op.create_index(
        "ux_demo_resp_session",
        "demographic_responses",
        ["participant_id", "field_id", "session_id"],
        unique=True,
        sqlite_where=sa.text("session_id IS NOT NULL"),
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )

    op.create_table(
        "trials",
        sa.Column("id", BigIntegerVariant, primary_key=True, autoincrement=True),
        sa.Column("client_uuid", GUID(), nullable=False, unique=True),
        sa.Column("session_id", GUID(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("block", sa.String(10), nullable=False),
        sa.Column("trial_index", sa.Integer(), nullable=False),
        sa.Column("stimulus_position", sa.Integer(), nullable=False),
        sa.Column("foreperiod_ms", sa.Integer(), nullable=False),
        sa.Column("key_pressed", sa.String(20), nullable=True),
        sa.Column("response_position", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("rt_ms", sa.Numeric(7, 1), nullable=True),
        sa.Column("premature_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraneous_keys", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_reason", sa.String(20), nullable=True),
        sa.Column("outlier_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stimulus_onset_client_ms", sa.Numeric(12, 1), nullable=True),
        sa.Column("response_client_ms", sa.Numeric(12, 1), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("block IN ('practice','test')", name="ck_trials_block"),
        sa.CheckConstraint(
            "outcome IN ('correct','incorrect','timeout','invalid')", name="ck_trials_outcome"
        ),
        sa.UniqueConstraint(
            "session_id", "attempt", "block", "trial_index", name="uq_trials_session_attempt_index"
        ),
    )
    op.create_index("ix_trials_session_attempt_block", "trials", ["session_id", "attempt", "block"])


def downgrade() -> None:
    op.drop_index("ix_trials_session_attempt_block", table_name="trials")
    op.drop_table("trials")
    op.drop_index("ux_demo_resp_session", table_name="demographic_responses")
    op.drop_index("ux_demo_resp_once", table_name="demographic_responses")
    op.drop_table("demographic_responses")
    op.drop_table("sessions")
    op.drop_table("demographic_fields")
    op.drop_table("participants")
    op.drop_table("studies")
    op.drop_index("ux_users_email_lower", table_name="users")
    op.drop_table("users")
