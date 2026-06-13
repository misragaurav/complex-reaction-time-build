#!/usr/bin/env python3
"""End-to-end smoke test for the CRT web application.

Runs the full happy path against a live stack (default: the docker compose
stack at http://localhost:8080) using only the Python standard library:

  health -> admin login -> create study -> demographic field -> participant
  -> assign session -> participant set-password -> start -> demographics
  -> upload practice+test trials -> complete -> summary -> study export ZIP

Usage:
    python scripts/smoke.py [--base-url http://localhost:8080] \
        [--admin-email admin@example.com] [--admin-password change-me-now-please]

Admin credentials default to $ADMIN_EMAIL / $ADMIN_PASSWORD, falling back to
the .env.example values. Exits 0 on success, 1 on the first failure.
"""

from __future__ import annotations

import argparse
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
                f"{method} {path}: expected {expected}, got {status}: {payload[:300].decode(errors='replace')}"
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
                    "foreperiod_ms": rng.randint(params["foreperiod_min_ms"], params["foreperiod_max_ms"]),
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
    researcher = Client(base_url)

    print("CRT smoke test")
    wait_for_health(researcher, health_timeout_s)

    # --- researcher path ---------------------------------------------------
    login = researcher.json("POST", "/auth/login", {"email": admin_email, "password": admin_password})
    researcher.token = login["access_token"]
    step(f"admin login as {login['user']['email']} (role {login['user']['role']})")

    study = researcher.json(
        "POST",
        "/studies",
        {"name": f"Smoke {suffix}", "description": "smoke-test study", "task_type": "CRT4"},
        expect=201,
    )
    study_id = study["id"]
    if study["params"]["test_trials"] != 20 or study["params"]["practice_trials"] != 3:
        raise SmokeFailure(f"unexpected default params: {study['params']}")
    step(f"study created ({study['name']}) with §5.4 defaults")

    field = researcher.json(
        "POST",
        f"/studies/{study_id}/demographic-fields",
        {
            "label": "Handedness",
            "field_type": "single_choice",
            "options": ["Left", "Right", "Ambidextrous"],
            "required": True,
            "frequency": "once",
        },
        expect=201,
    )
    step(f"demographic field created ({field['label']})")

    created = researcher.json(
        "POST", f"/studies/{study_id}/participants", {"count": 1, "prefix": "SMOKE"}, expect=201
    )
    participant = created[0]
    code = participant["code"]
    step(f"participant created ({code})")

    sessions = researcher.json(
        "POST",
        f"/studies/{study_id}/sessions",
        {"participant_ids": [participant["id"]], "count": 1},
        expect=201,
    )
    session_id = sessions[0]["id"]
    step(f"session assigned (order {sessions[0]['order_index']})")

    # --- participant path ----------------------------------------------------
    p = Client(base_url)
    check = p.json("POST", "/auth/participant/check", {"code": code})
    if check["password_set"] is not False:
        raise SmokeFailure(f"fresh code reports password_set={check['password_set']}")
    plogin = p.json("POST", "/auth/participant/set-password", {"code": code, "password": "smoke-pass-1"})
    p.token = plogin["access_token"]
    step("participant claimed code and logged in")

    mine = p.json("GET", "/me/sessions")
    if len(mine) != 1 or mine[0]["locked"]:
        raise SmokeFailure(f"unexpected /me/sessions: {mine}")

    start = p.json("POST", f"/sessions/{session_id}/start")
    params = start["params"]
    due = start["demographics_due"]
    if len(due) != 1:
        raise SmokeFailure(f"expected 1 demographic field due, got {len(due)}")
    step(f"session started (attempt {start['attempt']}, {params['task_type']})")

    p.json(
        "POST",
        f"/sessions/{session_id}/demographics",
        {"answers": [{"field_id": due[0]["id"], "value": "Right"}]},
        expect=204,
    )
    step("demographics submitted")

    p.json(
        "POST",
        f"/sessions/{session_id}/client-env",
        {
            "user_agent": "smoke.py",
            "screen_width": 1920,
            "screen_height": 1080,
            "device_pixel_ratio": 1.0,
            "refresh_rate_hz": 60.0,
            "timezone": "UTC",
        },
        expect=204,
    )

    trials = make_trials(params, start["attempt"])
    accepted = 0
    for i in range(0, len(trials), 25):
        batch = trials[i : i + 25]
        res = p.json("POST", f"/sessions/{session_id}/trials", {"trials": batch})
        accepted += res["accepted"]
    if accepted != len(trials):
        raise SmokeFailure(f"uploaded {len(trials)} trials but server accepted {accepted}")
    # Idempotency: re-sending the first batch must not create duplicates.
    p.json("POST", f"/sessions/{session_id}/trials", {"trials": trials[:5]})
    step(f"{accepted} trials uploaded (idempotent re-send ok)")

    p.json("POST", f"/sessions/{session_id}/complete", expect=204)
    step("session completed")

    # --- researcher verification ---------------------------------------------
    summary = researcher.json("GET", f"/sessions/{session_id}/summary")
    if summary["n_trials"] != params["test_trials"] or summary["accuracy_pct"] != 100.0:
        raise SmokeFailure(f"unexpected summary: n_trials={summary['n_trials']}, accuracy={summary['accuracy_pct']}")
    if summary["trimmed"]["mean_rt_ms"] is None:
        raise SmokeFailure("trimmed mean RT missing from summary")
    step(
        f"summary: n={summary['n_trials']}, accuracy={summary['accuracy_pct']}%, "
        f"trimmed mean RT={summary['trimmed']['mean_rt_ms']} ms"
    )

    _, zip_bytes, headers = researcher.request("GET", f"/studies/{study_id}/export.zip")
    names = set(zipfile.ZipFile(io.BytesIO(zip_bytes)).namelist())
    expected_files = {"trials.csv", "sessions_summary.csv", "participants_summary.csv", "demographics.csv"}
    if names != expected_files:
        raise SmokeFailure(f"export ZIP contains {sorted(names)}, expected {sorted(expected_files)}")
    step(f"study export ZIP ok ({headers.get('content-disposition', 'no filename')})")

    # Clean up: archive the smoke study so it does not clutter the default list.
    researcher.json("PATCH", f"/studies/{study_id}", {"is_archived": True})
    step("smoke study archived")

    print("SMOKE TEST PASSED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("SMOKE_BASE_URL", "http://localhost:8080"))
    parser.add_argument("--admin-email", default=os.environ.get("ADMIN_EMAIL", "admin@example.com"))
    parser.add_argument("--admin-password", default=os.environ.get("ADMIN_PASSWORD", "change-me-now-please"))
    parser.add_argument("--health-timeout", type=float, default=120.0, help="seconds to wait for /health")
    args = parser.parse_args()

    try:
        run(args.base_url, args.admin_email, args.admin_password, args.health_timeout)
    except SmokeFailure as e:
        print(f"SMOKE TEST FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
