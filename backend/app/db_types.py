from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, BigInteger, CHAR, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

# JSON storage: JSONB on PostgreSQL, plain JSON (TEXT-backed) on SQLite (D-17).
JSONVariant = JSON().with_variant(JSONB(), "postgresql")

# trials.id BIGSERIAL on PostgreSQL; SQLite needs plain INTEGER PRIMARY KEY
# (its ROWID alias) to autoincrement correctly.
BigIntegerVariant = BigInteger().with_variant(Integer(), "sqlite")


class GUID(TypeDecorator[uuid.UUID]):
    """Platform-independent UUID type.

    Uses PostgreSQL's native UUID type, otherwise stores as a 36-char string.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> uuid.UUID | None:
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
