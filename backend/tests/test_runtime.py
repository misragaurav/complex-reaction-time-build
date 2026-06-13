"""Session runtime tests: start/demographics/trials/complete/client-env.

Covers AC-2 (cross-participant isolation), AC-20 (order lock), AC-23
(completion row-count + FR-45 re-queue arithmetic), AC-24-32/41-43 (trial
outcome recomputation, outlier flagging, client_env), AC-34/35 (idempotent
upserts + resume state), and D-11 (once-per-participant demographics).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Session as SessionModel
from tests.helpers import correct_trial, invalid_trial, make_trial, post_trials, run_to_completion


def _parse_csv_rows(text: str) -> list[dict[str, str]]:
    lines = text.strip("\r\n").split("\r\n")
    header = lines[0].split(",")
    return [dict(zip(header, line.split(","), strict=True)) for line in lines[1:]]


def _second_participant_headers(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> dict[str, str]:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/participants", json={"count": 1}, headers=researcher_headers
    )
    assert resp.status_code == 201, resp.text
    p = resp.json()[0]
    resp2 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": p["code"], "password": "second-participant-pw"},
    )
    assert resp2.status_code == 200, resp2.text
    token: str = resp2.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_start_unowned_session_returns_404(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
) -> None:
    other_headers = _second_participant_headers(client, researcher_headers, study)

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=other_headers)
    assert resp.status_code == 404


def test_start_enforces_session_order_lock(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    participant: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={
            "participant_ids": [participant["id"]],
            "count": 2,
            "overrides": {"params": {"practice_trials": 1, "test_trials": 2}},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    sessions = sorted(resp.json(), key=lambda s: s["order_index"])
    session1, session2 = sessions

    # Session 2 cannot start while session 1 is still "created".
    resp2 = client.post(f"/api/v1/sessions/{session2['id']}/start", headers=participant_headers)
    assert resp2.status_code == 409

    run_to_completion(
        client, participant_headers, session1["id"], practice_trials=1, test_trials=2
    )

    resp3 = client.post(f"/api/v1/sessions/{session2['id']}/start", headers=participant_headers)
    assert resp3.status_code == 200, resp3.text


def test_trial_outcome_recomputation_and_outlier_flag(
    client: TestClient,
    researcher_headers: dict[str, str],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    trials = [
        # Correct response; client sends a bogus "incorrect" outcome that the
        # server must overwrite based on key_map/stimulus_position.
        make_trial(
            block="practice",
            trial_index=1,
            stimulus_position=0,
            key_pressed="KeyZ",
            rt_ms=234.5,
            outcome="incorrect",
        ),
        # Wrong key for the stimulus position -> incorrect, RT still recorded.
        make_trial(
            block="practice",
            trial_index=2,
            stimulus_position=1,
            key_pressed="KeyZ",
            rt_ms=400.0,
            outcome="correct",
        ),
        # No key pressed -> timeout, regardless of client-claimed outcome/RT.
        make_trial(
            block="practice",
            trial_index=3,
            stimulus_position=2,
            key_pressed=None,
            rt_ms=999.0,
            outcome="correct",
        ),
        # Unmapped ("extraneous") key -> incorrect with no response_position.
        make_trial(
            block="practice",
            trial_index=4,
            stimulus_position=0,
            key_pressed="KeyQ",
            rt_ms=500.0,
            outcome="correct",
            extraneous_keys=2,
        ),
        # Correct but below outlier_low_ms (150) -> outlier_flag = true.
        make_trial(
            block="practice",
            trial_index=5,
            stimulus_position=2,
            key_pressed="KeyC",
            rt_ms=120.0,
            outcome="incorrect",
        ),
        # Client-flagged invalid trial (e.g. fullscreen exit) is preserved as-is.
        make_trial(
            block="practice",
            trial_index=6,
            stimulus_position=0,
            key_pressed=None,
            outcome="invalid",
            invalid_reason="fullscreen_exit",
            premature_count=1,
        ),
    ]
    post_trials(client, participant_headers, session["id"], trials)

    resp2 = client.get(f"/api/v1/sessions/{session['id']}/export.csv", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    rows = {int(r["trial_index"]): r for r in _parse_csv_rows(resp2.text)}
    assert len(rows) == 6

    assert rows[1]["outcome"] == "correct"
    assert rows[1]["response_position"] == "0"
    assert rows[1]["rt_ms"] == "234.5"
    assert rows[1]["outlier_flag"] == "False"

    assert rows[2]["outcome"] == "incorrect"
    assert rows[2]["response_position"] == "0"
    assert rows[2]["rt_ms"] == "400.0"
    assert rows[2]["outlier_flag"] == "False"

    assert rows[3]["outcome"] == "timeout"
    assert rows[3]["response_position"] == ""
    assert rows[3]["rt_ms"] == ""
    assert rows[3]["key_pressed"] == ""

    assert rows[4]["outcome"] == "incorrect"
    assert rows[4]["response_position"] == ""
    assert rows[4]["rt_ms"] == "500.0"
    assert rows[4]["extraneous_keys"] == "2"

    assert rows[5]["outcome"] == "correct"
    assert rows[5]["response_position"] == "2"
    assert rows[5]["rt_ms"] == "120.0"
    assert rows[5]["outlier_flag"] == "True"

    assert rows[6]["outcome"] == "invalid"
    assert rows[6]["invalid_reason"] == "fullscreen_exit"
    assert rows[6]["response_position"] == ""
    assert rows[6]["rt_ms"] == ""
    assert rows[6]["premature_count"] == "1"
    assert rows[6]["outlier_flag"] == "False"


def test_idempotent_resubmission_and_resume_state(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    fixed_uuid = str(uuid.uuid4())
    trial = make_trial(
        block="practice",
        trial_index=1,
        stimulus_position=0,
        key_pressed="KeyZ",
        rt_ms=300.0,
        outcome="correct",
        client_uuid=fixed_uuid,
    )
    post_trials(client, participant_headers, session["id"], [trial])

    # Re-submitting the same client_uuid (e.g. retried sendBeacon) updates the
    # existing row in place rather than creating a duplicate.
    trial["rt_ms"] = 350.0
    post_trials(client, participant_headers, session["id"], [trial])

    resp2 = client.get(f"/api/v1/sessions/{session['id']}/export.csv", headers=researcher_headers)
    rows = _parse_csv_rows(resp2.text)
    assert len(rows) == 1
    assert rows[0]["rt_ms"] == "350.0"

    # Simulate a forced refresh: /start again reports resume state and bumps resume_count.
    resp3 = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp3.status_code == 200, resp3.text
    started = resp3.json()
    assert started["stored_trials"] == {"practice": [1], "test": []}

    resp4 = client.get(f"/api/v1/studies/{study['id']}/sessions", headers=researcher_headers)
    found = next(s for s in resp4.json() if s["id"] == session["id"])
    assert found["resume_count"] == 1


def test_conflicting_trial_index_different_uuid_returns_409(
    client: TestClient, session: dict[str, Any], participant_headers: dict[str, str]
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    trial_a = correct_trial("practice", 1, 0)
    resp_a = client.post(
        f"/api/v1/sessions/{session['id']}/trials",
        json={"trials": [trial_a]},
        headers=participant_headers,
    )
    assert resp_a.status_code == 200, resp_a.text

    trial_b = correct_trial("practice", 1, 0)
    resp_b = client.post(
        f"/api/v1/sessions/{session['id']}/trials",
        json={"trials": [trial_b]},
        headers=participant_headers,
    )
    assert resp_b.status_code == 409


def test_complete_missing_rows_then_success_then_double_complete(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    test_trials_param = session["params"]["test_trials"]
    assert test_trials_param == 20

    trials = [correct_trial("test", i, (i - 1) % 3) for i in range(1, test_trials_param)]
    post_trials(client, participant_headers, session["id"], trials)

    resp2 = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=participant_headers)
    assert resp2.status_code == 409
    detail = resp2.json()["detail"]
    assert detail["expected_rows"] == test_trials_param
    assert detail["missing_trial_indices"] == [test_trials_param]

    last = correct_trial("test", test_trials_param, (test_trials_param - 1) % 3)
    post_trials(client, participant_headers, session["id"], [last])

    resp3 = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=participant_headers)
    assert resp3.status_code == 204, resp3.text

    resp4 = client.get(f"/api/v1/studies/{study['id']}/sessions", headers=researcher_headers)
    found = next(s for s in resp4.json() if s["id"] == session["id"])
    assert found["status"] == "completed"
    assert found["completed_at"] is not None

    resp5 = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=participant_headers)
    assert resp5.status_code == 409


def test_complete_with_invalid_trial_requeue_arithmetic(
    client: TestClient, researcher_headers: dict[str, str], participant_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Requeue Study",
            "task_type": "CRT3",
            "params": {"practice_trials": 0, "test_trials": 5},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    requeue_study = resp.json()

    resp2 = client.post(
        f"/api/v1/studies/{requeue_study['id']}/participants", json={"count": 1}, headers=researcher_headers
    )
    assert resp2.status_code == 201, resp2.text
    p = resp2.json()[0]

    resp3 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": p["code"], "password": "requeue-participant-pw"},
    )
    assert resp3.status_code == 200, resp3.text
    requeue_headers = {"Authorization": f"Bearer {resp3.json()['access_token']}"}

    resp4 = client.post(
        f"/api/v1/studies/{requeue_study['id']}/sessions",
        json={"participant_ids": [p["id"]], "count": 1},
        headers=researcher_headers,
    )
    assert resp4.status_code == 201, resp4.text
    requeue_session = resp4.json()[0]

    resp5 = client.post(f"/api/v1/sessions/{requeue_session['id']}/start", headers=requeue_headers)
    assert resp5.status_code == 200, resp5.text

    # 5 configured test trials, one of which (index 2) is invalidated and
    # re-queued as index 6: expected_rows = 5 + min(k=1, 5) = 6.
    trials = [
        correct_trial("test", 1, 0),
        invalid_trial("test", 2, 1),
        correct_trial("test", 3, 2),
        correct_trial("test", 4, 0),
        correct_trial("test", 5, 1),
        correct_trial("test", 6, 2),
    ]
    post_trials(client, requeue_headers, requeue_session["id"], trials)

    resp6 = client.post(f"/api/v1/sessions/{requeue_session['id']}/complete", headers=requeue_headers)
    assert resp6.status_code == 204, resp6.text


def test_client_env_persists(
    client: TestClient, session: dict[str, Any], participant_headers: dict[str, str]
) -> None:
    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    payload = {
        "user_agent": "Mozilla/5.0 (Test Runner)",
        "screen_width": 1920,
        "screen_height": 1080,
        "device_pixel_ratio": 2.0,
        "refresh_rate_hz": 60.0,
        "timezone": "UTC",
    }
    resp2 = client.post(
        f"/api/v1/sessions/{session['id']}/client-env", json=payload, headers=participant_headers
    )
    assert resp2.status_code == 204, resp2.text

    db = SessionLocal()
    try:
        db_session = db.get(SessionModel, uuid.UUID(session["id"]))
        assert db_session is not None
        assert db_session.client_env == payload
    finally:
        db.close()


def test_runtime_endpoints_require_in_progress_session(
    client: TestClient, session: dict[str, Any], participant_headers: dict[str, str]
) -> None:
    trial = correct_trial("practice", 1, 0)
    resp = client.post(
        f"/api/v1/sessions/{session['id']}/trials",
        json={"trials": [trial]},
        headers=participant_headers,
    )
    assert resp.status_code == 409

    resp2 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={"answers": []},
        headers=participant_headers,
    )
    assert resp2.status_code == 409

    resp3 = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=participant_headers)
    assert resp3.status_code == 409

    payload = {
        "user_agent": "Mozilla/5.0",
        "screen_width": 1280,
        "screen_height": 720,
        "device_pixel_ratio": 1.0,
        "refresh_rate_hz": 60.0,
        "timezone": "UTC",
    }
    resp4 = client.post(
        f"/api/v1/sessions/{session['id']}/client-env", json=payload, headers=participant_headers
    )
    assert resp4.status_code == 409


def test_demographics_due_once_field_only_for_first_session(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Demographics Once Study",
            "task_type": "CRT3",
            "params": {"practice_trials": 0, "test_trials": 1},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    demo_study = resp.json()

    resp2 = client.post(
        f"/api/v1/studies/{demo_study['id']}/demographic-fields",
        json={"label": "Age", "field_type": "number", "required": False, "frequency": "once"},
        headers=researcher_headers,
    )
    assert resp2.status_code == 201, resp2.text
    field = resp2.json()

    resp3 = client.post(
        f"/api/v1/studies/{demo_study['id']}/participants", json={"count": 1}, headers=researcher_headers
    )
    p = resp3.json()[0]
    resp4 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": p["code"], "password": "demo-once-pw"},
    )
    headers = {"Authorization": f"Bearer {resp4.json()['access_token']}"}

    resp5 = client.post(
        f"/api/v1/studies/{demo_study['id']}/sessions",
        json={"participant_ids": [p["id"]], "count": 2},
        headers=researcher_headers,
    )
    assert resp5.status_code == 201, resp5.text
    sessions = sorted(resp5.json(), key=lambda s: s["order_index"])
    session1, session2 = sessions

    resp6 = client.post(f"/api/v1/sessions/{session1['id']}/start", headers=headers)
    assert resp6.status_code == 200, resp6.text
    assert [f["id"] for f in resp6.json()["demographics_due"]] == [field["id"]]

    resp7 = client.post(
        f"/api/v1/sessions/{session1['id']}/demographics",
        json={"answers": [{"field_id": field["id"], "value": "30"}]},
        headers=headers,
    )
    assert resp7.status_code == 204, resp7.text

    run_to_completion(client, headers, session1["id"], practice_trials=0, test_trials=1)

    resp8 = client.post(f"/api/v1/sessions/{session2['id']}/start", headers=headers)
    assert resp8.status_code == 200, resp8.text
    assert resp8.json()["demographics_due"] == []
