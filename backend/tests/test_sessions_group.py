"""MOD-11 regression tests: reassignment reflection in sessions list (MAC-141–145).

Verifies that after reassigning a participant (with no started sessions) the
sessions listing carries the new group_id / group_name immediately, and that
unassigned participants produce null values.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import create_sessions_orm


def _make_study(client: TestClient, headers: dict[str, str], name: str = "S") -> dict[str, Any]:
    resp = client.post(
        "/api/v1/studies",
        json={"name": name, "task_type": "CRT3"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _make_participant(
    client: TestClient, headers: dict[str, str], study_id: str
) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/participants",
        json={"count": 1},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data: list[dict[str, Any]] = resp.json()
    return data[0]


def _make_group(
    client: TestClient, headers: dict[str, str], study_id: str, name: str
) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/studies/{study_id}/groups",
        json={"name": name},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _list_sessions(
    client: TestClient, headers: dict[str, str], study_id: str
) -> list[dict[str, Any]]:
    resp = client.get(f"/api/v1/studies/{study_id}/sessions", headers=headers)
    assert resp.status_code == 200, resp.text
    data: list[dict[str, Any]] = resp.json()
    return data


# ---------------------------------------------------------------------------
# MAC-141: group_name / group_id are null when participant is unassigned
# ---------------------------------------------------------------------------

def test_sessions_carry_null_group_when_participant_unassigned(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _make_study(client, researcher_headers)
    participant = _make_participant(client, researcher_headers, study["id"])
    create_sessions_orm(client, researcher_headers, study, participant, count=1)

    sessions = _list_sessions(client, researcher_headers, study["id"])
    assert len(sessions) == 1
    assert sessions[0]["group_id"] is None
    assert sessions[0]["group_name"] is None


# ---------------------------------------------------------------------------
# MAC-142: group_name / group_id reflect initial assignment
# ---------------------------------------------------------------------------

def test_sessions_carry_group_info_after_assignment(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _make_study(client, researcher_headers)
    participant = _make_participant(client, researcher_headers, study["id"])
    group = _make_group(client, researcher_headers, study["id"], "Alpha")
    create_sessions_orm(client, researcher_headers, study, participant, count=2)

    client.post(
        f"/api/v1/groups/{group['id']}/assign",
        json={"participant_ids": [participant["id"]]},
        headers=researcher_headers,
    )

    sessions = _list_sessions(client, researcher_headers, study["id"])
    assert len(sessions) == 2
    for s in sessions:
        assert s["group_id"] == group["id"], f"Expected group_id={group['id']} got {s['group_id']}"
        assert s["group_name"] == "Alpha", f"Expected group_name='Alpha' got {s['group_name']}"


# ---------------------------------------------------------------------------
# MAC-143 / regression: after reassign with no started sessions the sessions
# listing carries the new group immediately (old bug: groupMap was stale)
# ---------------------------------------------------------------------------

def test_sessions_reflect_new_group_after_reassignment_no_started_sessions(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """Reassigning a participant with no started sessions: sessions must immediately
    carry the destination group's id and name in the next listing call."""
    study = _make_study(client, researcher_headers)
    participant = _make_participant(client, researcher_headers, study["id"])
    g1 = _make_group(client, researcher_headers, study["id"], "Alpha")
    g2 = _make_group(client, researcher_headers, study["id"], "Beta")

    # Assign to Alpha first.
    r1 = client.post(
        f"/api/v1/groups/{g1['id']}/assign",
        json={"participant_ids": [participant["id"]]},
        headers=researcher_headers,
    )
    assert r1.status_code == 200, r1.text

    create_sessions_orm(client, researcher_headers, study, participant, count=3)

    # Verify sessions show Alpha before reassignment.
    before = _list_sessions(client, researcher_headers, study["id"])
    assert all(s["group_name"] == "Alpha" for s in before)

    # Reassign to Beta — no sessions have been started.
    r2 = client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [participant["id"]]},
        headers=researcher_headers,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    # v2 Change 2: participant ends up in 'reassigned', not 'conflicts'.
    reassigned_ids = [item["participant_id"] for item in body["reassigned"]]
    assert participant["id"] in reassigned_ids, (
        f"Expected participant in reassigned list; got: {body}"
    )

    # Sessions listing must now carry Beta — this is the regression being tested.
    after = _list_sessions(client, researcher_headers, study["id"])
    assert len(after) == 3
    for s in after:
        assert s["group_id"] == g2["id"], (
            f"Expected group_id={g2['id']!r} after reassign; got {s['group_id']!r}. "
            "Bug: sessions still carry old group (stale join)."
        )
        assert s["group_name"] == "Beta", (
            f"Expected group_name='Beta' after reassign; got {s['group_name']!r}. "
            "Bug: sessions still carry old group (stale join)."
        )


# ---------------------------------------------------------------------------
# MAC-144: multiple participants, each in a different group
# ---------------------------------------------------------------------------

def test_sessions_carry_correct_group_per_participant(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study = _make_study(client, researcher_headers)
    p1 = _make_participant(client, researcher_headers, study["id"])
    p2 = _make_participant(client, researcher_headers, study["id"])
    g1 = _make_group(client, researcher_headers, study["id"], "Alpha")
    g2 = _make_group(client, researcher_headers, study["id"], "Beta")

    client.post(
        f"/api/v1/groups/{g1['id']}/assign",
        json={"participant_ids": [p1["id"]]},
        headers=researcher_headers,
    )
    client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [p2["id"]]},
        headers=researcher_headers,
    )

    create_sessions_orm(client, researcher_headers, study, p1, count=1)
    create_sessions_orm(client, researcher_headers, study, p2, count=1)

    sessions = _list_sessions(client, researcher_headers, study["id"])
    assert len(sessions) == 2

    by_participant = {s["participant_id"]: s for s in sessions}
    assert by_participant[p1["id"]]["group_name"] == "Alpha"
    assert by_participant[p1["id"]]["group_id"] == g1["id"]
    assert by_participant[p2["id"]]["group_name"] == "Beta"
    assert by_participant[p2["id"]]["group_id"] == g2["id"]
