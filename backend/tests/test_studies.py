"""Study tests (FR-9..FR-11): defaults, params lock, archive behavior."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.task_defaults import default_params


def test_create_study_with_no_params_uses_defaults_verbatim(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={"name": "Defaults Study", "task_type": "CRT3"},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()

    assert data["params"] == default_params("CRT3")
    assert data["params_locked"] is False
    assert data["counts"] == {
        "participants": 0,
        "sessions_total": 0,
        "sessions_completed": 0,
        "completion_pct": 0.0,
    }


def test_get_unknown_study_404(client: TestClient, researcher_headers: dict[str, str]) -> None:
    resp = client.get(
        "/api/v1/studies/00000000-0000-0000-0000-000000000000", headers=researcher_headers
    )
    assert resp.status_code == 404


def test_update_study_params_when_unlocked(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"params": {"test_trials": 10}},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    assert data["params"]["test_trials"] == 10
    assert data["params"]["task_type"] == "CRT3"
    # Unrelated defaults are preserved.
    assert data["params"]["practice_trials"] == default_params("CRT3")["practice_trials"]


def test_params_locked_after_session_started_returns_409(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    # Not locked before starting.
    assert session["params_locked"] is False if "params_locked" in session else True

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    resp2 = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"params": {"test_trials": 5}},
        headers=researcher_headers,
    )
    assert resp2.status_code == 409

    study_resp = client.get(f"/api/v1/studies/{study['id']}", headers=researcher_headers)
    assert study_resp.status_code == 200, study_resp.text
    assert study_resp.json()["params_locked"] is True


def test_archived_study_rejects_new_sessions(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant: dict[str, Any],
) -> None:
    resp = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"is_archived": True},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_archived"] is True

    resp2 = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol",
        json={"participant_ids": [participant["id"]]},
        headers=researcher_headers,
    )
    assert resp2.status_code == 409


def test_list_studies_archived_filter(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.get("/api/v1/studies", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    ids = [s["id"] for s in resp.json()]
    assert study["id"] in ids

    client.patch(
        f"/api/v1/studies/{study['id']}", json={"is_archived": True}, headers=researcher_headers
    )

    resp2 = client.get("/api/v1/studies", headers=researcher_headers)
    assert study["id"] not in [s["id"] for s in resp2.json()]

    resp3 = client.get("/api/v1/studies?archived=true", headers=researcher_headers)
    assert study["id"] in [s["id"] for s in resp3.json()]


def test_create_study_with_param_overrides(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "CRT2 Study",
            "task_type": "CRT2",
            "params": {"practice_trials": 5, "test_trials": 8},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    assert data["params"]["practice_trials"] == 5
    assert data["params"]["test_trials"] == 8
    assert data["params"]["key_map"] == default_params("CRT2")["key_map"]


def test_create_study_invalid_params_returns_422(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Bad Params Study",
            "task_type": "CRT3",
            "params": {"foreperiod_min_ms": 5000, "foreperiod_max_ms": 1000},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 422


def test_create_study_duplicate_key_map_codes_returns_422(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Duplicate Key Map Study",
            "task_type": "CRT3",
            "params": {"key_map": ["KeyZ", "KeyZ", "KeyC"]},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 422
