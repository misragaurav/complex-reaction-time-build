"""Demographic field tests (FR-12..FR-15, AC-12..AC-15)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _create_field(
    client: TestClient,
    headers: dict[str, str],
    study_id: str,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "label": "Age",
        "field_type": "number",
        "required": True,
        "frequency": "once",
    }
    payload.update(overrides)
    resp = client.post(
        f"/api/v1/studies/{study_id}/demographic-fields", json=payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, Any] = resp.json()
    return data


def test_single_choice_without_options_returns_422(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/demographic-fields",
        json={"label": "Handedness", "field_type": "single_choice", "frequency": "once"},
        headers=researcher_headers,
    )
    assert resp.status_code == 422


def test_single_choice_with_too_many_options_returns_422(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    resp = client.post(
        f"/api/v1/studies/{study['id']}/demographic-fields",
        json={
            "label": "Country",
            "field_type": "single_choice",
            "frequency": "once",
            "options": [f"Option {i}" for i in range(21)],
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 422


def test_create_and_list_demographic_fields_in_order(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    field1 = _create_field(client, researcher_headers, study["id"], label="Age")
    field2 = _create_field(
        client,
        researcher_headers,
        study["id"],
        label="Handedness",
        field_type="single_choice",
        options=["Left", "Right", "Ambidextrous"],
        frequency="every_session",
    )

    resp = client.get(
        f"/api/v1/studies/{study['id']}/demographic-fields", headers=researcher_headers
    )
    assert resp.status_code == 200, resp.text
    fields: list[dict[str, Any]] = resp.json()
    assert [f["id"] for f in fields] == [field1["id"], field2["id"]]
    assert [f["display_order"] for f in fields] == [0, 1]
    assert all(f["has_responses"] is False for f in fields)


def test_required_field_missing_on_submit_returns_422(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    _create_field(client, researcher_headers, study["id"], label="Age", required=True)

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text
    assert any(f["label"] == "Age" for f in resp.json()["demographics_due"])

    resp2 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={"answers": []},
        headers=participant_headers,
    )
    assert resp2.status_code == 422


def test_answer_validation_for_field_types(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    number_field = _create_field(client, researcher_headers, study["id"], label="Age")
    choice_field = _create_field(
        client,
        researcher_headers,
        study["id"],
        label="Handedness",
        field_type="single_choice",
        options=["Left", "Right"],
        frequency="once",
    )
    bool_field = _create_field(
        client,
        researcher_headers,
        study["id"],
        label="Wears glasses",
        field_type="boolean",
        frequency="once",
        required=False,
    )

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    # Bad number value.
    resp2 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={
            "answers": [
                {"field_id": number_field["id"], "value": "not-a-number"},
                {"field_id": choice_field["id"], "value": "Left"},
            ]
        },
        headers=participant_headers,
    )
    assert resp2.status_code == 422

    # Bad single_choice value.
    resp3 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={
            "answers": [
                {"field_id": number_field["id"], "value": "29"},
                {"field_id": choice_field["id"], "value": "Neither"},
            ]
        },
        headers=participant_headers,
    )
    assert resp3.status_code == 422

    # Valid submission, including an optional boolean field.
    resp4 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={
            "answers": [
                {"field_id": number_field["id"], "value": "29"},
                {"field_id": choice_field["id"], "value": "Left"},
                {"field_id": bool_field["id"], "value": "true"},
            ]
        },
        headers=participant_headers,
    )
    assert resp4.status_code == 204, resp4.text


def test_answered_field_rejects_label_edit_and_delete_retires_it(
    client: TestClient,
    researcher_headers: dict[str, str],
    study: dict[str, Any],
    session: dict[str, Any],
    participant_headers: dict[str, str],
) -> None:
    field = _create_field(client, researcher_headers, study["id"], label="Age", required=False)

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=participant_headers)
    assert resp.status_code == 200, resp.text

    resp2 = client.post(
        f"/api/v1/sessions/{session['id']}/demographics",
        json={"answers": [{"field_id": field["id"], "value": "42"}]},
        headers=participant_headers,
    )
    assert resp2.status_code == 204, resp2.text

    # Label/options edits are now rejected.
    resp3 = client.patch(
        f"/api/v1/demographic-fields/{field['id']}",
        json={"label": "Age (years)"},
        headers=researcher_headers,
    )
    assert resp3.status_code == 409

    # But other attributes (e.g. `required`) can still change.
    resp4 = client.patch(
        f"/api/v1/demographic-fields/{field['id']}",
        json={"required": True},
        headers=researcher_headers,
    )
    assert resp4.status_code == 200, resp4.text
    assert resp4.json()["required"] is True

    # DELETE retires rather than removing.
    resp5 = client.delete(
        f"/api/v1/demographic-fields/{field['id']}", headers=researcher_headers
    )
    assert resp5.status_code == 204

    resp6 = client.get(
        f"/api/v1/studies/{study['id']}/demographic-fields", headers=researcher_headers
    )
    assert resp6.status_code == 200, resp6.text
    fields = resp6.json()
    assert len(fields) == 1
    assert fields[0]["id"] == field["id"]
    assert fields[0]["is_retired"] is True
    assert fields[0]["has_responses"] is True


def test_unanswered_field_delete_removes_it(
    client: TestClient, researcher_headers: dict[str, str], study: dict[str, Any]
) -> None:
    field = _create_field(client, researcher_headers, study["id"], label="Unused")

    resp = client.delete(
        f"/api/v1/demographic-fields/{field['id']}", headers=researcher_headers
    )
    assert resp.status_code == 204

    resp2 = client.get(
        f"/api/v1/studies/{study['id']}/demographic-fields", headers=researcher_headers
    )
    assert resp2.json() == []
