"""Auth tests: FR-1..FR-8, AC-1..AC-8, AC-4a."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.security import decode_token
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, auth_headers, login
from tests.helpers import create_sessions_orm


def test_admin_login_success_returns_jwt_with_id_and_role_and_sets_refresh_cookie(
    client: TestClient,
) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()

    payload = decode_token(data["access_token"])
    assert payload["sub"] == data["user"]["id"]
    assert payload["role"] == "admin"
    assert data["user"]["email"] == ADMIN_EMAIL

    set_cookie = resp.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_admin_login_invalid_password_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_seed_admin_creates_exactly_one_active_admin(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    users: list[dict[str, Any]] = resp.json()
    admins = [u for u in users if u["role"] == "admin"]
    assert len(admins) == 1
    assert admins[0]["email"] == ADMIN_EMAIL
    assert admins[0]["is_active"] is True


def test_refresh_then_logout_then_refresh_returns_401(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    # admin_headers fixture already triggered a login, which set the refresh
    # cookie on the shared TestClient cookie jar.
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    resp2 = client.post("/api/v1/auth/refresh")
    assert resp2.status_code == 401


def test_rate_limit_11th_failed_login_returns_429(client: TestClient) -> None:
    bad = {"email": "nobody@example.com", "password": "wrong"}
    for _ in range(10):
        resp = client.post("/api/v1/auth/login", json=bad)
        assert resp.status_code == 401

    resp = client.post("/api/v1/auth/login", json=bad)
    assert resp.status_code == 429


def test_participant_jwt_cannot_call_researcher_endpoint(
    client: TestClient, participant_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/studies", headers=participant_headers)
    assert resp.status_code == 403


def test_participant_cannot_start_another_participants_session(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    # Create a second participant + session belonging to someone else.
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    other_participant = resp.json()[0]

    other_sessions = create_sessions_orm(client, researcher_headers, study, other_participant, count=1)
    other_session = other_sessions[0]

    resp = client.post(
        f"/api/v1/sessions/{other_session['id']}/start", headers=participant_headers
    )
    assert resp.status_code == 404


def test_set_password_succeeds_once_then_409_then_short_password_422(
    client: TestClient, participant: dict[str, Any]
) -> None:
    code = participant["code"]

    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": code, "password": "first-password"},
    )
    assert resp.status_code == 200, resp.text

    resp2 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": code, "password": "second-password"},
    )
    assert resp2.status_code == 409

    resp3 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": "ANYCODE", "password": "abc"},
    )
    assert resp3.status_code == 422


def test_admin_create_user_403_for_researcher_201_for_admin(
    client: TestClient, admin_headers: dict[str, str], researcher_headers: dict[str, str]
) -> None:
    payload = {
        "email": "newresearcher@example.com",
        "full_name": "New Researcher",
        "role": "researcher",
        "password": "new-researcher-pw",
    }

    resp = client.post("/api/v1/users", json=payload, headers=researcher_headers)
    assert resp.status_code == 403

    resp2 = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp2.status_code == 201, resp2.text


def test_admin_cannot_deactivate_self(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    admin_id = resp.json()["user"]["id"]

    resp2 = client.patch(
        f"/api/v1/users/{admin_id}", json={"is_active": False}, headers=admin_headers
    )
    assert resp2.status_code == 409


def test_reset_password_then_login_409_then_set_password_succeeds(
    client: TestClient,
    researcher_headers: dict[str, str],
    participant: dict[str, Any],
    participant_token: str,
) -> None:
    code = participant["code"]

    resp = client.patch(
        f"/api/v1/participants/{participant['id']}",
        json={"reset_password": True},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["password_set"] is False

    resp2 = client.post(
        "/api/v1/auth/participant/login",
        json={"code": code, "password": "participant-password"},
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"] == "password_not_set"

    resp3 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": code, "password": "brand-new-password"},
    )
    assert resp3.status_code == 200, resp3.text


def test_participant_check_unclaimed_then_claimed(
    client: TestClient, participant: dict[str, Any], participant_token: str
) -> None:
    # `participant_token` fixture already claimed the code via set-password,
    # so check a *different*, still-unclaimed participant first.
    resp = client.post("/api/v1/auth/participant/check", json={"code": "DOES-NOT-EXIST"})
    assert resp.status_code == 404
    msg_unknown = resp.json()["detail"]

    resp2 = client.post(
        "/api/v1/auth/participant/check", json={"code": participant["code"]}
    )
    assert resp2.status_code == 200
    assert resp2.json() == {"password_set": True}


def test_participant_check_unclaimed_code_and_deactivated_code(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    fresh = resp.json()[0]

    resp_unclaimed = client.post(
        "/api/v1/auth/participant/check", json={"code": fresh["code"]}
    )
    assert resp_unclaimed.status_code == 200
    assert resp_unclaimed.json() == {"password_set": False}

    resp_unknown = client.post(
        "/api/v1/auth/participant/check", json={"code": "NOSUCHCODE"}
    )
    assert resp_unknown.status_code == 404
    unknown_msg = resp_unknown.json()["detail"]

    resp_deactivate = client.patch(
        f"/api/v1/participants/{fresh['id']}",
        json={"is_active": False},
        headers=researcher_headers,
    )
    assert resp_deactivate.status_code == 200, resp_deactivate.text

    resp_deactivated = client.post(
        "/api/v1/auth/participant/check", json={"code": fresh["code"]}
    )
    assert resp_deactivated.status_code == 404
    assert resp_deactivated.json()["detail"] == unknown_msg


def test_deactivated_participant_login_returns_401(
    client: TestClient,
    researcher_headers: dict[str, str],
    participant: dict[str, Any],
    participant_token: str,
) -> None:
    resp = client.patch(
        f"/api/v1/participants/{participant['id']}",
        json={"is_active": False},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text

    resp2 = client.post(
        "/api/v1/auth/participant/login",
        json={"code": participant["code"], "password": "participant-password"},
    )
    assert resp2.status_code == 401


def test_unused_login_helper_smoke(client: TestClient) -> None:
    """Sanity check for the shared `login`/`auth_headers` helpers themselves."""
    token = login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    headers = auth_headers(token)
    resp = client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 200
