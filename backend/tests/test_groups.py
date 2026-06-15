"""MOD-4: participant groups.

Covers MAC-20..27 and the Step-4 requirements: one-group-per-participant
enforcement, 409 on reassignment, and group_name in CSV exports.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

from fastapi.testclient import TestClient

from .helpers import create_sessions_orm, run_to_completion


def _study(client: TestClient, headers: dict[str, str], **body: Any) -> dict[str, Any]:
    payload = {"name": "Group Study", "task_type": "CRT3", **body}
    resp = client.post("/api/v1/studies", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _participants(client: TestClient, headers: dict[str, str], study_id: str, count: int) -> list[dict[str, Any]]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/participants", json={"count": count}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    parts: list[dict[str, Any]] = resp.json()
    return parts


def _group(client: TestClient, headers: dict[str, str], study_id: str, name: str) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/groups", json={"name": name}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


# ---- MAC-20: create + unique name ----------------------------------------


def test_create_group_and_unique_name(client: TestClient, researcher_headers: dict[str, str]) -> None:
    study = _study(client, researcher_headers)
    g = _group(client, researcher_headers, study["id"], "Group A")
    assert g["name"] == "Group A"
    assert g["member_count"] == 0

    # Duplicate name within the same study -> 409.
    resp = client.post(
        f"/api/v1/studies/{study['id']}/groups", json={"name": "Group A"}, headers=researcher_headers
    )
    assert resp.status_code == 409, resp.text

    # Same name in a different study is fine.
    study2 = _study(client, researcher_headers, name="Other Study")
    ok = client.post(
        f"/api/v1/studies/{study2['id']}/groups", json={"name": "Group A"}, headers=researcher_headers
    )
    assert ok.status_code == 201, ok.text


# ---- MAC-21 / MAC-24: one group per participant, reassignment 409 ---------


def test_assign_and_reassignment_conflict(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 2)
    g1 = _group(client, researcher_headers, study["id"], "Group A")
    g2 = _group(client, researcher_headers, study["id"], "Group B")

    # Assign both to g1.
    resp = client.post(
        f"/api/v1/groups/{g1['id']}/assign",
        json={"participant_ids": [parts[0]["id"], parts[1]["id"]]},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["assigned"]) == 2
    assert resp.json()["conflicts"] == []

    # Reassigning a single already-assigned participant to g2 -> 409 with the
    # existing group name in the message.
    resp = client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    assert resp.status_code == 409, resp.text
    assert "Group A" in resp.json()["detail"]


def test_assign_batch_partial_conflict_is_200(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 2)
    g1 = _group(client, researcher_headers, study["id"], "Group A")
    g2 = _group(client, researcher_headers, study["id"], "Group B")

    # parts[0] already in g1.
    client.post(
        f"/api/v1/groups/{g1['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    # Batch to g2: one new (parts[1]) + one conflict (parts[0]) -> 200, split lists.
    resp = client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [parts[0]["id"], parts[1]["id"]]},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [a["participant_id"] for a in body["assigned"]] == [parts[1]["id"]]
    assert [c["participant_id"] for c in body["conflicts"]] == [parts[0]["id"]]


def test_participant_out_reflects_group(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 1)
    g = _group(client, researcher_headers, study["id"], "Group A")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    listed = client.get(f"/api/v1/studies/{study['id']}/participants", headers=researcher_headers).json()
    assert listed[0]["group_name"] == "Group A"
    assert listed[0]["group_id"] == g["id"]


# ---- MAC-22 / MAC-23 / MAC-25: detail, counter, completion ----------------


def test_group_patch_counter_and_detail(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 1)
    g = _group(client, researcher_headers, study["id"], "Group A")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    resp = client.patch(
        f"/api/v1/groups/{g['id']}", json={"current_intervention_session": 5}, headers=researcher_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["current_intervention_session"] == 5

    detail = client.get(f"/api/v1/groups/{g['id']}", headers=researcher_headers).json()
    assert detail["member_count"] == 1
    assert len(detail["members"]) == 1
    assert detail["members"][0]["code"] == parts[0]["code"]
    assert detail["completion"]["total_assigned"] == 1


# ---- MAC-27: delete lifecycle ---------------------------------------------


def test_delete_group_requires_no_members(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 1)
    g = _group(client, researcher_headers, study["id"], "Group A")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    # Has a member -> 409.
    resp = client.delete(f"/api/v1/groups/{g['id']}", headers=researcher_headers)
    assert resp.status_code == 409, resp.text

    # Empty group -> 204.
    empty = _group(client, researcher_headers, study["id"], "Empty")
    resp = client.delete(f"/api/v1/groups/{empty['id']}", headers=researcher_headers)
    assert resp.status_code == 204, resp.text


# ---- MAC-26: group_name in CSV exports ------------------------------------


def test_group_name_in_session_csv_export(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    # Build a completed session for an assigned participant, then check the
    # trailing group_name column in the session trial CSV.
    study, participant, sessions, p_headers = _create_completed(client, researcher_headers)
    g = _group(client, researcher_headers, study["id"], "Group A")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [participant["id"]]},
        headers=researcher_headers,
    )
    resp = client.get(f"/api/v1/sessions/{sessions[0]['id']}/export.csv", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    reader = csv.reader(io.StringIO(resp.text))
    header = next(reader)
    assert header[-1] == "group_name"
    rows = list(reader)
    assert rows and all(r[-1] == "Group A" for r in rows)


def test_group_name_empty_for_unassigned_in_zip(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study, participant, sessions, p_headers = _create_completed(client, researcher_headers)
    # No group assigned.
    resp = client.get(f"/api/v1/studies/{study['id']}/export.zip", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    for fname in ("trials.csv", "sessions_summary.csv", "participants_summary.csv"):
        reader = csv.reader(io.StringIO(zf.read(fname).decode()))
        header = next(reader)
        assert header[-1] == "group_name", fname
        for row in reader:
            assert row[-1] == "", f"{fname}: expected empty group_name for unassigned"


def _create_completed(
    client: TestClient, headers: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    study = _study(client, headers, params={"practice_trials": 0, "test_trials": 3})
    parts = _participants(client, headers, study["id"], 1)
    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": parts[0]["code"], "password": "group-participant-pw"},
    )
    p_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    sessions = create_sessions_orm(client, headers, study, parts[0], count=1)
    # MOD-5: activate before starting; pass researcher headers so run_to_completion activates.
    run_to_completion(
        client, p_headers, sessions[0]["id"], practice_trials=0, test_trials=3,
        researcher_headers=headers,
    )
    return study, parts[0], sessions, p_headers
