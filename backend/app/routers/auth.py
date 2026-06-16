from __future__ import annotations

import datetime
import uuid

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import DbDep
from app.models import Participant, User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    ParticipantCheckRequest,
    ParticipantCheckResponse,
    ParticipantLoginRequest,
    ParticipantPublic,
    ParticipantSetPasswordRequest,
    ParticipantTokenResponse,
    TokenResponse,
    UserPublic,
)
from app.security import (
    PARTICIPANT_REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    refresh_cookie_kwargs,
    verify_password,
)
from app.services.rate_limit import check_rate_limit, record_failure, record_success

router = APIRouter(prefix="/auth", tags=["auth"])

CODE_NOT_RECOGNIZED = "Code not recognized. Contact your researcher."


def _refresh_max_age() -> int:
    settings = get_settings()
    return int(datetime.timedelta(days=settings.refresh_token_expire_days).total_seconds())


# --- 1. Admin / researcher login -------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: DbDep) -> TokenResponse:
    identifier = payload.email.lower()
    check_rate_limit(identifier)

    user = db.execute(
        select(User).where(func.lower(User.email) == identifier)
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        record_failure(identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        record_failure(identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    record_success(identifier)

    access_token = create_access_token(sub=str(user.id), role=user.role)  # type: ignore[arg-type]
    refresh_token = create_refresh_token(sub=str(user.id), role=user.role)  # type: ignore[arg-type]

    settings = get_settings()
    response.set_cookie(
        value=refresh_token,
        **refresh_cookie_kwargs(settings, _refresh_max_age()),
    )

    return TokenResponse(
        access_token=access_token,
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
    )


# --- 2. Refresh access token (researcher/admin realm) -------------------------------------------
@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    db: DbDep,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    role = payload.get("role")
    try:
        sub = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    # Defense-in-depth: reject participant tokens on the researcher refresh endpoint.
    if role not in ("admin", "researcher"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong auth realm")

    user = db.get(User, sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    access_token = create_access_token(sub=str(user.id), role=user.role)  # type: ignore[arg-type]

    return AccessTokenResponse(access_token=access_token)


# --- 2a. Refresh access token (participant realm) ------------------------------------------------
@router.post("/participant/refresh", response_model=AccessTokenResponse)
def participant_refresh(
    db: DbDep,
    refresh_token: str | None = Cookie(default=None, alias=PARTICIPANT_REFRESH_COOKIE_NAME),
) -> AccessTokenResponse:
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        ) from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    role = payload.get("role")
    try:
        sub = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    # Defense-in-depth: only participant tokens are valid here.
    if role != "participant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong auth realm")

    participant = db.get(Participant, sub)
    if participant is None or not participant.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    access_token = create_access_token(sub=str(participant.id), role="participant")

    return AccessTokenResponse(access_token=access_token)


# --- 3. Logout -------------------------------------------------------------------------------------
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    settings = get_settings()
    # Clear both realm cookies so a single logout button works regardless of
    # which realm is active in this browser tab.
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    response.delete_cookie(
        key=PARTICIPANT_REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )


# --- 4. Participant login ---------------------------------------------------------------------
@router.post("/participant/login", response_model=ParticipantTokenResponse)
def participant_login(
    payload: ParticipantLoginRequest, response: Response, db: DbDep
) -> ParticipantTokenResponse:
    code = payload.code.strip().upper()
    check_rate_limit(code)

    participant = db.execute(
        select(Participant).where(Participant.code == code)
    ).scalar_one_or_none()

    if participant is None or not participant.is_active:
        record_failure(code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code or password")

    if participant.password_hash is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="password_not_set")

    if not verify_password(payload.password, participant.password_hash):
        record_failure(code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code or password")

    record_success(code)
    participant.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(participant)

    return _participant_token_response(participant, response)


# --- 4a. Check participant code -----------------------------------------------------------------
@router.post("/participant/check", response_model=ParticipantCheckResponse)
def participant_check(payload: ParticipantCheckRequest, db: DbDep) -> ParticipantCheckResponse:
    code = payload.code.strip().upper()
    check_rate_limit(code)

    participant = db.execute(
        select(Participant).where(Participant.code == code)
    ).scalar_one_or_none()

    if participant is None or not participant.is_active:
        record_failure(code)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CODE_NOT_RECOGNIZED)

    record_success(code)
    return ParticipantCheckResponse(password_set=participant.password_hash is not None)


# --- 5. Set participant password ----------------------------------------------------------------
@router.post("/participant/set-password", response_model=ParticipantTokenResponse)
def participant_set_password(
    payload: ParticipantSetPasswordRequest, response: Response, db: DbDep
) -> ParticipantTokenResponse:
    code = payload.code.strip().upper()
    check_rate_limit(code)

    participant = db.execute(
        select(Participant).where(Participant.code == code)
    ).scalar_one_or_none()

    if participant is None or not participant.is_active:
        record_failure(code)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CODE_NOT_RECOGNIZED)

    if participant.password_hash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Password has already been set"
        )

    record_success(code)
    participant.password_hash = hash_password(payload.password)
    participant.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(participant)

    return _participant_token_response(participant, response)


def _participant_token_response(
    participant: Participant, response: Response
) -> ParticipantTokenResponse:
    access_token = create_access_token(sub=str(participant.id), role="participant")
    refresh_token = create_refresh_token(sub=str(participant.id), role="participant")

    settings = get_settings()
    response.set_cookie(
        value=refresh_token,
        **refresh_cookie_kwargs(settings, _refresh_max_age(), name=PARTICIPANT_REFRESH_COOKIE_NAME),
    )

    return ParticipantTokenResponse(
        access_token=access_token,
        participant=ParticipantPublic(
            id=participant.id, code=participant.code, study_name=participant.study.name
        ),
    )
