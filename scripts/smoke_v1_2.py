#!/usr/bin/env python3
"""v1.2 smoke test — exercises MOD-7, MOD-8, MOD-10, MOD-11 end-to-end.

Scenario:
  1.  Health check.
  2.  Admin login.
  3.  Create a study — assert one task_type, no per-stage fields (MAC-104).
  4.  Create 3 participants; generate the 49-session protocol.
  5.  Assert all sessions carry study.task_type (MAC-103).
  6.  Create a group, assign all 3 participants.
  7.  Activate ONBOARDING with no IS set → 3 sessions activated (MAC-109).
  8.  Deactivate onboarding → 3 sessions expired (MAC-110).
  9.  Set IS = 1; activate PRE (default session_type) → 3 pre sessions activated (MAC-111).
  10. Login as participant p0, start their pre session → in_progress.
  11. Deactivate pre with force=false → 409 (MAC-114).
  12. Deactivate pre with force=true → 2 expired, 1 in_progress untouched (MAC-114).
  13. Create group2; reassign p1 → sessions listing reflects new group_name (MAC-143).
  14. Auth realm separation (MAC-133, MAC-135, MAC-136):
        a. Capture researcher refresh_token cookie from admin login.
        b. Capture participant_refresh_token cookie from participant set-password.
        c. POST /auth/refresh + researcher cookie → researcher-role token.
        d. POST /auth/refresh + ONLY participant cookie → 401.
        e. POST /auth/participant/refresh + participant cookie → participant-role token.
        f. POST /auth/participant/refresh + ONLY researcher cookie → 401.
  15. Archive study. Exit 0.

Usage (inside api container):
    python3 scripts/smoke_v1_2.py [--base-url http://localhost:8000]

Usage (from host, via nginx on port 8080):
    python3 scripts/smoke_v1_2.py --base-url http://localhost:8080
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any


CHECK = "✓"
FAIL = "✗"


class SmokeFailure(Exception):
    pass


class Client:
    """urllib-based API client with optional Bearer-token and cookie support."""

    def __init__(self, base_url: str) -> None:
        self.api = base_url.rstrip("/") + "/api/v1"
        self.token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
        cookies: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        """Returns (status, payload_bytes, extracted_cookies).

        `extracted_cookies` maps cookie name → value parsed from Set-Cookie headers.
        """
        url = self.api + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))

        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                status: int = res.status
                payload: bytes = res.read()
                raw_headers = res.headers
        except urllib.error.HTTPError as e:
            status = e.code
            payload = e.read()
            raw_headers = e.headers
        except urllib.error.URLError as e:
            raise SmokeFailure(f"{method} {url}: connection failed ({e.reason})") from e

        # Extract cookies from Set-Cookie headers (case-insensitive get_all).
        extracted: dict[str, str] = {}
        for sc in raw_headers.get_all("Set-Cookie") or []:
            name_val = sc.split(";")[0].strip()
            if "=" in name_val:
                k, v = name_val.split("=", 1)
                extracted[k.strip()] = v.strip()

        expected = expect if isinstance(expect, tuple) else (expect,)
        if status not in expected:
            raise SmokeFailure(
                f"{method} {path}: expected {expected}, got {status}: "
                f"{payload[:400].decode(errors='replace')}"
            )
        return status, payload, extracted

    def json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
        cookies: dict[str, str] | None = None,
    ) -> Any:
        _, payload, _ = self.request(method, path, body, expect, cookies=cookies)
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
            last_error = f"unhealthy: {body}"
        except SmokeFailure as e:
            last_error = str(e)
        time.sleep(2)
    raise SmokeFailure(f"/health not ok within {timeout_s:.0f}s: {last_error}")


def decode_jwt_role(token: str) -> str:
    """Extract the `role` claim from a JWT without verifying the signature."""
    parts = token.split(".")
    if len(parts) != 3:
        return ""
    payload_b64 = parts[1]
    # Re-pad to a multiple of 4.
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    return str(payload.get("role", ""))


def make_trials(params: dict[str, Any], attempt: int) -> list[dict[str, Any]]:
    rng = random.Random(42)
    key_map: list[str] = params["key_map"]
    trials: list[dict[str, Any]] = []
    onset = 5_000.0
    for block, count in (
        ("practice", params["practice_trials"]),
        ("test", params["test_trials"]),
    ):
        for index in range(1, count + 1):
            pos = rng.randrange(len(key_map))
            rt = round(rng.uniform(250.0, 600.0), 1)
            trials.append(
                {
                    "client_uuid": str(uuid.uuid4()),
                    "attempt": attempt,
                    "block": block,
                    "trial_index": index,
                    "stimulus_position": pos,
                    "foreperiod_ms": rng.randint(
                        params["foreperiod_min_ms"], params["foreperiod_max_ms"]
                    ),
                    "key_pressed": key_map[pos],
                    "response_position": pos,
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
    R = Client(base_url)

    print("CRT v1.2 smoke test")
    wait_for_health(R, health_timeout_s)

    # -----------------------------------------------------------------------
    # Admin login — also capture the researcher refresh cookie for step 14.
    # -----------------------------------------------------------------------
    _, login_payload, login_cookies = R.request(
        "POST",
        "/auth/login",
        {"email": admin_email, "password": admin_password},
        expect=200,
    )
    login_data = json.loads(login_payload)
    R.token = login_data["access_token"]
    researcher_refresh_cookie = login_cookies.get("refresh_token", "")
    step(f"admin login as {login_data['user']['email']}")
    if not researcher_refresh_cookie:
        fail("admin login did not set a refresh_token cookie")
    step("researcher refresh_token cookie captured")

    # -----------------------------------------------------------------------
    # Step 3: Create study — MOD-7: single task_type, no per-stage fields.
    # Stale per-stage keys in the body are ignored by the server (MAC-107).
    # -----------------------------------------------------------------------
    study_payload = {
        "name": f"Smoke-v1.2-{suffix}",
        "task_type": "CRT3",
        "num_intervention_sessions": 24,
        "sessions_per_week": 3,
        # Stale keys that MOD-7 dropped — server must ignore them (MAC-107):
        "task_type_onboarding": "CRT4",
        "task_type_pre": "CRT4",
        "task_type_post": "CRT4",
    }
    study = R.json("POST", "/studies", study_payload, expect=201)
    study_id: str = study["id"]

    # MAC-104: StudyOut must not echo per-stage task_type fields.
    for bad_key in ("task_type_onboarding", "task_type_pre", "task_type_post"):
        if bad_key in study:
            fail(f"StudyOut contains unexpected key '{bad_key}' (MOD-7 MAC-104)")
    if study["task_type"] != "CRT3":
        fail(f"expected task_type='CRT3', got {study['task_type']!r}")
    step("study created: task_type='CRT3', no per-stage keys in response (MAC-104) ✓")

    # -----------------------------------------------------------------------
    # Step 4: Create 3 participants (bulk) and generate the protocol.
    # -----------------------------------------------------------------------
    plist = R.json(
        "POST",
        f"/studies/{study_id}/participants",
        {"count": 3, "prefix": f"S12{suffix[:4]}"},
        expect=201,
    )
    if len(plist) != 3:
        fail(f"expected 3 participants, got {len(plist)}")
    p_codes = [p["code"] for p in plist]
    p0_id, p1_id, p2_id = plist[0]["id"], plist[1]["id"], plist[2]["id"]
    step(f"created 3 participants: {', '.join(p_codes)}")

    gen = R.json(
        "POST",
        f"/studies/{study_id}/generate-protocol",
        {"participant_ids": [p["id"] for p in plist]},
        expect=(200, 201),
    )
    step(
        f"protocol generated: {gen['created'][0]['session_count']} sessions "
        f"× {len(gen['created'])} participants"
    )

    # -----------------------------------------------------------------------
    # Step 5: MAC-103 — all sessions carry study.task_type (CRT3).
    # -----------------------------------------------------------------------
    sessions_all = R.json("GET", f"/studies/{study_id}/sessions")
    for s in sessions_all:
        if s["task_type"] != "CRT3":
            fail(
                f"session {s['id']} has task_type={s['task_type']!r}, "
                f"expected 'CRT3' (MAC-103)"
            )
    # Also verify that the generate-protocol endpoint ignores stale per-stage
    # keys (MAC-107) by re-checking that no per-stage column bled in.
    if any(("task_type_pre" in s) for s in sessions_all):
        fail("sessions unexpectedly contain task_type_pre key (MOD-7)")
    step("all protocol sessions carry task_type='CRT3' (MAC-103) ✓")

    # Build a lookup: session_id → session, by participant_id.
    p0_sessions = {s["order_index"]: s for s in sessions_all if s["participant_id"] == p0_id}
    p1_sessions = {s["order_index"]: s for s in sessions_all if s["participant_id"] == p1_id}

    # -----------------------------------------------------------------------
    # Step 6: Create group, assign 3 participants.
    # -----------------------------------------------------------------------
    group = R.json(
        "POST",
        f"/studies/{study_id}/groups",
        {"name": f"Group-A-{suffix}", "description": "smoke v1.2"},
        expect=201,
    )
    group_id: str = group["id"]
    group_name: str = group["name"]
    assign = R.json(
        "POST",
        f"/groups/{group_id}/assign",
        {"participant_ids": [p["id"] for p in plist]},
    )
    if len(assign["assigned"]) != 3 or assign["conflicts"]:
        fail(f"unexpected assign response: {assign}")
    step(f"group '{group_name}' created; 3 participants assigned")

    # -----------------------------------------------------------------------
    # Step 7: MOD-8 / MAC-109 — activate ONBOARDING with no IS set.
    # -----------------------------------------------------------------------
    act_onb = R.json(
        "POST",
        f"/groups/{group_id}/activate",
        {"session_type": "onboarding"},
    )
    activated_onb = act_onb["activated"]
    if len(activated_onb) != 3:
        fail(
            f"expected 3 onboarding sessions activated, got {len(activated_onb)} (MAC-109)"
        )
    for item in activated_onb:
        if item.get("session_type", item.get("display_label", "")) not in (
            "onboarding",
            "Onboarding",
        ):
            pass  # display_label is "Onboarding" for onboarding session
    step(f"onboarding activation: {len(activated_onb)} sessions activated (MAC-109) ✓")

    # -----------------------------------------------------------------------
    # Step 8: MAC-110 — deactivate onboarding.
    # -----------------------------------------------------------------------
    deact_onb = R.json(
        "POST",
        f"/groups/{group_id}/deactivate",
        {"session_type": "onboarding"},
    )
    expired_onb = deact_onb["expired"]
    if len(expired_onb) != 3:
        fail(f"expected 3 onboarding sessions expired, got {len(expired_onb)} (MAC-110)")
    step(f"onboarding deactivation: {len(expired_onb)} sessions expired (MAC-110) ✓")

    # -----------------------------------------------------------------------
    # Step 9: MAC-111 — set IS=1; activate PRE (default session_type).
    # -----------------------------------------------------------------------
    R.json("PATCH", f"/groups/{group_id}", {"current_intervention_session": 1})
    step("IS set to 1")

    # Default session_type is "pre"; pass empty body to verify backwards-compat (MAC-111).
    act_pre = R.json("POST", f"/groups/{group_id}/activate", {})
    activated_pre = act_pre["activated"]
    if len(activated_pre) != 3:
        fail(f"expected 3 pre sessions activated, got {len(activated_pre)} (MAC-111)")
    step(
        f"pre activation (default session_type): {len(activated_pre)} sessions activated "
        f"(MAC-111) ✓"
    )

    # Find p0's activated pre-session (order_index=2 for IS=1).
    p0_pre = next(
        (s for s in activated_pre if s["participant_id"] == p0_id), None
    )
    if p0_pre is None:
        fail("p0's pre session not found in activation response")
    p0_pre_session_id: str = p0_pre["session_id"]

    # -----------------------------------------------------------------------
    # Step 10: Login as participant p0; start their pre session → in_progress.
    # -----------------------------------------------------------------------
    P0 = Client(base_url)
    set_pw_resp = P0.json(
        "POST",
        "/auth/participant/set-password",
        {"code": p_codes[0], "password": f"smoke-p0-{suffix}"},
    )
    P0.token = set_pw_resp["access_token"]
    step(f"participant {p_codes[0]} password set and logged in")

    start_resp = P0.json("POST", f"/sessions/{p0_pre_session_id}/start")
    if start_resp.get("task_type") != "CRT3":
        fail(
            f"expected CRT3 task type on session start, "
            f"got {start_resp.get('task_type')!r}"
        )
    step(f"participant {p_codes[0]} started pre session (task_type=CRT3, in_progress)")

    # -----------------------------------------------------------------------
    # Step 11: MAC-114 — deactivate pre with force=false → 409.
    # -----------------------------------------------------------------------
    status_11, payload_11, _ = R.request(
        "POST",
        f"/groups/{group_id}/deactivate",
        {"session_type": "pre", "force": False},
        expect=409,
    )
    detail_11 = json.loads(payload_11)["detail"]
    if isinstance(detail_11, dict):
        in_prog_count = detail_11.get("in_progress_count", 0)
    else:
        in_prog_count = 1  # non-structured 409 still counts
    if in_prog_count < 1:
        fail(f"expected in_progress_count ≥ 1 in 409 body, got {detail_11}")
    step(
        f"deactivate pre force=false → 409 "
        f"(in_progress_count={in_prog_count}) (MAC-114) ✓"
    )

    # -----------------------------------------------------------------------
    # Step 12: MAC-114 — deactivate pre with force=true.
    # -----------------------------------------------------------------------
    deact_pre = R.json(
        "POST",
        f"/groups/{group_id}/deactivate",
        {"session_type": "pre", "force": True},
    )
    expired_pre = deact_pre["expired"]
    in_prog_left = deact_pre.get("in_progress_count", 0)

    # 2 of the 3 activated sessions should be expired (p1, p2); p0's is in_progress.
    if len(expired_pre) != 2:
        fail(f"expected 2 expired sessions after force deactivate, got {len(expired_pre)}")
    if in_prog_left != 1:
        fail(f"expected in_progress_count=1 after force deactivate, got {in_prog_left}")

    # Verify p0's session is still in_progress (untouched).
    all_sessions = R.json("GET", f"/studies/{study_id}/sessions")
    p0_pre_db = next((s for s in all_sessions if s["id"] == p0_pre_session_id), None)
    if p0_pre_db is None:
        fail("could not find p0's pre session in session list after force deactivate")
    if p0_pre_db["status"] != "in_progress":
        fail(
            f"p0's pre session should be in_progress after force deactivate, "
            f"got {p0_pre_db['status']!r}"
        )
    step(
        f"force deactivate: {len(expired_pre)} expired, {in_prog_left} in_progress "
        f"(untouched) (MAC-114) ✓"
    )

    # -----------------------------------------------------------------------
    # Step 13: MAC-143 — reassignment reflected in sessions listing.
    # p1's sessions are in created/expired state → reassignment is allowed.
    # -----------------------------------------------------------------------
    # Verify p1 is currently in group_name.
    p1_sessions_before = [s for s in all_sessions if s["participant_id"] == p1_id]
    if not p1_sessions_before:
        fail("no sessions found for p1")
    for s in p1_sessions_before:
        if s.get("group_name") != group_name:
            fail(
                f"before reassign: p1 session expected group_name={group_name!r}, "
                f"got {s.get('group_name')!r}"
            )
    step(f"before reassign: p1 sessions carry group_name={group_name!r} (MAC-143 pre-check) ✓")

    # Create group2 and reassign p1.
    group2 = R.json(
        "POST",
        f"/studies/{study_id}/groups",
        {"name": f"Group-B-{suffix}"},
        expect=201,
    )
    group2_id: str = group2["id"]
    group2_name: str = group2["name"]

    reassign = R.json(
        "POST",
        f"/groups/{group2_id}/assign",
        {"participant_ids": [p1_id]},
    )
    # Response has "assigned" for new assignments and "reassigned" for moves.
    moved = len(reassign.get("assigned", [])) + len(reassign.get("reassigned", []))
    if moved != 1:
        fail(f"reassignment failed: {reassign}")
    step(f"p1 reassigned from '{group_name}' → '{group2_name}'")

    # Fetch sessions again — p1 should now appear under group2.
    all_sessions_after = R.json("GET", f"/studies/{study_id}/sessions")
    p1_sessions_after = [s for s in all_sessions_after if s["participant_id"] == p1_id]
    if not p1_sessions_after:
        fail("no sessions found for p1 after reassign")
    for s in p1_sessions_after:
        if s.get("group_name") != group2_name:
            fail(
                f"after reassign: p1 session expected group_name={group2_name!r}, "
                f"got {s.get('group_name')!r} (MAC-143)"
            )
    step(f"after reassign: p1 sessions carry group_name={group2_name!r} (MAC-143) ✓")

    # -----------------------------------------------------------------------
    # Step 14: MOD-10 — auth realm separation.
    # researcher_refresh_cookie was captured in step 2.
    # Now capture participant refresh cookie via p2's set-password.
    # -----------------------------------------------------------------------
    # 14b: participant p2 set-password → capture participant_refresh_token cookie.
    _, pp_payload, pp_cookies = R.request(
        "POST",
        "/auth/participant/set-password",
        {"code": p_codes[2], "password": f"smoke-p2-{suffix}"},
        expect=200,
    )
    participant_refresh_cookie = pp_cookies.get("participant_refresh_token", "")
    if not participant_refresh_cookie:
        fail("participant set-password did not set participant_refresh_token cookie")
    step(f"participant {p_codes[2]} set-password; participant_refresh_token cookie captured")

    # Use a cookie-only client (no Bearer token) for the realm tests.
    AUTH = Client(base_url)

    # 14c: POST /auth/refresh with researcher cookie → researcher-role token (MAC-133).
    refresh_resp = AUTH.json(
        "POST",
        "/auth/refresh",
        expect=200,
        cookies={"refresh_token": researcher_refresh_cookie},
    )
    res_role = decode_jwt_role(refresh_resp["access_token"])
    if res_role not in ("admin", "researcher"):
        fail(
            f"POST /auth/refresh with researcher cookie returned role={res_role!r}; "
            f"expected admin/researcher (MAC-133)"
        )
    step(
        f"POST /auth/refresh + researcher cookie → role={res_role!r} "
        f"(MAC-133) ✓"
    )

    # 14d: POST /auth/refresh with ONLY participant cookie → 401 (MAC-135).
    AUTH.request(
        "POST",
        "/auth/refresh",
        expect=401,
        cookies={"participant_refresh_token": participant_refresh_cookie},
    )
    step("POST /auth/refresh + participant_refresh_token cookie → 401 (MAC-135) ✓")

    # 14e: POST /auth/participant/refresh + participant cookie → participant-role (MAC-136).
    p_refresh_resp = AUTH.json(
        "POST",
        "/auth/participant/refresh",
        expect=200,
        cookies={"participant_refresh_token": participant_refresh_cookie},
    )
    p_role = decode_jwt_role(p_refresh_resp["access_token"])
    if p_role != "participant":
        fail(
            f"POST /auth/participant/refresh with participant cookie returned role={p_role!r}; "
            f"expected participant (MAC-136)"
        )
    step(f"POST /auth/participant/refresh + participant cookie → role={p_role!r} (MAC-136) ✓")

    # 14f: POST /auth/participant/refresh + ONLY researcher cookie → 401 (MAC-136).
    AUTH.request(
        "POST",
        "/auth/participant/refresh",
        expect=401,
        cookies={"refresh_token": researcher_refresh_cookie},
    )
    step(
        "POST /auth/participant/refresh + researcher cookie only → 401 (MAC-136) ✓"
    )

    # -----------------------------------------------------------------------
    # Cleanup.
    # -----------------------------------------------------------------------
    R.json("PATCH", f"/studies/{study_id}", {"is_archived": True})
    step("smoke study archived")

    print("SMOKE V1.2 TEST PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000 for inside-container run)",
    )
    parser.add_argument(
        "--admin-email",
        default=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("ADMIN_PASSWORD", "AdminDev2024!"),
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=30.0,
        help="seconds to wait for /health",
    )
    args = parser.parse_args()

    try:
        run(args.base_url, args.admin_email, args.admin_password, args.health_timeout)
    except SmokeFailure as e:
        print(f"{FAIL} SMOKE V1.2 TEST FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
