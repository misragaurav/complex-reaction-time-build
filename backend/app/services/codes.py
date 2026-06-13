"""Code generation for participant codes (FR-16) and session codes (FR-19)."""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.models import Participant
from app.models import Session as SessionModel

# Unambiguous alphabet (no 0/O, 1/I/L) per FR-16.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _random_code(length: int) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def generate_participant_code(db: OrmSession, prefix: str | None) -> str:
    """Generate a globally-unique participant code `{PREFIX-}XXXX`."""
    prefix_part = f"{prefix}-" if prefix else ""
    while True:
        candidate = f"{prefix_part}{_random_code(4)}"
        exists = db.execute(select(Participant.id).where(Participant.code == candidate)).first()
        if exists is None:
            return candidate


def generate_session_code(db: OrmSession) -> str:
    """Generate a globally-unique 8-character session code."""
    while True:
        candidate = _random_code(8)
        exists = db.execute(select(SessionModel.id).where(SessionModel.code == candidate)).first()
        if exists is None:
            return candidate
