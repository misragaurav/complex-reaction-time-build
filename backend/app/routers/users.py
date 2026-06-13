from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import AdminUserDep, DbDep
from app.models import User
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(admin: AdminUserDep, db: DbDep) -> list[User]:
    return list(db.execute(select(User).order_by(User.created_at)).scalars().all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, admin: AdminUserDep, db: DbDep) -> User:
    email = payload.email.lower()
    existing = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = User(
        email=email,
        full_name=payload.full_name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, payload: UserUpdate, admin: AdminUserDep, db: DbDep) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.is_active is False and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cannot deactivate your own account"
        )

    if payload.email is not None:
        new_email = payload.email.lower()
        existing = db.execute(
            select(User).where(func.lower(User.email) == new_email, User.id != user.id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = new_email

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return user
