"""CSV/ZIP export tests (FR-54..FR-57, AC-54..AC-57) and preview (FR-33, AC-33)."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Session as SessionModel
from app.services.exports import (
    DEMOGRAPHICS_COLUMNS,
    PARTICIPANT_SUMMARY_COLUMNS,
    SESSION_SUMMARY_COLUMNS,
    TRIAL_COLUMNS,
)
from app.task_defaults import default_params
from tests.helpers import create_study_participant_session, run_to_completion


def _read_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = list(reader)
    fieldnames = reader.fieldnames
    assert fieldnames is not None
    return list(fieldnames), rows


def test_session_and_participant_csv_exports(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study, participant, sessions, headers = create_study_participant_session(
        client,
        researcher_headers,
        name="Export Study",
        practice_trials=1,
        test_trials=2,
        count=2,
    )
    session1, session2 = sessions[0], sessions[1]

    run_to_completion(client, headers, session1["id"], practice_trials=1, test_trials=2)
    run_to_completion(client, headers, session2["id"], practice_trials=1, test_trials=2)

    resp = client.get(f"/api/v1/sessions/{session1['id']}/export.csv", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")

    pattern = re.compile(
        r'^attachment; filename="export_study_session_'
        + re.escape(session1["code"])
        + r'_\d{8}-\d{4}\.csv"$'
    )
    assert pattern.match(resp.headers["content-disposition"]), resp.headers["content-disposition"]

    header, rows = _read_csv(resp.text)
    assert header == TRIAL_COLUMNS
    assert len(rows) == 3  # 1 practice + 2 test

    practice_rows = [r for r in rows if r["block"] == "practice"]
    test_rows = [r for r in rows if r["block"] == "test"]
    assert len(practice_rows) == 1
    assert len(test_rows) == 2

    for row in rows:
        assert row["study_name"] == "Export Study"
        assert row["study_id"] == study["id"]
        assert row["task_type"] == "CRT3"
        assert row["participant_code"] == participant["code"]
        assert row["session_code"] == session1["code"]
        assert row["session_order"] == "1"
        assert row["attempt"] == "1"
        assert row["outcome"] == "correct"
        assert row["rt_ms"] == "400.0"
        assert row["outlier_flag"] == "False"
        assert row["session_started_at_iso"].endswith("+00:00")
        assert row["session_completed_at_iso"].endswith("+00:00")

    resp2 = client.get(
        f"/api/v1/participants/{participant['id']}/export.csv", headers=researcher_headers
    )
    assert resp2.status_code == 200, resp2.text

    pattern2 = re.compile(
        r'^attachment; filename="export_study_participant_'
        + re.escape(participant["code"])
        + r'_\d{8}-\d{4}\.csv"$'
    )
    assert pattern2.match(resp2.headers["content-disposition"]), resp2.headers["content-disposition"]

    header2, rows2 = _read_csv(resp2.text)
    assert header2 == TRIAL_COLUMNS
    assert len(rows2) == 6  # both sessions, 1 practice + 2 test each

    codes_seen = {r["session_code"] for r in rows2}
    assert codes_seen == {session1["code"], session2["code"]}
    for code in (session1["code"], session2["code"]):
        assert sum(1 for r in rows2 if r["session_code"] == code) == 3


def test_study_export_zip_contains_four_files(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    study, participant, sessions, headers = create_study_participant_session(
        client,
        researcher_headers,
        name="Zip Study",
        practice_trials=0,
        test_trials=2,
        count=2,
    )
    session1, session2 = sessions[0], sessions[1]

    field_resp = client.post(
        f"/api/v1/studies/{study['id']}/demographic-fields",
        json={"label": "Age", "field_type": "number", "required": True, "frequency": "once"},
        headers=researcher_headers,
    )
    assert field_resp.status_code == 201, field_resp.text
    field = field_resp.json()

    start_resp = client.post(f"/api/v1/sessions/{session1['id']}/start", headers=headers)
    assert start_resp.status_code == 200, start_resp.text
    assert any(f["id"] == field["id"] for f in start_resp.json()["demographics_due"])

    demo_resp = client.post(
        f"/api/v1/sessions/{session1['id']}/demographics",
        json={"answers": [{"field_id": field["id"], "value": "29"}]},
        headers=headers,
    )
    assert demo_resp.status_code == 204, demo_resp.text

    # Session1 already started above (demographics check); skip the /start call.
    run_to_completion(client, headers, session1["id"], practice_trials=0, test_trials=2, skip_start=True)

    resp = client.get(f"/api/v1/studies/{study['id']}/export.zip", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/zip"

    pattern = re.compile(r'^attachment; filename="zip_study_study_\d{8}-\d{4}\.zip"$')
    assert pattern.match(resp.headers["content-disposition"]), resp.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert zf.namelist() == [
        "trials.csv",
        "sessions_summary.csv",
        "participants_summary.csv",
        "demographics.csv",
    ]

    trials_header, trials_rows = _read_csv(zf.read("trials.csv").decode("utf-8"))
    assert trials_header == TRIAL_COLUMNS
    assert len(trials_rows) == 2
    assert all(r["session_code"] == session1["code"] for r in trials_rows)
    assert all(r["block"] == "test" for r in trials_rows)

    sessions_header, sessions_rows = _read_csv(zf.read("sessions_summary.csv").decode("utf-8"))
    assert sessions_header == SESSION_SUMMARY_COLUMNS
    assert len(sessions_rows) == 2

    by_code = {r["session_code"]: r for r in sessions_rows}
    row1, row2 = by_code[session1["code"]], by_code[session2["code"]]

    assert row1["status"] == "completed"
    assert row1["n_trials"] == "2"
    assert row1["n_correct"] == "2"
    assert row1["accuracy_pct"] == "100.0"
    assert row1["mean_rt_ms_raw"] == "400.0"
    assert row1["mean_rt_ms_trim"] == "400.0"
    assert row1["started_at_iso"].endswith("+00:00")
    assert row1["completed_at_iso"].endswith("+00:00")

    assert row2["status"] == "activated"  # MOD-5: auto-activated by test helper
    assert row2["n_trials"] == "0"
    assert row2["n_correct"] == "0"
    assert row2["accuracy_pct"] == ""
    assert row2["mean_rt_ms_raw"] == ""
    assert row2["started_at_iso"] == ""
    assert row2["completed_at_iso"] == ""

    participants_header, participants_rows = _read_csv(
        zf.read("participants_summary.csv").decode("utf-8")
    )
    assert participants_header == PARTICIPANT_SUMMARY_COLUMNS
    assert len(participants_rows) == 1
    prow = participants_rows[0]
    assert prow["participant_code"] == participant["code"]
    assert prow["n_completed_sessions"] == "1"
    assert prow["mean_of_session_means_ms_raw"] == ""
    assert prow["iiv_between_ms_raw"] == ""
    assert prow["cov_between_raw"] == ""
    assert prow["mean_of_session_means_ms_trim"] == ""
    assert prow["iiv_between_ms_trim"] == ""
    assert prow["cov_between_trim"] == ""

    demo_header, demo_rows = _read_csv(zf.read("demographics.csv").decode("utf-8"))
    assert demo_header == DEMOGRAPHICS_COLUMNS
    assert len(demo_rows) == 1
    drow = demo_rows[0]
    assert drow["participant_code"] == participant["code"]
    assert drow["session_code"] == ""
    assert drow["field_label"] == "Age"
    assert drow["field_type"] == "number"
    assert drow["value"] == "29"
    assert drow["answered_at_iso"].endswith("+00:00")


def test_preview_caps_trial_counts_and_creates_no_rows(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    resp = client.post(
        "/api/v1/studies",
        json={
            "name": "Preview Study",
            "task_type": "CRT3",
            "params": {"practice_trials": 10, "test_trials": 50},
        },
        headers=researcher_headers,
    )
    assert resp.status_code == 201, resp.text
    study: dict[str, Any] = resp.json()

    db = SessionLocal()
    try:
        count_before = db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.study_id == study["id"])
        ).scalar_one()
    finally:
        db.close()
    assert count_before == 0

    resp2 = client.post(f"/api/v1/studies/{study['id']}/preview", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()

    assert data["task_type"] == "CRT3"
    assert data["params"]["practice_trials"] == 3
    assert data["params"]["test_trials"] == 3
    assert data["params"]["key_map"] == default_params("CRT3")["key_map"]

    db2 = SessionLocal()
    try:
        count_after = db2.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.study_id == study["id"])
        ).scalar_one()
    finally:
        db2.close()
    assert count_after == 0

    resp3 = client.post(
        "/api/v1/studies/00000000-0000-0000-0000-000000000000/preview", headers=researcher_headers
    )
    assert resp3.status_code == 404


def test_export_unknown_ids_return_404(client: TestClient, researcher_headers: dict[str, str]) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    resp = client.get(f"/api/v1/sessions/{unknown}/export.csv", headers=researcher_headers)
    assert resp.status_code == 404

    resp2 = client.get(f"/api/v1/participants/{unknown}/export.csv", headers=researcher_headers)
    assert resp2.status_code == 404

    resp3 = client.get(f"/api/v1/studies/{unknown}/export.zip", headers=researcher_headers)
    assert resp3.status_code == 404
