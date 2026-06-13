from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.deps import DbDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbDep) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status}
