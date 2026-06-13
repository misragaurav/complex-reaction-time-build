"""User management tests (FR-4): admin-only CRUD, role checks."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import login


def test_list_users_requires_admin(
    client: TestClient, researcher_headers: dict[str, str], participant_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/users", headers=researcher_headers)
    assert resp.status_code == 403

    resp2 = client.get("/api/v1/users", headers=participant_headers)
    assert resp2.status_code == 403


def test_create_user_lowercases_email_and_rejects_duplicates(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    payload = {
        "email": "Mixed.Case@Example.com",
        "full_name": "Mixed Case",
        "role": "researcher",
        "password": "a-strong-password",
    }
    resp = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == "mixed.case@example.com"

    dup = {**payload, "email": "mixed.case@example.com"}
    resp2 = client.post("/api/v1/users", json=dup, headers=admin_headers)
    assert resp2.status_code == 409


def test_create_user_password_too_short_returns_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    payload = {
        "email": "shortpw@example.com",
        "full_name": "Short Pw",
        "role": "researcher",
        "password": "short",
    }
    resp = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert resp.status_code == 422


def test_update_user_fields_and_login_with_new_password(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/users",
        json={
            "email": "editable@example.com",
            "full_name": "Editable User",
            "role": "researcher",
            "password": "original-password",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]

    resp2 = client.patch(
        f"/api/v1/users/{user_id}",
        json={"full_name": "Renamed User", "password": "updated-password"},
        headers=admin_headers,
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["full_name"] == "Renamed User"

    # New password works for login.
    token = login(client, "editable@example.com", "updated-password")
    assert token


def test_update_user_email_conflict(
    client: TestClient, admin_headers: dict[str, str], researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/users",
        json={
            "email": "second@example.com",
            "full_name": "Second User",
            "role": "researcher",
            "password": "second-password",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    second_id = resp.json()["id"]

    resp2 = client.patch(
        f"/api/v1/users/{second_id}",
        json={"email": "researcher@example.com"},
        headers=admin_headers,
    )
    assert resp2.status_code == 409


def test_patch_user_requires_admin(
    client: TestClient, researcher_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/users",
        json={
            "email": "target@example.com",
            "full_name": "Target User",
            "role": "researcher",
            "password": "target-password",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    target_id = resp.json()["id"]

    resp2 = client.patch(
        f"/api/v1/users/{target_id}", json={"full_name": "Hacked"}, headers=researcher_headers
    )
    assert resp2.status_code == 403


def test_patch_unknown_user_404(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000",
        json={"full_name": "Nobody"},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_list_users_returns_all(
    client: TestClient, admin_headers: dict[str, str], researcher_headers: dict[str, str]
) -> None:
    resp = client.get("/api/v1/users", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    users: list[dict[str, Any]] = resp.json()
    roles = {u["role"] for u in users}
    assert "admin" in roles
    assert "researcher" in roles
