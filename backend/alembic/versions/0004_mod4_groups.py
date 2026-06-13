"""MOD-4: participant groups

Creates the ``groups`` and ``participant_group_assignments`` tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-13 00:00:02.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db_types import GUID

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groups",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("study_id", GUID(), sa.ForeignKey("studies.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("current_intervention_session", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("study_id", "name", name="uq_groups_study_name"),
        sa.CheckConstraint(
            "current_intervention_session IS NULL OR current_intervention_session BETWEEN 1 AND 52",
            name="ck_groups_current_intervention_session",
        ),
    )

    op.create_table(
        "participant_group_assignments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "participant_id",
            GUID(),
            sa.ForeignKey("participants.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("group_id", GUID(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column(
            "assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_pga_group", "participant_group_assignments", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_pga_group", table_name="participant_group_assignments")
    op.drop_table("participant_group_assignments")
    op.drop_table("groups")
