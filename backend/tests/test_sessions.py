"""Session management tests (FR-18..FR-23, AC-18..AC-23)."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Session as SessionModel
from app.task_defaults import default_params
from tests.helpers import post_trials, correct_trial


def _create_participants(
    client: TestClient, headers: dict[str, str], study_id: str, count: int
) -> list[dict[str, Any]]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/participants", json={"count": count}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    data: list[dict[str, Any]] = resp.json()
    return data


def test_create_sessions_for_multiple_participants_snapshot_and_overrides(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    participants = _create_participants(client, researcher_headers, study["id"], 3)

    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": [p["id"] for p in participants], "count": 2},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    sessions: list[dict[str, Any]] = resp.json()
    assert len(sessions) == 6

    by_participant: dict[str, list[dict[str, Any]]] = {}
    for s in sessions:
        by_participant.setdefault(s["participant_id"], []).append(s)
        assert s["params"] == default_params("CRT3")
        assert s["status"] == "created"
        assert s["attempt"] == 1
        assert s["resume_count"] == 0
        assert s["stats"] == {
            "trimmed_mean_rt_ms": None,
            "accuracy_pct": None,
            "n_outliers_flagged": 0,
        }

    for p in participants:
        order_indexes = sorted(s["order_index"] for s in by_participant[p["id"]])
        assert order_indexes == [1, 2]

    # A further session with overrides is appended (order_index 3) and its
    # params are the merged snapshot, not a live reference to the study.
    resp2 = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={
            "participant_ids": [participants[0]["id"]],
            "count": 1,
            "overrides": {"params": {"test_trials": 5}},
        },
        headers=researcher_headers,
    )
    assert resp2.status_code == 201, resp2.text
    overridden = resp2.json()[0]
    assert overridden["order_index"] == 3
    assert overridden["params"]["test_trials"] == 5
    assert overridden["params"]["practice_trials"] == default_params("CRT3")["practice_trials"]

    # Editing the study afterwards does not change existing session snapshots.
    resp3 = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"params": {"test_trials": 99}},
        headers=researcher_headers,
    )
    assert resp3.status_code == 200, resp3.text

    resp4 = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"participant_id": participants[0]["id"]},
    )
    assert resp4.status_code == 200, resp4.text
    refetched = {s["order_index"]: s for s in resp4.json()}
    assert refetched[1]["params"]["test_trials"] == default_params("CRT3")["test_trials"]
    assert refetched[3]["params"]["test_trials"] == 5


def test_create_sessions_unknown_participant_returns_404(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": ["00000000-0000-0000-0000-000000000000"], "count": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 404


def test_list_sessions_filter_sort_and_invalid_params(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    participants = _create_participants(client, researcher_headers, study["id"], 1)
    pid = participants[0]["id"]

    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": [pid], "count": 2},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    sessions = resp.json()
    session1, session2 = sorted(sessions, key=lambda s: s["order_index"])

    # Cancel session 2 (status == "created" -> allowed).
    resp_cancel = client.patch(
        f"/api/v1/sessions/{session2['id']}", json={"action": "cancel"}, headers=researcher_headers
    )
    assert resp_cancel.status_code == 200, resp_cancel.text
    assert resp_cancel.json()["status"] == "cancelled"

    # Cancelled sessions are excluded from the listing entirely.
    resp_list = client.get(
        f"/api/v1/studies/{study['id']}/sessions", headers=researcher_headers
    )
    assert resp_list.status_code == 200, resp_list.text
    ids = [s["id"] for s in resp_list.json()]
    assert session1["id"] in ids
    assert session2["id"] not in ids

    # Filter by participant + status.
    resp_filtered = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"participant_id": pid, "status": "created"},
    )
    assert resp_filtered.status_code == 200, resp_filtered.text
    assert [s["id"] for s in resp_filtered.json()] == [session1["id"]]

    # Invalid status filter -> 422.
    resp_bad_status = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"status": "bogus"},
    )
    assert resp_bad_status.status_code == 422

    # Invalid sort field -> 422.
    resp_bad_sort = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"sort": "bogus"},
    )
    assert resp_bad_sort.status_code == 422


def test_lazy_abandonment_after_31_minutes(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    db = SessionLocal()
    try:
        db_session = db.get(SessionModel, uuid.UUID(session["id"]))
        assert db_session is not None
        db_session.last_activity_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=31
        )
        db.commit()
    finally:
        db.close()

    resp2 = client.get(f"/api/v1/studies/{study['id']}/sessions", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    found = next(s for s in resp2.json() if s["id"] == session["id"])
    assert found["status"] == "abandoned"


def test_reset_session_increments_attempt_and_preserves_old_trials(
    client: TestClient,
    researcher_headers: dict[str, str],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    post_trials(
        client,
        participant_headers,
        session["id"],
        [correct_trial("practice", 1, 0)],
    )

    resp2 = client.patch(
        f"/api/v1/sessions/{session['id']}", json={"action": "reset"}, headers=researcher_headers
    )
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()
    assert data["status"] == "created"
    assert data["attempt"] == 2
    assert data["started_at"] is None
    assert data["resume_count"] == 0

    # The attempt-1 trial is still queryable via export, tagged attempt=1.
    resp3 = client.get(
        f"/api/v1/sessions/{session['id']}/export.csv", headers=researcher_headers
    )
    assert resp3.status_code == 200, resp3.text
    lines = resp3.text.strip("\r\n").split("\r\n")
    header = lines[0].split(",")
    rows = [dict(zip(header, line.split(","), strict=True)) for line in lines[1:]]
    assert len(rows) == 1
    assert rows[0]["attempt"] == "1"

    # DELETE is rejected while trial rows exist for any attempt.
    resp4 = client.delete(f"/api/v1/sessions/{session['id']}", headers=researcher_headers)
    assert resp4.status_code == 409


def test_delete_session_without_trials_succeeds(
    client: TestClient, researcher_headers: dict[str, str], session: dict[str, Any]
) -> None:
    resp = client.delete(f"/api/v1/sessions/{session['id']}", headers=researcher_headers)
    assert resp.status_code == 204

    resp2 = client.get(
        f"/api/v1/studies/{session['study_id']}/sessions", headers=researcher_headers
    )
    assert session["id"] not in [s["id"] for s in resp2.json()]


def test_delete_unknown_session_404(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.delete(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000", headers=researcher_headers
    )
    assert resp.status_code == 404


def test_cancel_only_allowed_when_created_and_reset_not_allowed_when_created(
    client: TestClient,
    researcher_headers: dict[str, str],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    # A freshly-created session cannot be reset (only completed/abandoned/in_progress).
    resp = client.patch(
        f"/api/v1/sessions/{session['id']}", json={"action": "reset"}, headers=researcher_headers
    )
    assert resp.status_code == 409

    resp2 = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp2.status_code == 200, resp2.text

    # Now in_progress: cancel is no longer allowed.
    resp3 = client.patch(
        f"/api/v1/sessions/{session['id']}", json={"action": "cancel"}, headers=researcher_headers
    )
    assert resp3.status_code == 409

    # ...but reset is.
    resp4 = client.patch(
        f"/api/v1/sessions/{session['id']}", json={"action": "reset"}, headers=researcher_headers
    )
    assert resp4.status_code == 200, resp4.text
    assert resp4.json()["status"] == "created"


def test_my_sessions_lock_state(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": [participant["id"]], "count": 2},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text

    resp2 = client.get("/api/v1/me/sessions", headers=participant_headers)
    assert resp2.status_code == 200, resp2.text
    sessions = sorted(resp2.json(), key=lambda s: s["order_index"])
    assert sessions[0]["order_index"] == 1
    assert sessions[0]["locked"] is False
    assert sessions[1]["order_index"] == 2
    assert sessions[1]["locked"] is True
