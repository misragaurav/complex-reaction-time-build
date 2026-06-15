"""MOD-2: Simple Reaction Time (SRT) task type.

Covers MAC-5..10 and the Step-4 SRT requirements: outcome logic
(correct-only / timeout / invalid), `max_consecutive_repeats` ignored, and
422 on a key_map whose length != 1.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi.testclient import TestClient

from app.task_defaults import default_params, render_instructions

from .helpers import activate_session, create_sessions_orm, make_trial, post_trials

SRT_KEY_MAP = ["Space"]


def _create_srt_study(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "SRT Study",
    test_trials: int = 3,
    practice_trials: int = 0,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name, "task_type": "SRT"}
    merged = {"practice_trials": practice_trials, "test_trials": test_trials}
    if params:
        merged.update(params)
    body["params"] = merged
    resp = client.post("/api/v1/studies", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _make_participant_session(
    client: TestClient, headers: dict[str, str], study_id: str
) -> tuple[dict[str, Any], dict[str, str]]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/participants", json={"count": 1}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    participant = resp.json()[0]

    resp2 = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "srt-participant-pw"},
    )
    assert resp2.status_code == 200, resp2.text
    p_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

    study_resp = client.get(f"/api/v1/studies/{study_id}", headers=headers)
    assert study_resp.status_code == 200, study_resp.text
    study = study_resp.json()

    sessions = create_sessions_orm(client, headers, study, participant, count=1)
    session = sessions[0]
    # MOD-5: activate so the participant can start.
    activate_session(client, headers, session["id"])
    return session, p_headers


def _trial_csv_rows(
    client: TestClient, headers: dict[str, str], session_id: str
) -> list[dict[str, str]]:
    resp = client.get(f"/api/v1/sessions/{session_id}/export.csv", headers=headers)
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


# ---- MAC-5 / MAC-6: schema, defaults, round-trip --------------------------


def test_create_srt_study_defaults_and_roundtrip(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies", json={"name": "SRT defaults", "task_type": "SRT"}, headers=researcher_headers
    )
    assert resp.status_code == 201, resp.text
    study = resp.json()
    assert study["task_type"] == "SRT"
    # MFR-6: default SRT key map is exactly ["Space"].
    assert study["params"]["task_type"] == "SRT"
    assert study["params"]["key_map"] == ["Space"]

    # Round-trips via GET.
    got = client.get(f"/api/v1/studies/{study['id']}", headers=researcher_headers)
    assert got.status_code == 200
    assert got.json()["task_type"] == "SRT"


def test_invalid_task_type_rejected(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies", json={"name": "bad", "task_type": "CRT5"}, headers=researcher_headers
    )
    assert resp.status_code == 422, resp.text


# ---- MAC-8: key_map cardinality (exactly 1 for SRT) -----------------------


def test_srt_keymap_length_must_be_one(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    # length 2 -> 422
    resp = client.post(
        "/api/v1/studies",
        json={"name": "two keys", "task_type": "SRT", "params": {"key_map": ["Space", "KeyZ"]}},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text

    # length 0 -> 422
    resp = client.post(
        "/api/v1/studies",
        json={"name": "no keys", "task_type": "SRT", "params": {"key_map": []}},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text



# ---- MAC-7 / outcome logic: correct-only, timeout, invalid ----------------


def test_srt_outcomes_correct_and_timeout(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_srt_study(client, researcher_headers, test_trials=3, practice_trials=0)
    session, p_headers = _make_participant_session(client, researcher_headers, study["id"])

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=p_headers)
    assert resp.status_code == 200, resp.text
    # The start response advertises the SRT params (1-key map).
    assert resp.json()["task_type"] == "SRT"
    assert resp.json()["params"]["key_map"] == ["Space"]

    trials = [
        make_trial(block="test", trial_index=1, stimulus_position=0, key_pressed="Space", rt_ms=310.0, outcome="correct"),
        make_trial(block="test", trial_index=2, stimulus_position=0, key_pressed=None, outcome="timeout"),
        make_trial(block="test", trial_index=3, stimulus_position=0, key_pressed="Space", rt_ms=298.0, outcome="correct"),
    ]
    post_trials(client, p_headers, session["id"], trials)
    resp = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=p_headers)
    assert resp.status_code == 204, resp.text

    rows = _trial_csv_rows(client, researcher_headers, session["id"])
    assert len(rows) == 3
    # Every SRT trial is at the single position 0; no 'incorrect' ever appears.
    assert all(r["stimulus_position"] == "0" for r in rows)
    assert all(r["outcome"] != "incorrect" for r in rows)
    by_index = {r["trial_index"]: r for r in rows}
    assert by_index["1"]["outcome"] == "correct" and by_index["1"]["response_position"] == "0"
    assert by_index["2"]["outcome"] == "timeout" and by_index["2"]["response_position"] == ""
    assert by_index["3"]["outcome"] == "correct" and by_index["3"]["response_position"] == "0"


def test_srt_invalid_outcome_and_requeue(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_srt_study(client, researcher_headers, test_trials=1, practice_trials=0)
    session, p_headers = _make_participant_session(client, researcher_headers, study["id"])

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=p_headers)
    assert resp.status_code == 200, resp.text

    # One invalid (fullscreen exit) then its requeued replacement (k=1 -> 2 rows).
    trials = [
        make_trial(
            block="test", trial_index=1, stimulus_position=0, key_pressed=None,
            outcome="invalid", invalid_reason="fullscreen_exit",
        ),
        make_trial(block="test", trial_index=2, stimulus_position=0, key_pressed="Space", rt_ms=305.0, outcome="correct"),
    ]
    post_trials(client, p_headers, session["id"], trials)
    resp = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=p_headers)
    assert resp.status_code == 204, resp.text

    rows = _trial_csv_rows(client, researcher_headers, session["id"])
    by_index = {r["trial_index"]: r for r in rows}
    assert by_index["1"]["outcome"] == "invalid" and by_index["1"]["response_position"] == ""
    assert by_index["2"]["outcome"] == "correct" and by_index["2"]["response_position"] == "0"
    assert all(r["stimulus_position"] == "0" for r in rows)


# ---- max_consecutive_repeats ignored for SRT ------------------------------


def test_srt_max_consecutive_repeats_ignored(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    # Even with max_consecutive_repeats=1, an SRT session of many trials (all
    # necessarily at position 0) is accepted and completes -- the constraint is
    # stored but has no effect (MFR-7).
    study = _create_srt_study(
        client, researcher_headers, test_trials=5, practice_trials=0,
        params={"max_consecutive_repeats": 1},
    )
    assert study["params"]["max_consecutive_repeats"] == 1
    session, p_headers = _make_participant_session(client, researcher_headers, study["id"])

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=p_headers)
    assert resp.status_code == 200, resp.text
    trials = [
        make_trial(block="test", trial_index=i, stimulus_position=0, key_pressed="Space", rt_ms=300.0, outcome="correct")
        for i in range(1, 6)
    ]
    post_trials(client, p_headers, session["id"], trials)
    resp = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=p_headers)
    assert resp.status_code == 204, resp.text

    rows = _trial_csv_rows(client, researcher_headers, session["id"])
    assert len(rows) == 5
    assert all(r["stimulus_position"] == "0" and r["outcome"] == "correct" for r in rows)


# ---- MAC-9: SRT statistics share the CRT shape ----------------------------


def test_srt_summary_shape_matches_crt(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_srt_study(client, researcher_headers, test_trials=3, practice_trials=0)
    session, p_headers = _make_participant_session(client, researcher_headers, study["id"])
    client.post(f"/api/v1/sessions/{session['id']}/start", headers=p_headers)
    trials = [
        make_trial(block="test", trial_index=i, stimulus_position=0, key_pressed="Space", rt_ms=300.0 + i, outcome="correct")
        for i in range(1, 4)
    ]
    post_trials(client, p_headers, session["id"], trials)
    client.post(f"/api/v1/sessions/{session['id']}/complete", headers=p_headers)

    resp = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    # Same shape as CRT: raw + trimmed stat blocks, accuracy ~100% (no incorrect).
    assert "raw" in summary and "trimmed" in summary
    assert summary["n_correct"] == 3
    assert summary["accuracy_pct"] == 100.0


# ---- MAC-10: instructions render grammatically for N=1 --------------------


def test_srt_instructions_render_singular() -> None:
    params = default_params("SRT")
    rendered = render_instructions(params["instructions_text"], params)
    assert "Space" in rendered
    # Singular phrasing: "a cross", never the plural "crosses".
    assert "crosses" not in rendered
    # Placeholders fully substituted.
    assert "{KEYS}" not in rendered and "{P}" not in rendered and "{T}" not in rendered
