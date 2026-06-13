"""MOD-2: add 'SRT' to the task_type CHECK constraints

Widens the ``ck_studies_task_type`` and ``ck_sessions_task_type`` CHECK
constraints from ``('CRT2','CRT3','CRT4')`` to ``('SRT','CRT2','CRT3','CRT4')``.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    ("studies", "ck_studies_task_type"),
    ("sessions", "ck_sessions_task_type"),
)
_NEW = "task_type IN ('SRT','CRT2','CRT3','CRT4')"
_OLD = "task_type IN ('CRT2','CRT3','CRT4')"


def _set_check(condition: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table, name in _TABLES:
            op.drop_constraint(name, table, type_="check")
            op.create_check_constraint(name, table, condition)
    else:
        # SQLite cannot ALTER a CHECK constraint in place; recreate via batch.
        for table, name in _TABLES:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(name, type_="check")
                batch_op.create_check_constraint(name, condition)


def upgrade() -> None:
    _set_check(_NEW)


def downgrade() -> None:
    _set_check(_OLD)
