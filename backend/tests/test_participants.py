"""Participant tests (FR-16..FR-17, AC-16..AC-17)."""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

CODE_RE = re.compile(r"^[A-Z0-9_-]+$")


def test_bulk_create_100_participants_unique_codes(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 100},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    participants: list[dict[str, Any]] = resp.json()
    assert len(participants) == 100

    codes = [p["code"] for p in participants]
    assert len(set(codes)) == 100
    for code in codes:
        assert CODE_RE.fullmatch(code), code
    for p in participants:
        assert p["password_set"] is False
        assert p["is_active"] is True
        assert p["sessions_assigned"] == 0
        assert p["sessions_completed"] == 0


def test_bulk_create_with_prefix(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 3, "prefix": "lab"},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    for p in resp.json():
        assert p["code"].startswith("LAB-")


def test_manual_codes_creation_and_duplicate_conflict(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"codes": ["p001", "p002"]},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    codes = [p["code"] for p in resp.json()]
    assert codes == ["P001", "P002"]

    resp2 = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"codes": ["P001"]},
        headers=researcher_headers,
    )
    assert resp2.status_code == 409


def test_manual_codes_invalid_format_returns_422(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"codes": ["bad code with spaces"]},
        headers=researcher_headers,
    )
    assert resp.status_code == 422


def test_manual_codes_duplicate_within_request_returns_422(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"codes": ["DUP", "dup"]},
        headers=researcher_headers,
    )
    assert resp.status_code == 422


def test_create_participants_requires_count_or_codes(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={},
        headers=researcher_headers,
    )
    assert resp.status_code == 422

    resp2 = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"count": 1, "codes": ["X"]},
        headers=researcher_headers,
    )
    assert resp2.status_code == 422


def test_participants_csv_export(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants",
        json={"codes": ["ALPHA", "BETA"]},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text

    resp2 = client.get(
        f"/api/v1/studies/{study['id']}/participants.csv", headers=researcher_headers
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.headers["content-type"].startswith("text/csv")
    lines = resp2.text.strip("\r\n").split("\r\n")
    assert lines[0] == "code"
    assert set(lines[1:]) == {"ALPHA", "BETA"}


def test_deactivated_participant_login_401_but_still_listed(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant: dict[str, Any],
    participant_token: str,
) -> None:
    resp = client.patch(
        f"/api/v1/participants/{participant['id']}",
        json={"is_active": False},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    resp2 = client.post(
        "/api/v1/auth/participant/login",
        json={"code": participant["code"], "password": "participant-password"},
    )
    assert resp2.status_code == 401

    # Still appears in researcher-facing listings/exports.
    resp3 = client.get(
        f"/api/v1/studies/{study['id']}/participants", headers=researcher_headers
    )
    assert resp3.status_code == 200, resp3.text
    assert any(p["id"] == participant["id"] for p in resp3.json())

    resp4 = client.get(
        f"/api/v1/studies/{study['id']}/participants.csv", headers=researcher_headers
    )
    assert participant["code"] in resp4.text


def test_update_participant_unknown_404(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.patch(
        "/api/v1/participants/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers=researcher_headers,
    )
    assert resp.status_code == 404


def test_update_participant_requires_a_field(
    client: TestClient, researcher_headers: dict[str, str], participant: dict[str, Any]
) -> None:
    resp = client.patch(
        f"/api/v1/participants/{participant['id']}", json={}, headers=researcher_headers
    )
    assert resp.status_code == 422
