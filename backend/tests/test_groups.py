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


# ---- MAC-21 / v2-Change-2: one group per participant, reassign-when-not-started ----


def test_assign_and_reassignment_when_no_sessions_started(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """v2 Change 2: reassigning a participant with no started sessions succeeds
    (previously returned 409; now returns 200 with participant in 'reassigned')."""
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

    # Reassigning to g2 with no sessions started → success, participant in 'reassigned'.
    resp = client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    reassigned_ids = [r["participant_id"] for r in body["reassigned"]]
    assert parts[0]["id"] in reassigned_ids
    assert body["conflicts"] == []


def test_assign_batch_partial_reassignment_is_200(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """v2 Change 2: batch assign where one participant has no started sessions
    is reassigned (not returned as a conflict)."""
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 2)
    g1 = _group(client, researcher_headers, study["id"], "Group A")
    g2 = _group(client, researcher_headers, study["id"], "Group B")

    # parts[0] already in g1, no sessions started.
    client.post(
        f"/api/v1/groups/{g1['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    # Batch to g2: parts[1] new, parts[0] reassigned → both succeed.
    resp = client.post(
        f"/api/v1/groups/{g2['id']}/assign",
        json={"participant_ids": [parts[0]["id"], parts[1]["id"]]},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [a["participant_id"] for a in body["assigned"]] == [parts[1]["id"]]
    reassigned_ids = [r["participant_id"] for r in body["reassigned"]]
    assert parts[0]["id"] in reassigned_ids
    assert body["conflicts"] == []


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


def _setup_group_with_protocol(
    client: TestClient,
    headers: dict[str, str],
    num_members: int = 1,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Create a study with a 3-session protocol, assign members to a group."""
    study = _study(
        client, headers,
        num_intervention_sessions=3,
        sessions_per_week=3,
    )
    parts = _participants(client, headers, study["id"], num_members)
    g = _group(client, headers, study["id"], "Group A")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [p["id"] for p in parts]},
        headers=headers,
    )
    resp = client.post(
        f"/api/v1/studies/{study['id']}/generate-protocol", json={}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return study, parts, g


# ---- MAC-109..115: MOD-8 onboarding-aware activation ----------------------


def test_activate_group_onboarding(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-109: activating onboarding ignores the IS counter."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=2)
    # No IS set on the group — should still work for onboarding.
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    assert body["session_type"] == "onboarding"
    assert len(body["activated"]) == 2
    for item in body["activated"]:
        assert item["session_type"] == "onboarding"


def test_deactivate_group_onboarding(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-110: deactivating onboarding expires those activated sessions."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=2)
    client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    resp = client.post(
        f"/api/v1/groups/{g['id']}/deactivate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    assert len(body["expired"]) == 2
    assert body["in_progress_count"] == 0


def test_activate_onboarding_blocked_by_open_pre(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-113: global guard — activated pre session blocks onboarding activation."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    activate_resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert activate_resp.status_code == 200, activate_resp.text
    assert len(activate_resp.json()["activated"]) >= 1

    # Now activating onboarding must fail — the pre session is still activated.
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    assert resp.status_code == 409, resp.text
    detail: Any = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert "blocking" in detail
    assert len(detail["blocking"]) >= 1


def test_activate_pre_requires_is(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-112/MFR-216: activating pre without intervention_session_number returns 422."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre"},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text
    # Error must mention intervention_session_number (from model_validator).
    assert "intervention_session_number" in str(resp.json()["detail"])


def test_deactivate_force_leaves_in_progress(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-114: force deactivate expires activated sessions; in_progress run is untouched."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=2)
    # Give participant[0] a password so they can start a session.
    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": parts[0]["code"], "password": "mod8-force-pw"},
    )
    assert resp.status_code == 200, resp.text
    p_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # Group-activate pre IS=1 for all members.
    activate_resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert activate_resp.status_code == 200, activate_resp.text
    assert len(activate_resp.json()["activated"]) == 2

    # Find and start the pre IS=1 session for participant[0] → in_progress.
    all_sessions: list[dict[str, Any]] = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"participant_id": parts[0]["id"]},
    ).json()
    pre_s = next(
        s for s in all_sessions
        if s["session_type"] == "pre" and s["intervention_session_number"] == 1
    )
    start_resp = client.post(f"/api/v1/sessions/{pre_s['id']}/start", headers=p_headers)
    assert start_resp.status_code == 200, start_resp.text

    # Soft deactivate → 409 because one session is in_progress.
    resp = client.post(
        f"/api/v1/groups/{g['id']}/deactivate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 409, resp.text
    detail_409: Any = resp.json()["detail"]
    assert isinstance(detail_409, dict)
    assert detail_409["in_progress_count"] >= 1

    # Force deactivate → 200; activated sessions expire, in_progress stays.
    resp = client.post(
        f"/api/v1/groups/{g['id']}/deactivate",
        json={"session_type": "pre", "intervention_session_number": 1, "force": True},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    assert body["in_progress_count"] >= 1
    assert len(body["expired"]) >= 1

    # Verify the in_progress session was NOT expired.
    updated: list[dict[str, Any]] = client.get(
        f"/api/v1/studies/{study['id']}/sessions",
        headers=researcher_headers,
        params={"participant_id": parts[0]["id"]},
    ).json()
    still_in_progress = next(s for s in updated if s["id"] == pre_s["id"])
    assert still_in_progress["status"] == "in_progress"


# ---- MOD-12 (MFR-215/MFR-216): name-based activation tests ------------------


def test_activate_name_based_not_counter_based(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-215/MFR-215: regression — activate uses explicit IS from request, not group counter."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=2)

    # Step 2: set group counter to 99 (no sessions at IS 99 exist) — simulate misaligned state.
    client.patch(
        f"/api/v1/groups/{g['id']}",
        json={"current_intervention_session": 99},
        headers=researcher_headers,
    )

    # Step 3: call activate with explicit IS=1 (request IS=1 != group counter 99).
    # OLD code: used counter=99, found no sessions, returned activated:[].
    # NEW code: uses payload.intervention_session_number=1, activates IS-1 sessions.
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()

    # Step 4: both IS-1 pre sessions activated; counter side-effect updates to 1.
    assert len(body["activated"]) == 2, f"expected 2 activated, got: {body}"
    for item in body["activated"]:
        assert item["session_type"] == "pre"
    detail = client.get(f"/api/v1/groups/{g['id']}", headers=researcher_headers).json()
    assert detail["current_intervention_session"] == 1

    # Steps 5-6: activate IS-1 again (sessions now 'activated', not 'created'/'expired').
    # Side effect fires; zero result does not error.
    resp2 = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert resp2.status_code == 409, resp2.text  # global guard: IS-1 pre still activated


def test_activate_request_pre_without_is_number_returns_422(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216: pre without intervention_session_number → 422."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre"},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "intervention_session_number" in str(resp.json()["detail"])


def test_activate_request_post_without_is_number_returns_422(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216: post with intervention_session_number=null → 422."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "post", "intervention_session_number": None},
        headers=researcher_headers,
    )
    assert resp.status_code == 422, resp.text
    assert "intervention_session_number" in str(resp.json()["detail"])


def test_activate_request_onboarding_ignores_is_number(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / D-12.4: onboarding with non-null IS is coerced to null; activates correctly."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding", "intervention_session_number": 3},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    assert len(body["activated"]) == 1
    assert body["activated"][0]["session_type"] == "onboarding"


def test_activate_onboarding_no_is_required(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216: onboarding with no IS (null counter) → 200."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    # Group counter is None (never set by _setup_group_with_protocol).
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["activated"]) == 1


def test_current_is_side_effect_pre_activate(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / MFR-212: activate pre IS=3 sets group.current_intervention_session = 3."""
    study, parts, g = _setup_group_with_protocol(
        client, researcher_headers, num_members=1
    )
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 3},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    detail = client.get(f"/api/v1/groups/{g['id']}", headers=researcher_headers).json()
    assert detail["current_intervention_session"] == 3


def test_current_is_side_effect_pre_deactivate(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / MFR-212: deactivate pre IS=3 sets group.current_intervention_session = 3."""
    study, parts, g = _setup_group_with_protocol(
        client, researcher_headers, num_members=1
    )
    # Activate IS-3 pre first (so there's something to deactivate).
    client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 3},
        headers=researcher_headers,
    )
    # Now deactivate IS-3 pre (counter currently 3 from above).
    # Set counter to 1 via patch to verify deactivate overrides it.
    client.patch(
        f"/api/v1/groups/{g['id']}",
        json={"current_intervention_session": 1},
        headers=researcher_headers,
    )
    resp = client.post(
        f"/api/v1/groups/{g['id']}/deactivate",
        json={"session_type": "pre", "intervention_session_number": 3},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    detail = client.get(f"/api/v1/groups/{g['id']}", headers=researcher_headers).json()
    assert detail["current_intervention_session"] == 3


def test_current_is_not_updated_for_onboarding(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / MFR-212: onboarding activate/deactivate does not change group IS counter."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    client.patch(
        f"/api/v1/groups/{g['id']}",
        json={"current_intervention_session": 7},
        headers=researcher_headers,
    )
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "onboarding"},
        headers=researcher_headers,
    )
    assert resp.status_code == 200, resp.text
    detail = client.get(f"/api/v1/groups/{g['id']}", headers=researcher_headers).json()
    assert detail["current_intervention_session"] == 7  # unchanged


def test_sessions_overview_endpoint(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / MAC-201: sessions-overview returns stages ordered by order_index."""
    from app.services.protocol import compute_display_label as cdl

    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=2)
    resp = client.get(f"/api/v1/groups/{g['id']}/sessions-overview", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    stages = body["stages"]

    # _setup_group_with_protocol: num_intervention_sessions=3, sessions_per_week=3
    # → 1 onboarding + 3 pre + 3 post = 7 stages
    assert len(stages) == 7, f"expected 7 stages, got {stages}"

    # First stage: onboarding (order_index=1).
    s0 = stages[0]
    assert s0["session_type"] == "onboarding"
    assert s0["intervention_session_number"] is None
    assert s0["display_label"] == "Onboarding"
    assert s0["order_index"] == 1
    assert s0["member_total"] == 2

    # All seven status keys present with 0 except 'created'.
    expected_keys = {"created", "expired", "activated", "in_progress", "completed", "abandoned", "cancelled"}
    for st in stages:
        assert set(st["counts"].keys()) == expected_keys, f"wrong count keys: {st}"
        assert st["counts"]["created"] == st["member_total"]

    # Ordered by order_index ascending.
    order_indices = [s["order_index"] for s in stages]
    assert order_indices == sorted(order_indices)

    # Second stage: pre IS=1; display_label matches compute_display_label.
    s1 = stages[1]
    assert s1["session_type"] == "pre"
    assert s1["intervention_session_number"] == 1
    assert s1["display_label"] == cdl("pre", s1["week_number"], s1["day_within_week"])


def test_sessions_overview_empty_for_no_protocol(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216: sessions-overview returns stages:[] when no sessions generated."""
    study = _study(client, researcher_headers)
    parts = _participants(client, researcher_headers, study["id"], 1)
    g = _group(client, researcher_headers, study["id"], "No Protocol")
    client.post(
        f"/api/v1/groups/{g['id']}/assign",
        json={"participant_ids": [parts[0]["id"]]},
        headers=researcher_headers,
    )
    resp = client.get(f"/api/v1/groups/{g['id']}/sessions-overview", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["stages"] == []


def test_global_guard_still_enforced(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MFR-216 / MFR-115: global guard blocks activation when member has open session."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    # Activate IS-1 pre.
    activate_resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "pre", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert activate_resp.status_code == 200
    assert len(activate_resp.json()["activated"]) >= 1

    # Try activating IS-1 post → 409 (member has open IS-1 pre).
    resp = client.post(
        f"/api/v1/groups/{g['id']}/activate",
        json={"session_type": "post", "intervention_session_number": 1},
        headers=researcher_headers,
    )
    assert resp.status_code == 409, resp.text
    detail: Any = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert "blocking" in detail
    assert len(detail["blocking"]) >= 1


def test_activate_is_range_validation(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    """MAC-209: intervention_session_number must be in [1, 156]."""
    study, parts, g = _setup_group_with_protocol(client, researcher_headers, num_members=1)
    for bad_is in (0, 157):
        resp = client.post(
            f"/api/v1/groups/{g['id']}/activate",
            json={"session_type": "pre", "intervention_session_number": bad_is},
            headers=researcher_headers,
        )
        assert resp.status_code == 422, f"expected 422 for IS={bad_is}, got {resp.status_code}"
