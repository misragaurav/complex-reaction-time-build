"""Summary statistics tests (FR-47..FR-49, AC-47..AC-49, D-9/D-10)."""

from __future__ import annotations

import statistics

from fastapi.testclient import TestClient

from tests.helpers import (
    KEY_MAP_CRT3,
    correct_trial,
    create_study_participant_session,
    incorrect_trial,
    run_to_completion,
    timeout_trial,
)


def _expected_rt_stats(rts: list[float]) -> dict[str, float | int | None]:
    n = len(rts)
    if n == 0:
        return {
            "n": 0,
            "mean_rt_ms": None,
            "median_rt_ms": None,
            "sd_rt_ms": None,
            "cov": None,
            "iiv_within_ms": None,
        }
    mean = statistics.mean(rts)
    median = statistics.median(rts)
    sd: float | None
    cov: float | None
    if n >= 2:
        sd = statistics.stdev(rts)
        cov = (sd / mean) if mean else None
    else:
        sd = None
        cov = None
    return {
        "n": n,
        "mean_rt_ms": round(mean, 4),
        "median_rt_ms": round(median, 4),
        "sd_rt_ms": round(sd, 4) if sd is not None else None,
        "cov": round(cov, 4) if cov is not None else None,
        "iiv_within_ms": round(sd, 4) if sd is not None else None,
    }


def test_session_summary_matches_hand_computed_stats(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    _study, _participant, sessions, headers = create_study_participant_session(
        client, researcher_headers, name="AC47 Stats Study", test_trials=20
    )
    session = sessions[0]

    outlier_rt = 120.0
    plain_rts = [300.0 + 10.0 * i for i in range(16)]  # 300, 310, ..., 450

    trials = [correct_trial("test", 1, 0, rt_ms=outlier_rt, key_map=KEY_MAP_CRT3)]
    for offset, rt in enumerate(plain_rts):
        idx = offset + 2  # indices 2..17
        trials.append(correct_trial("test", idx, idx % 3, rt_ms=rt, key_map=KEY_MAP_CRT3))
    trials.append(incorrect_trial("test", 18, 0, rt_ms=400.0, key_map=KEY_MAP_CRT3))
    trials.append(incorrect_trial("test", 19, 1, rt_ms=410.0, key_map=KEY_MAP_CRT3))
    trials.append(timeout_trial("test", 20, 2))

    resp = client.post(f"/api/v1/sessions/{session['id']}/start", headers=headers)
    assert resp.status_code == 200, resp.text
    for i in range(0, len(trials), 25):
        batch = trials[i : i + 25]
        resp_batch = client.post(
            f"/api/v1/sessions/{session['id']}/trials", json={"trials": batch}, headers=headers
        )
        assert resp_batch.status_code == 200, resp_batch.text
    resp_complete = client.post(f"/api/v1/sessions/{session['id']}/complete", headers=headers)
    assert resp_complete.status_code == 204, resp_complete.text

    resp2 = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    data = resp2.json()

    raw_rts = [outlier_rt] + plain_rts
    trimmed_rts = plain_rts

    assert data["n_trials"] == 20
    assert data["n_correct"] == 17
    assert data["n_timeouts"] == 1
    assert data["n_invalid"] == 0
    assert data["n_premature"] == 0
    assert data["n_outliers_flagged"] == 1
    assert data["accuracy_pct"] == round(17 / 20 * 100, 4)
    assert len(data["trials"]) == 20

    expected_raw = _expected_rt_stats(raw_rts)
    expected_trimmed = _expected_rt_stats(trimmed_rts)
    for key, value in expected_raw.items():
        assert data["raw"][key] == value, key
    for key, value in expected_trimmed.items():
        assert data["trimmed"][key] == value, key

    assert data["raw"]["iiv_within_ms"] == data["raw"]["sd_rt_ms"]
    assert data["trimmed"]["iiv_within_ms"] == data["trimmed"]["sd_rt_ms"]


def test_cross_session_statistics_and_study_summary(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    _study, participant, sessions, headers = create_study_participant_session(
        client, researcher_headers, name="AC48 Cross-Session Study", test_trials=4, count=3
    )
    assert [s["order_index"] for s in sessions] == [1, 2, 3]

    session_means = [300.0, 400.0, 500.0]
    for session, rt in zip(sessions, session_means, strict=True):
        run_to_completion(client, headers, session["id"], practice_trials=0, test_trials=4, rt_ms=rt)

        resp = client.get(f"/api/v1/participants/{participant['id']}/summary", headers=researcher_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        n_done = session["order_index"]
        assert data["n_completed_sessions"] == n_done
        assert len(data["sessions"]) == n_done
        if n_done < 2:
            assert data["cross_session_raw"] == {
                "mean_of_session_means_ms": None,
                "iiv_between_ms": None,
                "cov_between": None,
            }
            assert data["cross_session_trimmed"] == data["cross_session_raw"]

    resp = client.get(f"/api/v1/participants/{participant['id']}/summary", headers=researcher_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    expected_mean = round(statistics.mean(session_means), 4)
    expected_sd = round(statistics.stdev(session_means), 4)
    expected_cov = round(expected_sd / expected_mean, 4)

    for cross in (data["cross_session_raw"], data["cross_session_trimmed"]):
        assert cross["mean_of_session_means_ms"] == expected_mean
        assert cross["iiv_between_ms"] == expected_sd
        assert cross["cov_between"] == expected_cov

    for s, rt in zip(data["sessions"], session_means, strict=True):
        assert s["raw"]["mean_rt_ms"] == rt
        assert s["accuracy_pct"] == 100.0

    resp2 = client.get(f"/api/v1/studies/{_study['id']}/summary", headers=researcher_headers)
    assert resp2.status_code == 200, resp2.text
    study_data = resp2.json()

    assert study_data["n_participants"] == 1
    assert study_data["n_sessions_total"] == 3
    assert study_data["n_sessions_completed"] == 3
    assert study_data["completion_pct"] == 100.0
    assert study_data["trimmed_mean_rt"] == {"mean": expected_mean, "sd": expected_sd, "n": 3}
    assert study_data["trimmed_sd_rt"] == {"mean": 0.0, "sd": 0.0, "n": 3}
    assert study_data["accuracy_pct"] == {"mean": 100.0, "sd": 0.0, "n": 3}


def test_summary_endpoints_unknown_ids_return_404(
    client: TestClient, researcher_headers: dict[str, str]
) -> None:
    unknown = "00000000-0000-0000-0000-000000000000"

    resp = client.get(f"/api/v1/sessions/{unknown}/summary", headers=researcher_headers)
    assert resp.status_code == 404

    resp2 = client.get(f"/api/v1/participants/{unknown}/summary", headers=researcher_headers)
    assert resp2.status_code == 404

    resp3 = client.get(f"/api/v1/studies/{unknown}/summary", headers=researcher_headers)
    assert resp3.status_code == 404
