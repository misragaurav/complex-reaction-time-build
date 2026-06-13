"""Shared pytest fixtures.

Sets up a file-based SQLite database (per D-17) *before* importing any
``app.*`` module, since ``app.database`` creates its engine at import time
from ``Settings.resolved_database_url``. Each test gets a fresh schema via
``drop_all``/``create_all`` and a fresh ``TestClient`` (whose lifespan runs
``seed_admin()`` against that schema).
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="crt-backend-tests-")

os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["APP_ENV"] = "development"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "admin-password-123"
os.environ["ALLOWED_ORIGINS"] = ""
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import rate_limit  # noqa: E402

ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture()
def client() -> Iterator[TestClient]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rate_limit.reset_all()
    with TestClient(app) as c:
        yield c


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture()
def admin_headers(admin_token: str) -> dict[str, str]:
    return auth_headers(admin_token)


@pytest.fixture()
def researcher_headers(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    resp = client.post(
        "/api/v1/users",
        json={
            "email": "researcher@example.com",
            "full_name": "Resea Rcher",
            "role": "researcher",
            "password": "researcher-password",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    token = login(client, "researcher@example.com", "researcher-password")
    return auth_headers(token)


@pytest.fixture()
def study(client: TestClient, researcher_headers: dict[str, str]) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/studies",
        json={"name": "Test Study", "task_type": "CRT3"},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


@pytest.fixture()
def participant(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    data: list[dict[str, Any]] = resp.json()
    return data[0]


@pytest.fixture()
def participant_token(client: TestClient, participant: dict[str, Any]) -> str:
    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "participant-password"},
    )
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


@pytest.fixture()
def participant_headers(participant_token: str) -> dict[str, str]:
    return auth_headers(participant_token)


@pytest.fixture()
def session(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant: dict[str, Any],
) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": [participant["id"]], "count": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    data: list[dict[str, Any]] = resp.json()
    s = data[0]
    # MOD-5: activate immediately so tests can call /start without an extra step.
    resp2 = client.post(f"/api/v1/sessions/{s['id']}/activate", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    return resp2.json()  # return the updated session with status="activated"
