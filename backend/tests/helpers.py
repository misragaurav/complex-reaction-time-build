"""Shared test helpers for building trial payloads and driving a session
through the runtime endpoints.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

KEY_MAP_CRT3 = ["KeyZ", "KeyX", "KeyC"]


def make_trial(
    *,
    block: str,
    trial_index: int,
    stimulus_position: int,
    key_pressed: str | None,
    rt_ms: float | None = None,
    outcome: str = "correct",
    foreperiod_ms: int = 1500,
    attempt: int = 1,
    premature_count: int = 0,
    extraneous_keys: int = 0,
    invalid_reason: str | None = None,
    stimulus_onset_client_ms: float | None = None,
    response_client_ms: float | None = None,
    client_uuid: str | None = None,
) -> dict[str, Any]:
    return {
        "client_uuid": client_uuid or str(uuid.uuid4()),
        "attempt": attempt,
        "block": block,
        "trial_index": trial_index,
        "stimulus_position": stimulus_position,
        "foreperiod_ms": foreperiod_ms,
        "key_pressed": key_pressed,
        "outcome": outcome,
        "rt_ms": rt_ms,
        "premature_count": premature_count,
        "extraneous_keys": extraneous_keys,
        "invalid_reason": invalid_reason,
        "stimulus_onset_client_ms": stimulus_onset_client_ms,
        "response_client_ms": response_client_ms,
    }


def correct_trial(
    block: str,
    trial_index: int,
    stimulus_position: int,
    rt_ms: float = 400.0,
    key_map: list[str] | None = None,
) -> dict[str, Any]:
    km = key_map or KEY_MAP_CRT3
    return make_trial(
        block=block,
        trial_index=trial_index,
        stimulus_position=stimulus_position,
        key_pressed=km[stimulus_position],
        rt_ms=rt_ms,
        outcome="correct",
    )


def incorrect_trial(
    block: str,
    trial_index: int,
    stimulus_position: int,
    rt_ms: float = 400.0,
    key_map: list[str] | None = None,
) -> dict[str, Any]:
    km = key_map or KEY_MAP_CRT3
    wrong_position = (stimulus_position + 1) % len(km)
    return make_trial(
        block=block,
        trial_index=trial_index,
        stimulus_position=stimulus_position,
        key_pressed=km[wrong_position],
        rt_ms=rt_ms,
        outcome="incorrect",
    )


def timeout_trial(block: str, trial_index: int, stimulus_position: int) -> dict[str, Any]:
    return make_trial(
        block=block,
        trial_index=trial_index,
        stimulus_position=stimulus_position,
        key_pressed=None,
        outcome="timeout",
    )


def invalid_trial(
    block: str,
    trial_index: int,
    stimulus_position: int,
    invalid_reason: str = "fullscreen_exit",
) -> dict[str, Any]:
    return make_trial(
        block=block,
        trial_index=trial_index,
        stimulus_position=stimulus_position,
        key_pressed=None,
        outcome="invalid",
        invalid_reason=invalid_reason,
    )


def post_trials(
    client: TestClient, headers: dict[str, str], session_id: str, trials: list[dict[str, Any]]
) -> None:
    """Submit `trials` in batches of <=25 (TrialBatchRequest.max_length)."""
    for i in range(0, len(trials), 25):
        batch = trials[i : i + 25]
        resp = client.post(
            f"/api/v1/sessions/{session_id}/trials", json={"trials": batch}, headers=headers
        )
        assert resp.status_code == 200, resp.text


def create_study_participant_session(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    test_trials: int,
    practice_trials: int = 0,
    count: int = 1,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    """Create a study (with the given trial counts), one participant with a
    set password, and `count` sessions for that participant.

    Returns `(study, participant, sessions, participant_headers)`.
    """
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": name,
            "task_type": "CRT3",
            "params": {"practice_trials": practice_trials, "test_trials": test_trials},
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    study: dict[str, Any] = resp.json()

    resp2 = client.post(
        f"/api/v1/studies/{study['id']}/participants", json={"count": 1}, headers=headers
    )
    assert resp2.status_code == 201, resp2.text
    participant: dict[str, Any] = resp2.json()[0]

    resp3 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "fixture-participant-pw"},
    )
    assert resp3.status_code == 200, resp3.text
    participant_headers = {"Authorization": f"Bearer {resp3.json()['access_token']}"}

    resp4 = client.post(
        f"/api/v1/studies/{study['id']}/sessions",
        json={"participant_ids": [participant["id"]], "count": count},
        headers=headers,
    )
    assert resp4.status_code == 201, resp4.text
    sessions: list[dict[str, Any]] = sorted(resp4.json(), key=lambda s: s["order_index"])

    return study, participant, sessions, participant_headers


def run_to_completion(
    client: TestClient,
    headers: dict[str, str],
    session_id: str,
    *,
    practice_trials: int,
    test_trials: int,
    rt_ms: float = 400.0,
    key_map: list[str] | None = None,
) -> None:
    """Start the session, submit all-correct practice + test trials, and complete it."""
    resp = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers)
    assert resp.status_code == 200, resp.text

    km = key_map or KEY_MAP_CRT3
    n = len(km)
    practice = [
        correct_trial("practice", i, (i - 1) % n, rt_ms=rt_ms, key_map=km)
        for i in range(1, practice_trials + 1)
    ]
    test = [
        correct_trial("test", i, (i - 1) % n, rt_ms=rt_ms, key_map=km)
        for i in range(1, test_trials + 1)
    ]
    if practice:
        post_trials(client, headers, session_id, practice)
    post_trials(client, headers, session_id, test)
    resp = client.post(f"/api/v1/sessions/{session_id}/complete", headers=headers)
    assert resp.status_code == 204, resp.text
