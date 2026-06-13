"""In-memory rate limiting for auth endpoints (FR-6).

A simple, process-local counter keyed by identifier (email or participant
code, lower-cased). Suitable for the single-process deployment described in
the PRD; documented as in-memory per FR-6 ("in-memory or DB-backed counter").
"""

from __future__ import annotations

import datetime
import threading

from fastapi import HTTPException, status

WINDOW = datetime.timedelta(minutes=15)
MAX_FAILED_ATTEMPTS = 10

_lock = threading.Lock()
_failed_attempts: dict[str, list[datetime.datetime]] = {}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _prune(identifier: str, now: datetime.datetime) -> list[datetime.datetime]:
    attempts = _failed_attempts.get(identifier, [])
    attempts = [t for t in attempts if now - t < WINDOW]
    _failed_attempts[identifier] = attempts
    return attempts


def check_rate_limit(identifier: str) -> None:
    """Raise 429 if `identifier` has reached the failed-attempt limit."""
    key = identifier.strip().lower()
    now = _now()
    with _lock:
        attempts = _prune(key, now)
        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Please try again later.",
            )


def record_failure(identifier: str) -> None:
    key = identifier.strip().lower()
    now = _now()
    with _lock:
        attempts = _prune(key, now)
        attempts.append(now)
        _failed_attempts[key] = attempts


def record_success(identifier: str) -> None:
    key = identifier.strip().lower()
    with _lock:
        _failed_attempts.pop(key, None)


def reset_all() -> None:
    """Test helper: clear all rate-limit state."""
    with _lock:
        _failed_attempts.clear()
