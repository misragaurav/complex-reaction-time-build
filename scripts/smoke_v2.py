#!/usr/bin/env python3
"""Modifications smoke test — exercises MOD-2 through MOD-5 end-to-end.

Scenario:
  1. Create a v2 study (sessions_per_week=3, num_intervention_sessions=24).
  2. Create 4 participants, generate the 49-session protocol.
  3. Verify display_label values for selected sessions (MOD-3, D-15).
  4. Create a group, assign all 4 participants, set current_intervention_session=1.
  5. Group-activate (MFR-31); verify activated sessions and display_label (MOD-5).
  6. Attempt to start a non-activated session → assert 403.
  7. Start the activated session for participant 1 (now in_progress).
  8. Deactivate with force=false → assert 409 (in_progress session blocks).
  9. Deactivate with force=true → assert 3 sessions expired.
  10. Complete participant 1's session (trials + /complete).
  11. Verify group_name in study export CSV (MOD-4).
  Exit 0 on success.

Usage:
    python scripts/smoke_v2.py [--base-url http://localhost:8080] \\
        [--admin-email admin@example.com] [--admin-password AdminDev2024!]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from typing import Any

CHECK = "✓"
FAIL  = "✗"


class SmokeFailure(Exception):
    pass


class Client:
    def __init__(self, base_url: str) -> None:
        self.api = base_url.rstrip("/") + "/api/v1"
        self.token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
    ) -> tuple[int, bytes, dict[str, str]]:
        url = self.api + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                status, payload = res.status, res.read()
                headers = {k.lower(): v for k, v in res.headers.items()}
        except urllib.error.HTTPError as e:
            status, payload = e.code, e.read()
            headers = {k.lower(): v for k, v in e.headers.items()}
        except urllib.error.URLError as e:
            raise SmokeFailure(f"{method} {url}: connection failed ({e.reason})") from e

        expected = expect if isinstance(expect, tuple) else (expect,)
        if status not in expected:
            raise SmokeFailure(
                f"{method} {path}: expected {expected}, got {status}: "
                f"{payload[:300].decode(errors='replace')}"
            )
        return status, payload, headers

    def json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
    ) -> Any:
        _, payload, _ = self.request(method, path, body, expect)
        return json.loads(payload) if payload else None


def step(message: str) -> None:
    print(f"  {CHECK} {message}")


def fail(message: str) -> None:
    raise SmokeFailure(message)


def wait_for_health(client: Client, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error = "no attempt made"
    while time.monotonic() < deadline:
        try:
            body = client.json("GET", "/health")
            if body.get("status") == "ok" and body.get("db") == "ok":
                step(f"health: {body}")
                return
            last_error = f"unhealthy response: {body}"
        except SmokeFailure as e:
            last_error = str(e)
        time.sleep(2)
    raise SmokeFailure(f"/health not ok within {timeout_s:.0f}s; last error: {last_error}")


def make_trials(params: dict[str, Any], attempt: int) -> list[dict[str, Any]]:
    rng = random.Random(2026)
    key_map: list[str] = params["key_map"]
    trials: list[dict[str, Any]] = []
    onset = 5_000.0
    for block, count in (("practice", params["practice_trials"]), ("test", params["test_trials"])):
        for index in range(1, count + 1):
            position = rng.randrange(len(key_map))
            rt = round(rng.uniform(250.0, 600.0), 1)
            trials.append(
                {
                    "client_uuid": str(uuid.uuid4()),
                    "attempt": attempt,
                    "block": block,
                    "trial_index": index,
                    "stimulus_position": position,
                    "foreperiod_ms": rng.randint(
                        params["foreperiod_min_ms"], params["foreperiod_max_ms"]
                    ),
                    "key_pressed": key_map[position],
                    "response_position": position,
                    "outcome": "correct",
                    "rt_ms": rt,
                    "premature_count": 0,
                    "extraneous_keys": 0,
                    "invalid_reason": None,
                    "stimulus_onset_client_ms": onset,
                    "response_client_ms": onset + rt,
                }
            )
            onset += 5_000.0
    return trials


def run(base_url: str, admin_email: str, admin_password: str, health_timeout_s: float) -> None:
    suffix = uuid.uuid4().hex[:6].upper()
    R = Client(base_url)  # researcher/admin client

    print("CRT v2 smoke test")
    wait_for_health(R, health_timeout_s)

    # ------------------------------------------------------------------
    # Admin login.
    # ------------------------------------------------------------------
    login = R.json("POST", "/auth/login", {"email": admin_email, "password": admin_password})
    R.token = login["access_token"]
    step(f"admin login as {login['user']['email']}")

    # ------------------------------------------------------------------
    # MOD-3: create a study with protocol config.
    # Mixed task types: onboarding=CRT3, pre=SRT (MOD-2), post=CRT4.
    # ------------------------------------------------------------------
    study = R.json(
        "POST",
        "/studies",
        {
            "name": f"Smoke-v2-{suffix}",
            "task_type": "CRT4",
            "num_intervention_sessions": 24,
            "sessions_per_week": 3,
            "task_type_onboarding": "CRT3",
            "task_type_pre": "SRT",
            "task_type_post": "CRT4",
        },
        expect=201,
    )
    study_id = study["id"]
    if study["num_intervention_sessions"] != 24 or study["sessions_per_week"] != 3:
        fail(f"unexpected protocol config: {study}")
    step(
        f"study created ({study['name']}): "
        f"N={study['num_intervention_sessions']}, SPW={study['sessions_per_week']}"
    )

    # ------------------------------------------------------------------
    # Create 4 participants.
    # ------------------------------------------------------------------
    plist = R.json(
        "POST",
        f"/studies/{study_id}/participants",
        {"count": 4, "prefix": "V2SMK"},
        expect=201,
    )
    if len(plist) != 4:
        fail(f"expected 4 participants, got {len(plist)}")
    step(f"4 participants created: {[p['code'] for p in plist]}")

    # ------------------------------------------------------------------
    # MOD-3: generate the full 49-session protocol.
    # ------------------------------------------------------------------
    p0_id = plist[0]["id"]
    gen = R.json(
        "POST",
        f"/studies/{study_id}/generate-protocol",
        {"participant_ids": [p["id"] for p in plist]},
        expect=201,
    )
    if len(gen["created"]) != 4 or gen["created"][0]["session_count"] != 49:
        fail(f"unexpected generate-protocol response: {gen}")
    step(
        f"protocol generated: {gen['created'][0]['session_count']} sessions "
        f"x {len(gen['created'])} participants"
    )

    # ------------------------------------------------------------------
    # Verify display_label values (MOD-3, D-15).
    # Reference participant: plist[0].
    # Expected (sessions_per_week=3, num_intervention_sessions=24):
    #   order_index=1  -> "Onboarding"
    #   order_index=2  -> "Week 1 · Day 1 · Pre"    (k=1, pre)
    #   order_index=4  -> "Week 1 · Day 2 · Pre"    (k=2, pre)
    #   order_index=5  -> "Week 1 · Day 2 · Post"   (k=2, post)
    #   order_index=24 -> "Week 4 · Day 3 · Pre"    (k=12, pre)
    # ------------------------------------------------------------------
    sessions_all = R.json("GET", f"/studies/{study_id}/sessions")
    p0_sessions = {s["order_index"]: s for s in sessions_all if s["participant_id"] == p0_id}
    if len(p0_sessions) != 49:
        fail(f"expected 49 sessions for participant 0, got {len(p0_sessions)}")

    expected_labels = {
        1:  "Onboarding",
        2:  "Week 1 · Day 1 · Pre",
        4:  "Week 1 · Day 2 · Pre",
        5:  "Week 1 · Day 2 · Post",
        24: "Week 4 · Day 3 · Pre",
    }
    for idx, expected in expected_labels.items():
        got = p0_sessions[idx]["display_label"]
        if got != expected:
            fail(f"display_label order_index={idx}: expected {expected!r}, got {got!r}")
    step("display_label values correct for order_index 1, 2, 4, 5, 24")

    # ------------------------------------------------------------------
    # MOD-4: create a group, assign all 4 participants.
    # ------------------------------------------------------------------
    group = R.json(
        "POST",
        f"/studies/{study_id}/groups",
        {"name": f"Group-{suffix}", "description": "smoke group"},
        expect=201,
    )
    group_id = group["id"]
    step(f"group created: {group['name']}")

    assign = R.json(
        "POST",
        f"/groups/{group_id}/assign",
        {"participant_ids": [p["id"] for p in plist]},
    )
    if len(assign["assigned"]) != 4 or assign["conflicts"]:
        fail(f"unexpected assign response: {assign}")
    step(f"4 participants assigned to group")

    R.json("PATCH", f"/groups/{group_id}", {"current_intervention_session": 1})
    step("current_intervention_session set to 1")

    # ------------------------------------------------------------------
    # MOD-5: group activate — opens the k=1 pre-sessions for all members.
    # ------------------------------------------------------------------
    act_resp = R.json("POST", f"/groups/{group_id}/activate")
    activated = act_resp["activated"]
    if len(activated) != 4:
        fail(f"expected 4 activated sessions, got {len(activated)}: {activated}")
    for item in activated:
        if item["display_label"] != "Week 1 · Day 1 · Pre":
            fail(
                f"activated session for {item['code']} has wrong label: "
                f"{item['display_label']!r} (expected 'Week 1 · Day 1 · Pre')"
            )
        if item["order_index"] != 2:
            fail(f"activated session has wrong order_index={item['order_index']}, expected 2")
    step(f"group activated: {len(activated)} sessions, label='Week 1 · Day 1 · Pre', order_index=2 ✓")

    # ------------------------------------------------------------------
    # MOD-5: set up participant 0 client (needed for /start calls).
    # ------------------------------------------------------------------
    P0 = Client(base_url)
    p0_login_resp = P0.json(
        "POST",
        "/auth/participant/set-password",
        {"code": plist[0]["code"], "password": "smoke-v2-pw"},
    )
    P0.token = p0_login_resp["access_token"]
    step(f"participant {plist[0]['code']} logged in")

    # ------------------------------------------------------------------
    # MOD-5: attempt to start a 'created' session (NOT the activated one) -> 403.
    # Use order_index=3 (k=1, post) which is still in 'created' state.
    # ------------------------------------------------------------------
    P0.request("POST", f"/sessions/{p0_sessions[3]['id']}/start", expect=403)
    step("start on created session (order_index=3) -> 403 as expected")

    # ------------------------------------------------------------------
    # MOD-5: start the activated session for participant 0.
    # ------------------------------------------------------------------
    p0_activated = next(s for s in activated if s["participant_id"] == p0_id)
    p0_activated_session_id = p0_activated["session_id"]

    start_resp = P0.json("POST", f"/sessions/{p0_activated_session_id}/start")
    if start_resp["task_type"] != "SRT":
        fail(f"expected SRT task type for k=1 pre, got {start_resp['task_type']}")
    step(f"participant {plist[0]['code']} started activated session (SRT, attempt {start_resp['attempt']})")

    # ------------------------------------------------------------------
    # MOD-5: deactivate with force=false → 409 (participant 0 is in_progress).
    # ------------------------------------------------------------------
    R.request("POST", f"/groups/{group_id}/deactivate", {"force": False}, expect=409)
    step("deactivate force=false → 409 (in_progress session blocks) ✓")

    # ------------------------------------------------------------------
    # MOD-5: deactivate with force=true → 3 remaining activated → expired.
    # ------------------------------------------------------------------
    deact = R.json("POST", f"/groups/{group_id}/deactivate", {"force": True})
    if len(deact["expired"]) != 3:
        fail(f"expected 3 expired sessions, got {len(deact['expired'])}")
    if deact["in_progress_count"] != 1:
        fail(f"expected in_progress_count=1, got {deact['in_progress_count']}")
    step(f"deactivate force=true → {len(deact['expired'])} expired, {deact['in_progress_count']} in_progress left")

    # Verify expired sessions have status='expired' in DB (single fetch).
    expired_ids = {item["session_id"] for item in deact["expired"]}
    refreshed = {x["id"]: x for x in R.json("GET", f"/studies/{study_id}/sessions")}
    for sid in expired_ids:
        found = refreshed.get(sid)
        if found is None:
            fail(f"expired session {sid} not found in study sessions")
        if found["status"] != "expired":
            fail(f"session {found['code']} expected 'expired', got {found['status']!r}")
    step("all 3 deactivated sessions confirmed as 'expired' in DB ✓")

    # ------------------------------------------------------------------
    # Complete participant 0's in_progress session (trials -> complete).
    # ------------------------------------------------------------------
    trials = make_trials(start_resp["params"], start_resp["attempt"])
    accepted = 0
    for i in range(0, len(trials), 25):
        batch_resp = P0.json(
            "POST",
            f"/sessions/{p0_activated_session_id}/trials",
            {"trials": trials[i : i + 25]},
        )
        accepted += batch_resp["accepted"]
    if accepted != len(trials):
        fail(f"uploaded {len(trials)} trials but server accepted {accepted}")
    P0.json("POST", f"/sessions/{p0_activated_session_id}/complete", expect=204)
    step(f"participant {plist[0]['code']} completed their session ({len(trials)} trials)")

    # ------------------------------------------------------------------
    # MOD-4: verify group_name in study export CSV.
    # ------------------------------------------------------------------
    _, zip_bytes, _ = R.request("GET", f"/studies/{study_id}/export.zip")
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    sessions_csv = zf.read("sessions_summary.csv").decode("utf-8")
    reader = csv.DictReader(io.StringIO(sessions_csv))
    rows = list(reader)
    if not rows:
        fail("sessions_summary.csv is empty")
    if "group_name" not in (reader.fieldnames or []):
        fail(f"group_name not in sessions_summary.csv header: {reader.fieldnames}")
    completed_rows = [r for r in rows if r.get("status") == "completed"]
    if not completed_rows:
        fail("no completed session found in sessions_summary.csv")
    gname = completed_rows[0]["group_name"]
    if gname != group["name"]:
        fail(f"group_name in CSV is {gname!r}, expected {group['name']!r}")
    step(f"group_name '{gname}' present in sessions_summary.csv ✓")

    # Clean up.
    R.json("PATCH", f"/studies/{study_id}", {"is_archived": True})
    step("smoke study archived")

    print("SMOKE V2 TEST PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8080")
    )
    parser.add_argument(
        "--admin-email", default=os.environ.get("ADMIN_EMAIL", "admin@example.com")
    )
    parser.add_argument(
        "--admin-password", default=os.environ.get("ADMIN_PASSWORD", "AdminDev2024!")
    )
    parser.add_argument(
        "--health-timeout", type=float, default=120.0, help="seconds to wait for /health"
    )
    args = parser.parse_args()

    try:
        run(args.base_url, args.admin_email, args.admin_password, args.health_timeout)
    except SmokeFailure as e:
        print(f"{FAIL} SMOKE V2 TEST FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
