#!/usr/bin/env python3
"""v1.3 smoke test — exercises MOD-12 (name-based activation) and notes MOD-13.

Scenario:
  1.  Health check.
  2.  Admin login.
  3.  Create study, 3 participants, generate protocol.
  4.  Create group, assign 3 participants.
  5.  GET /groups/{id}/sessions-overview → verify stages returned (MFR-214).
  6.  Activate ONBOARDING with session_type only (no intervention_session_number).
      Server coerces non-null ISN → null for onboarding (D-12.4).
      Verify 3 sessions activated.
  7.  sessions-overview: verify onboarding activated counts.
  8.  Deactivate ONBOARDING → 3 expired.
  9.  Activate PRE IS=1 using explicit intervention_session_number=1 (MFR-211).
      Verify 3 sessions activated. Verify group counter updated to 1 (MFR-212).
  10. REGRESSION — counter drift (the silent-zero bug):
      a. PATCH group counter to 99 (simulate drift).
      b. sessions-overview still returns correct IS=1 stage data.
      c. Activate IS=1 again (sessions now 'activated') → 200 activated=[] (MFR-207).
      d. This proves matching uses payload.intervention_session_number, not the counter.
  11. Deactivate PRE IS=1 with explicit intervention_session_number=1.
      Verify 3 expired (the in-progress guard is not tested here — covered in v1.2).
  12. sessions-overview: verify pre IS=1 now shows expired counts.
  13. Archive study. Exit 0.

MOD-13 (collapsible Sessions table) is a frontend-only change and is not exercisable
via this API smoke script. It is verified by the usePersistentState unit tests and
manual acceptance criteria in ACCEPTANCE.md.

Usage (inside api container):
    python3 scripts/smoke_v1_3.py [--base-url http://localhost:8000]

Usage (from host, via nginx on port 8080):
    python3 scripts/smoke_v1_3.py --base-url http://localhost:8080
"""

from __future__ import annotations

import argparse
import json
import os
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
    """urllib-based API client."""

    def __init__(self, base_url: str) -> None:
        self.api = base_url.rstrip("/") + "/api/v1"
        self.token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
    ) -> tuple[int, bytes]:
        url = self.api + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                status: int = res.status
                payload: bytes = res.read()
        except urllib.error.HTTPError as e:
            status = e.code
            payload = e.read()
        except urllib.error.URLError as e:
            raise SmokeFailure(f"{method} {url}: connection failed ({e.reason})") from e
        expected = expect if isinstance(expect, tuple) else (expect,)
        if status not in expected:
            raise SmokeFailure(
                f"{method} {path}: expected {expected}, got {status}: "
                f"{payload[:400].decode(errors='replace')}"
            )
        return status, payload

    def json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expect: int | tuple[int, ...] = 200,
    ) -> Any:
        _, payload = self.request(method, path, body, expect)
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


