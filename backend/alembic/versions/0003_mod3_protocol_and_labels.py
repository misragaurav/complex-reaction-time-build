"""MOD-3: study protocol config + session labelling fields

Adds the longitudinal-protocol configuration columns to ``studies`` and the
session-labelling columns to ``sessions`` (with a D2 backfill of any
pre-existing session rows), plus the protocol lookup index.

CHECK constraints are emitted on PostgreSQL (the production target). On SQLite
they are omitted here — SQLite dev/test schemas are built from the models via
``create_all`` (which includes the constraints), and SQLite cannot ALTER-ADD a
CHECK without a full table rebuild.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-13 00:00:01.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECKS = [
    ("ck_studies_num_intervention_sessions", "studies", "num_intervention_sessions BETWEEN 1 AND 156"),
    ("ck_studies_sessions_per_week", "studies", "sessions_per_week BETWEEN 1 AND 7"),
    ("ck_studies_tt_onboarding", "studies", "task_type_onboarding IN ('SRT','CRT2','CRT3','CRT4')"),
    ("ck_studies_tt_pre", "studies", "task_type_pre IN ('SRT','CRT2','CRT3','CRT4')"),
    ("ck_studies_tt_post", "studies", "task_type_post IN ('SRT','CRT2','CRT3','CRT4')"),
    ("ck_sessions_session_type", "sessions", "session_type IN ('onboarding','pre','post')"),
    (
        "ck_sessions_intervention_number",
        "sessions",
        "intervention_session_number IS NULL OR intervention_session_number BETWEEN 1 AND 156",
    ),
    ("ck_sessions_week_number", "sessions", "week_number IS NULL OR week_number >= 1"),
    (
        "ck_sessions_day_within_week",
        "sessions",
        "day_within_week IS NULL OR day_within_week BETWEEN 1 AND 7",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # --- studies protocol-config columns ---
    op.add_column("studies", sa.Column("num_intervention_sessions", sa.Integer(), nullable=False, server_default="24"))
    op.add_column("studies", sa.Column("sessions_per_week", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("studies", sa.Column("task_type_onboarding", sa.String(10), nullable=False, server_default="CRT4"))
    op.add_column("studies", sa.Column("task_type_pre", sa.String(10), nullable=False, server_default="CRT4"))
    op.add_column("studies", sa.Column("task_type_post", sa.String(10), nullable=False, server_default="CRT4"))

    # --- sessions labelling columns ---
    op.add_column("sessions", sa.Column("session_type", sa.String(12), nullable=False, server_default="pre"))
    op.add_column("sessions", sa.Column("intervention_session_number", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("week_number", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("day_within_week", sa.Integer(), nullable=True))
    op.add_column("sessions", sa.Column("display_label", sa.String(80), nullable=False, server_default=""))
    op.add_column(
        "sessions",
        sa.Column("display_label_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # --- D2 backfill: existing sessions become 'pre' with derived labels ---
    rows = bind.execute(
        sa.text(
            "SELECT s.id AS id, s.order_index AS oi, st.sessions_per_week AS spw "
            "FROM sessions s JOIN studies st ON st.id = s.study_id"
        )
    ).fetchall()
    for row in rows:
        spw = row.spw or 3
        oi = row.oi
        week = (oi + spw - 1) // spw  # ceil(oi / spw)
        day = ((oi - 1) % spw) + 1
        bind.execute(
            sa.text(
                "UPDATE sessions SET intervention_session_number=:n, week_number=:w, "
                "day_within_week=:d, display_label=:lbl WHERE id=:id"
            ),
            {"n": oi, "w": week, "d": day, "lbl": f"Session {oi}", "id": row.id},
        )

    op.create_index(
        "ix_sessions_protocol", "sessions", ["study_id", "session_type", "intervention_session_number"]
    )

    if is_pg:
        for name, table, condition in _CHECKS:
            op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        for name, table, _ in _CHECKS:
            op.drop_constraint(name, table, type_="check")

    op.drop_index("ix_sessions_protocol", table_name="sessions")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("display_label_overridden")
        batch_op.drop_column("display_label")
        batch_op.drop_column("day_within_week")
        batch_op.drop_column("week_number")
        batch_op.drop_column("intervention_session_number")
        batch_op.drop_column("session_type")

    with op.batch_alter_table("studies") as batch_op:
        batch_op.drop_column("task_type_post")
        batch_op.drop_column("task_type_pre")
        batch_op.drop_column("task_type_onboarding")
        batch_op.drop_column("sessions_per_week")
        batch_op.drop_column("num_intervention_sessions")
