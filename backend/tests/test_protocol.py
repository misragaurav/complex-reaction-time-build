"""MOD-3: session labelling and longitudinal protocol structure.

Covers MAC-11..19 and the Step-4 requirements: display_label computation
across all sessions_per_week values, the multiple-of rule, protocol-generation
idempotency, and display_label_overridden persistence.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.protocol import compute_display_label, compute_week_day


def _create_study(
    client: TestClient, headers: dict[str, str], **body: Any
) -> dict[str, Any]:
    payload = {"name": "Protocol Study", "task_type": "CRT4", **body}
    resp = client.post("/api/v1/studies", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _add_participants(
    client: TestClient, headers: dict[str, str], study_id: str, count: int
) -> list[dict[str, Any]]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/participants", json={"count": count}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    parts: list[dict[str, Any]] = resp.json()
    return parts


def _sessions_by_order(
    client: TestClient, headers: dict[str, str], study_id: str
) -> dict[int, dict[str, Any]]:
    resp = client.get(f"/api/v1/studies/{study_id}/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    return {s["order_index"]: s for s in resp.json()}


# ---- MAC-15: week/day computation (pure) ----------------------------------


def test_compute_week_day_matches_formula_all_sessions_per_week() -> None:
    for spw in range(1, 8):
        for k in range(1, 40):
            week, day = compute_week_day(k, spw)
            assert week == math.ceil(k / spw)
            assert day == ((k - 1) % spw) + 1
            assert 1 <= day <= spw


def test_compute_week_day_table_for_spw_3() -> None:
    expected = {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (2, 1), 5: (2, 2), 6: (2, 3), 24: (8, 3)}
    for k, (week, day) in expected.items():
        assert compute_week_day(k, 3) == (week, day)


def test_compute_display_label_rules() -> None:
    assert compute_display_label("onboarding", None, None) == "Onboarding"
    assert compute_display_label("pre", 2, 2) == "Week 2 · Day 2 · Pre"
    assert compute_display_label("post", 8, 3) == "Week 8 · Day 3 · Post"


# ---- MAC-11: defaults + round-trip ----------------------------------------


def test_protocol_config_defaults_and_roundtrip(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers)
    assert study["num_intervention_sessions"] == 24
    assert study["sessions_per_week"] == 3
    assert study["task_type_onboarding"] == "CRT4"
    assert study["task_type_pre"] == "CRT4"
    assert study["task_type_post"] == "CRT4"
    assert study["protocol_locked"] is False

    # Update + GET round-trip.
    resp = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"sessions_per_week": 2, "num_intervention_sessions": 24, "task_type_pre": "SRT"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    got = client.get(f"/api/v1/studies/{study['id']}", headers=researcher_headers).json()
    assert got["sessions_per_week"] == 2
    assert got["task_type_pre"] == "SRT"


# ---- MAC-12: multiple-of rule + post-generation lock ----------------------


def test_multiple_of_rule_on_create(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={"name": "bad", "task_type": "CRT4", "num_intervention_sessions": 25, "sessions_per_week": 3},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "multiple" in resp.json()["detail"].lower()


def test_multiple_of_rule_on_update(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers)  # 24 / 3
    resp = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"sessions_per_week": 5},  # 24 % 5 != 0
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text


def test_protocol_locked_after_generation(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=6, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    resp = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers
    )
    assert resp.status_code == 201, resp.text

    # Now locked: changing a protocol field -> 422.
    locked = client.get(f"/api/v1/studies/{study['id']}", headers=researcher_headers).json()
    assert locked["protocol_locked"] is True
    resp = client.patch(
        f"/api/v1/studies/{study['id']}",
        json={"num_intervention_sessions": 9},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "locked" in resp.json()["detail"].lower()

    # A non-protocol field (name) still updates fine while locked.
    resp = client.patch(
        f"/api/v1/studies/{study['id']}", json={"name": "Renamed"}, headers=researcher_headers
    )
    assert resp.status_code == 200, resp.text


# ---- MAC-13 / MAC-17: protocol shape & order_index ------------------------


def test_generate_protocol_shape_and_order_index(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=24, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    resp = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert len(body["created"]) == 1
    assert body["created"][0]["session_count"] == 49  # 1 + 2*24

    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    assert len(sessions) == 49
    # Onboarding at order_index 1.
    assert sessions[1]["session_type"] == "onboarding"
    assert sessions[1]["display_label"] == "Onboarding"
    assert sessions[1]["intervention_session_number"] is None
    # pre(k) at 2k, post(k) at 2k+1.
    for k in range(1, 25):
        pre = sessions[2 * k]
        post = sessions[2 * k + 1]
        assert pre["session_type"] == "pre" and pre["intervention_session_number"] == k
        assert post["session_type"] == "post" and post["intervention_session_number"] == k


# ---- MAC-16: display_label values + override ------------------------------


def test_generated_display_labels(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=24, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    client.post(f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers)
    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    # Smoke table (D15): order_index 1/4/5/24.
    assert sessions[1]["display_label"] == "Onboarding"
    assert sessions[4]["display_label"] == "Week 1 · Day 2 · Pre"
    assert sessions[5]["display_label"] == "Week 1 · Day 2 · Post"
    assert sessions[24]["display_label"] == "Week 4 · Day 3 · Pre"
    # order_index 2 (k=1) -> Week 1 · Day 1 · Pre (used by smoke activation).
    assert sessions[2]["display_label"] == "Week 1 · Day 1 · Pre"


def test_display_label_override_persists(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=6, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    client.post(f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers)
    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    target = sessions[2]
    assert target["display_label_overridden"] is False

    resp = client.patch(
        f"/api/v1/sessions/{target['id']}",
        json={"display_label": "Custom label"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["display_label"] == "Custom label"
    assert resp.json()["display_label_overridden"] is True

    # Persists across reads.
    again = _sessions_by_order(client, researcher_headers, study["id"])
    assert again[2]["display_label"] == "Custom label"
    assert again[2]["display_label_overridden"] is True


def test_session_label_fields_immutable_via_patch(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=6, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    client.post(f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers)
    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    target = sessions[2]
    # session_type / intervention_session_number are not accepted by PATCH.
    resp = client.patch(
        f"/api/v1/sessions/{target['id']}",
        json={"session_type": "post"},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text


# ---- MAC-18: idempotency + week_start --------------------------------------


def test_generate_protocol_idempotent(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=6, sessions_per_week=3)
    parts = _add_participants(client, researcher_headers, study["id"], 2)

    first = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers
    )
    assert first.status_code == 201, first.text
    assert len(first.json()["created"]) == 2
    assert first.json()["created"][0]["session_count"] == 13  # 1 + 2*6

    # Second call: both participants skipped, no new sessions.
    second = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers
    )
    assert second.status_code == 201, second.text
    assert second.json()["created"] == []
    assert {item["participant_id"] for item in second.json()["skipped"]} == {p["id"] for p in parts}

    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    # 13 per participant, but order_index keys collide across participants in the
    # dict; assert the raw count instead.
    resp = client.get(f"/api/v1/studies/{study['id']}/sessions", headers=researcher_headers)
    assert len(resp.json()) == 26  # 13 * 2


def test_generate_protocol_week_start_offset(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=6, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    resp = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol",
        json={"week_start": 2},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    # k=1 pre at order_index 2 -> week_start(2)-1+ceil(1/3) = 2 -> "Week 2 · Day 1 · Pre".
    assert sessions[2]["week_number"] == 2
    assert sessions[2]["display_label"] == "Week 2 · Day 1 · Pre"


def test_generate_protocol_task_type_overrides(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    # Study is CRT4; generate with SRT pre/post and CRT2 onboarding.
    study = _create_study(client, researcher_headers, num_intervention_sessions=3, sessions_per_week=3)
    _add_participants(client, researcher_headers, study["id"], 1)
    resp = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol",
        json={"task_type_onboarding": "CRT2", "task_type_pre": "SRT", "task_type_post": "SRT"},
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    sessions = _sessions_by_order(client, researcher_headers, study["id"])
    assert sessions[1]["task_type"] == "CRT2"  # onboarding
    assert sessions[2]["task_type"] == "SRT"  # pre(1)
    assert sessions[2]["params"]["key_map"] == ["Space"]  # SRT key_map snapshot
    assert sessions[3]["task_type"] == "SRT"  # post(1)


# ---- MAC-19: participant-facing labelling ---------------------------------


def test_my_sessions_include_label_and_type(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _create_study(client, researcher_headers, num_intervention_sessions=3, sessions_per_week=3)
    parts = _add_participants(client, researcher_headers, study["id"], 1)
    client.post(f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=researcher_headers)

    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": parts[0]["code"], "password": "label-participant-pw"},
    )
    assert resp.status_code == 200, resp.text
    p_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    mine = client.get("/api/v1/me/sessions", headers=p_headers)
    assert mine.status_code == 200, mine.text
    rows = mine.json()
    assert rows[0]["session_type"] == "onboarding"
    assert rows[0]["display_label"] == "Onboarding"
    assert rows[1]["session_type"] == "pre"
    assert rows[1]["display_label"] == "Week 1 · Day 1 · Pre"
