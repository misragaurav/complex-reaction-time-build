"""MOD-7: drop per-stage task_type columns from studies

Removes ``task_type_onboarding``, ``task_type_pre``, ``task_type_post`` and
their CHECK constraints.  All session stages now derive their task type from
the single ``studies.task_type`` column.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-15 00:00:00.000000

Note: downgrade() re-adds the columns with default 'CRT4'.  The original
per-stage values are not recoverable from a downgrade.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_studies_tt_onboarding", "studies", type_="check")
        op.drop_constraint("ck_studies_tt_pre", "studies", type_="check")
        op.drop_constraint("ck_studies_tt_post", "studies", type_="check")
        op.drop_column("studies", "task_type_onboarding")
        op.drop_column("studies", "task_type_pre")
        op.drop_column("studies", "task_type_post")
    else:
        with op.batch_alter_table("studies") as batch_op:
            batch_op.drop_constraint("ck_studies_tt_onboarding", type_="check")
            batch_op.drop_constraint("ck_studies_tt_pre", type_="check")
            batch_op.drop_constraint("ck_studies_tt_post", type_="check")
            batch_op.drop_column("task_type_onboarding")
            batch_op.drop_column("task_type_pre")
            batch_op.drop_column("task_type_post")


def downgrade() -> None:
    bind = op.get_bind()
    _check_onboarding = "task_type_onboarding IN ('SRT','CRT2','CRT3','CRT4')"
    _check_pre = "task_type_pre IN ('SRT','CRT2','CRT3','CRT4')"
    _check_post = "task_type_post IN ('SRT','CRT2','CRT3','CRT4')"
    if bind.dialect.name == "postgresql":
        op.add_column(
            "studies",
            sa.Column("task_type_onboarding", sa.String(10), nullable=False, server_default="CRT4"),
        )
        op.add_column(
            "studies",
            sa.Column("task_type_pre", sa.String(10), nullable=False, server_default="CRT4"),
        )
        op.add_column(
            "studies",
            sa.Column("task_type_post", sa.String(10), nullable=False, server_default="CRT4"),
        )
        op.create_check_constraint("ck_studies_tt_onboarding", "studies", _check_onboarding)
        op.create_check_constraint("ck_studies_tt_pre", "studies", _check_pre)
        op.create_check_constraint("ck_studies_tt_post", "studies", _check_post)
    else:
        with op.batch_alter_table("studies") as batch_op:
            batch_op.add_column(
                sa.Column("task_type_onboarding", sa.String(10), nullable=False, server_default="CRT4")
            )
            batch_op.add_column(
                sa.Column("task_type_pre", sa.String(10), nullable=False, server_default="CRT4")
            )
            batch_op.add_column(
                sa.Column("task_type_post", sa.String(10), nullable=False, server_default="CRT4")
            )
            batch_op.create_check_constraint("ck_studies_tt_onboarding", _check_onboarding)
            batch_op.create_check_constraint("ck_studies_tt_pre", _check_pre)
            batch_op.create_check_constraint("ck_studies_tt_post", _check_post)
