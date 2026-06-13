"""Initial admin seeding (FR-7)."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import hash_password

logger = logging.getLogger("app.seed")


def seed_admin() -> None:
    """If no admin exists, create one from ADMIN_EMAIL/ADMIN_PASSWORD.

    Logs a warning either way: prompting a password change after creation,
    or noting that seeding was skipped because env vars are unset.
    """
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = db.execute(select(User).where(User.role == "admin")).first()
        if existing is not None:
            return
        if not settings.admin_email or not settings.admin_password:
            logger.warning(
                "No admin account exists and ADMIN_EMAIL/ADMIN_PASSWORD are not "
                "set. Set these environment variables and restart the "
                "application to create the initial admin account."
            )
            return
        admin = User(
            email=settings.admin_email.strip().lower(),
            password_hash=hash_password(settings.admin_password),
            full_name="Administrator",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        logger.warning(
            "Created initial admin account '%s'. Please log in and change the "
            "password as soon as possible.",
            admin.email,
        )
    finally:
        db.close()
