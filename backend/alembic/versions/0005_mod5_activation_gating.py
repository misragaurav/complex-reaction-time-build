"""MOD-5: session activation gating

Widens ``sessions.status`` CHECK to include ``'activated'`` and ``'expired'``;
adds ``activated_at``, ``expired_at``, and ``activated_by`` columns (MFR-28..30).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-13 00:00:03.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.db_types import GUID

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_STATUS = (
    "status IN ('created','activated','in_progress','completed','abandoned','expired','cancelled')"
)
_OLD_STATUS = (
    "status IN ('created','in_progress','completed','abandoned','cancelled')"
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_sessions_status", "sessions", type_="check")
        op.create_check_constraint("ck_sessions_status", "sessions", _NEW_STATUS)
        op.add_column("sessions", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column("sessions", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(
            "sessions",
            sa.Column("activated_by", GUID(), sa.ForeignKey("users.id"), nullable=True),
        )
    else:
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.drop_constraint("ck_sessions_status", type_="check")
            batch_op.create_check_constraint("ck_sessions_status", _NEW_STATUS)
            batch_op.add_column(sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(
                sa.Column("activated_by", GUID(), sa.ForeignKey("users.id"), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_sessions_status", "sessions", type_="check")
        op.create_check_constraint("ck_sessions_status", "sessions", _OLD_STATUS)
        op.drop_column("sessions", "activated_at")
        op.drop_column("sessions", "expired_at")
        op.drop_column("sessions", "activated_by")
    else:
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.drop_constraint("ck_sessions_status", type_="check")
            batch_op.create_check_constraint("ck_sessions_status", _OLD_STATUS)
            batch_op.drop_column("activated_at")
            batch_op.drop_column("expired_at")
            batch_op.drop_column("activated_by")