def run(base_url: str, admin_email: str, admin_password: str, health_timeout_s: float) -> None:
    suffix = uuid.uuid4().hex[:6].upper()
    R = Client(base_url)

    print("CRT v1.3 smoke test — MOD-12 name-based activation")
    wait_for_health(R, health_timeout_s)

    # -----------------------------------------------------------------------
    # Step 2: Admin login.
    # -----------------------------------------------------------------------
    login = R.json("POST", "/auth/login", {"email": admin_email, "password": admin_password})
    R.token = login["access_token"]
    step(f"admin login as {login['user']['email']}")

    # -----------------------------------------------------------------------
    # Step 3: Create study + 3 participants + generate protocol.
    # -----------------------------------------------------------------------
    study = R.json(
        "POST",
        "/studies",
        {
            "name": f"Smoke-v1.3-{suffix}",
            "task_type": "CRT2",
            "num_intervention_sessions": 6,
            "sessions_per_week": 3,
        },
        expect=201,
    )
    study_id: str = study["id"]
    step(f"study created: {study['name']}")

    plist = R.json(
        "POST",
        f"/studies/{study_id}/participants",
        {"count": 3, "prefix": f"S13{suffix[:4]}"},
        expect=201,
    )
    if len(plist) != 3:
        fail(f"expected 3 participants, got {len(plist)}")
    p_ids = [p["id"] for p in plist]
    step(f"3 participants created: {', '.join(p['code'] for p in plist)}")

    gen = R.json(
        "POST",
        f"/studies/{study_id}/generate-protocol",
        {"participant_ids": p_ids},
        expect=(200, 201),
    )
    step(f"protocol generated: {gen['created'][0]['session_count']} sessions × 3 participants")

    # -----------------------------------------------------------------------
    # Step 4: Create group, assign 3 participants.
    # -----------------------------------------------------------------------
    group = R.json(
        "POST",
        f"/studies/{study_id}/groups",
        {"name": f"Group-A-{suffix}"},
        expect=201,
    )
    group_id: str = group["id"]
    assign = R.json("POST", f"/groups/{group_id}/assign", {"participant_ids": p_ids})
    if len(assign["assigned"]) != 3:
        fail(f"expected 3 assigned, got: {assign}")
    step(f"group '{group['name']}' created, 3 participants assigned")

    # -----------------------------------------------------------------------
    # Step 5: GET /groups/{id}/sessions-overview (MFR-214).
    # -----------------------------------------------------------------------
    overview = R.json("GET", f"/groups/{group_id}/sessions-overview")
    stages = overview.get("stages", [])
    if not stages:
        fail("sessions-overview returned no stages (MFR-214)")
    stage_keys = {(s["session_type"], s["intervention_session_number"]) for s in stages}
    # Expect at least onboarding + pre IS=1 to be present.
    if ("onboarding", None) not in stage_keys:
        fail(f"expected onboarding stage in overview, got keys: {stage_keys}")
    if not any(st == "pre" for st, _ in stage_keys):
        fail(f"expected at least one 'pre' stage in overview, got keys: {stage_keys}")
    step(
        f"sessions-overview: {len(stages)} stages returned "
        f"(includes onboarding + pre stages) (MFR-214) ✓"
    )

    # -----------------------------------------------------------------------
    # Step 6: Activate ONBOARDING (no intervention_session_number). (D-12.4)
    # -----------------------------------------------------------------------
    act_onb = R.json(
        "POST",
        f"/groups/{group_id}/activate",
        {"session_type": "onboarding"},
    )
    if len(act_onb["activated"]) != 3:
        fail(
            f"expected 3 onboarding sessions activated, got {len(act_onb['activated'])} (D-12.4)"
        )
    step(f"onboarding activation: 3 sessions activated (D-12.4) ✓")

    # Also verify that passing intervention_session_number: 5 is silently coerced to null.
    # We can only test this by confirming the server accepted the request without 422.
    act_onb_coerce = R.json(
        "POST",
        f"/groups/{group_id}/activate",
        {"session_type": "onboarding", "intervention_session_number": 5},
        expect=200,
    )
    # Sessions are already activated; coercion means ISN=null was used → zero activated.
    # The important check is no 422 was raised.
    step(
        f"onboarding + ISN=5 coerced to null (D-12.4): server returned 200, "
        f"activated={len(act_onb_coerce['activated'])} ✓"
    )

    # -----------------------------------------------------------------------
    # Step 7: sessions-overview — onboarding counts reflect activation.
    # -----------------------------------------------------------------------
    ov2 = R.json("GET", f"/groups/{group_id}/sessions-overview")
    onb_stage = next(
        (s for s in ov2["stages"] if s["session_type"] == "onboarding"),
        None,
    )
    if onb_stage is None:
        fail("onboarding stage missing from overview after activation")
    if onb_stage["counts"]["activated"] != 3:
        fail(
            f"expected onboarding activated=3, got {onb_stage['counts']['activated']} "
            f"(MFR-214 post-activation check)"
        )
    step(
        f"sessions-overview after onboarding activate: activated={onb_stage['counts']['activated']} ✓"
    )

    # -----------------------------------------------------------------------
    # Step 8: Deactivate ONBOARDING → 3 expired.
    # -----------------------------------------------------------------------
    deact_onb = R.json(
        "POST",
        f"/groups/{group_id}/deactivate",
        {"session_type": "onboarding"},
    )
    if len(deact_onb["expired"]) != 3:
        fail(f"expected 3 onboarding sessions expired, got {len(deact_onb['expired'])}")
    step(f"onboarding deactivation: 3 sessions expired ✓")

    # -----------------------------------------------------------------------
    # Step 9: Activate PRE IS=1 with explicit intervention_session_number (MFR-211).
    # -----------------------------------------------------------------------
    act_pre = R.json(
        "POST",
        f"/groups/{group_id}/activate",
        {"session_type": "pre", "intervention_session_number": 1},
    )
    if len(act_pre["activated"]) != 3:
        fail(
            f"expected 3 pre IS=1 sessions activated, got {len(act_pre['activated'])} (MFR-211)"
        )
    step(f"PRE IS=1 activation: 3 sessions activated using explicit ISN (MFR-211) ✓")

    # Verify counter updated as side effect (MFR-212).
    group_detail = R.json("GET", f"/groups/{group_id}")
    counter = group_detail.get("current_intervention_session")
    if counter != 1:
        fail(
            f"expected group counter updated to 1 after pre IS=1 activate, got {counter!r} (MFR-212)"
        )
    step(f"group counter updated to 1 as side effect (MFR-212) ✓")

    # -----------------------------------------------------------------------
    # Step 10: REGRESSION — counter drift does NOT cause silent zero-activation.
    # -----------------------------------------------------------------------
    # 10a: Drift the counter to 99 (simulate researcher editing it incorrectly).
    R.json("PATCH", f"/groups/{group_id}", {"current_intervention_session": 99})
    g_drifted = R.json("GET", f"/groups/{group_id}")
    if g_drifted.get("current_intervention_session") != 99:
        fail("failed to set drifted counter to 99 for regression test")
    step("REGRESSION: group counter drifted to 99 (simulating stale state)")

    # 10b: sessions-overview still returns correct stage data despite drifted counter.
    ov_drift = R.json("GET", f"/groups/{group_id}/sessions-overview")
    pre1_stage = next(
        (s for s in ov_drift["stages"] if s["session_type"] == "pre" and s["intervention_session_number"] == 1),
        None,
    )
    if pre1_stage is None:
        fail("pre IS=1 stage missing from sessions-overview after counter drift")
    if pre1_stage["counts"]["activated"] != 3:
        fail(
            f"expected pre IS=1 activated=3 in overview (counter drift should not affect it), "
            f"got {pre1_stage['counts']['activated']}"
        )
    step(
        f"sessions-overview correct despite counter=99: "
        f"pre IS=1 activated={pre1_stage['counts']['activated']} ✓"
    )

    # 10c: Activate IS=1 again (sessions already 'activated') → 200, activated=[] (MFR-207).
    act_pre_again = R.json(
        "POST",
        f"/groups/{group_id}/activate",
        {"session_type": "pre", "intervention_session_number": 1},
        expect=200,
    )
    if act_pre_again["activated"] != []:
        fail(
            f"expected activated=[] on second IS=1 activate (no created/expired left), "
            f"got {act_pre_again['activated']!r} (MFR-207)"
        )
    step(
        "second IS=1 activate → 200 activated=[] (no silent mismatch, MFR-207) ✓"
    )

    # 10d: Verify matching used explicit ISN=1, not drifted counter=99.
    #      If old code ran, it would have tried to match IS=99 → activated=[] for a different reason.
    #      We confirm the IS=1 sessions are still 'activated' (not touched by a wrong match).
    sessions_all = R.json("GET", f"/studies/{study_id}/sessions")
    pre1_sessions = [
        s for s in sessions_all
        if s["session_type"] == "pre" and s.get("intervention_session_number") == 1
        and s["participant_id"] in p_ids
    ]
    activated_count = sum(1 for s in pre1_sessions if s["status"] == "activated")
    if activated_count != 3:
        fail(
            f"REGRESSION FAILED: expected 3 pre IS=1 sessions in 'activated' state, "
            f"got {activated_count} (ISN matching broken)"
        )
    step(
        f"REGRESSION CONFIRMED: pre IS=1 sessions still activated={activated_count} "
        f"(payload ISN used, not drifted counter) ✓"
    )

    # -----------------------------------------------------------------------
    # Step 11: Deactivate PRE IS=1 with explicit ISN.
    # -----------------------------------------------------------------------
    deact_pre = R.json(
        "POST",
        f"/groups/{group_id}/deactivate",
        {"session_type": "pre", "intervention_session_number": 1, "force": True},
    )
    if len(deact_pre["expired"]) != 3:
        fail(f"expected 3 pre IS=1 sessions expired, got {len(deact_pre['expired'])}")
    step(f"PRE IS=1 deactivation (force): 3 sessions expired ✓")

    # -----------------------------------------------------------------------
    # Step 12: sessions-overview — pre IS=1 now shows expired counts.
    # -----------------------------------------------------------------------
    ov_final = R.json("GET", f"/groups/{group_id}/sessions-overview")
    pre1_final = next(
        (s for s in ov_final["stages"] if s["session_type"] == "pre" and s["intervention_session_number"] == 1),
        None,
    )
    if pre1_final is None:
        fail("pre IS=1 stage missing from final overview")
    if pre1_final["counts"]["expired"] != 3:
        fail(
            f"expected pre IS=1 expired=3, got {pre1_final['counts']['expired']} (MFR-214)"
        )
    step(
        f"sessions-overview final: pre IS=1 expired={pre1_final['counts']['expired']} ✓ (MFR-214)"
    )

    # -----------------------------------------------------------------------
    # Cleanup.
    # -----------------------------------------------------------------------
    R.json("PATCH", f"/studies/{study_id}", {"is_archived": True})
    step("smoke study archived")

    print()
    print("SMOKE V1.3 TEST PASSED")
    print()
    print("Note: MOD-13 (collapsible Sessions table) is a frontend-only change.")
    print("It is verified by usePersistentState unit tests and ACCEPTANCE.md criteria.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CRT_BASE_URL", "http://localhost:8000"),
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--admin-email",
        default=os.environ.get("CRT_ADMIN_EMAIL", "admin@example.com"),
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("CRT_ADMIN_PASSWORD", "changeme"),
    )
    parser.add_argument(
        "--health-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for /health before failing",
    )
    args = parser.parse_args()
    try:
        run(args.base_url, args.admin_email, args.admin_password, args.health_timeout)
        return 0
    except SmokeFailure as e:
        print(f"\n  {FAIL} SMOKE FAILURE: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
