"""MOD-10 regression tests: auth realm separation (MAC-133–140).

Verifies that a participant login does not clobber the researcher refresh
cookie and that each realm's refresh endpoint accepts only its own token.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.security import PARTICIPANT_REFRESH_COOKIE_NAME, REFRESH_COOKIE_NAME, create_refresh_token, decode_token
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


# ---------------------------------------------------------------------------
# MAC-133 / regression: participant login must not invalidate researcher refresh
# ---------------------------------------------------------------------------

def test_participant_login_does_not_clobber_researcher_refresh_cookie(
    client: TestClient,
    researcher_headers: dict[str, str],
    participant: dict[str, Any],
) -> None:
    """After a participant logs in, the researcher's /auth/refresh must still work."""
    # Researcher is already logged in via researcher_headers fixture, which
    # stored a refresh_token cookie in the TestClient's cookie jar.
    pre_refresh = client.post("/api/v1/auth/refresh")
    assert pre_refresh.status_code == 200, pre_refresh.text
    researcher_role = decode_token(pre_refresh.json()["access_token"])["role"]
    assert researcher_role in ("admin", "researcher")

    # Participant sets a password in the same "browser" (shared cookie jar).
    # Before the fix this used the same cookie name and would overwrite the
    # researcher's refresh token.
    p_resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "realm-test-pw"},
    )
    assert p_resp.status_code == 200, p_resp.text

    # Researcher refresh must still succeed — this is the bug this test covers.
    post_refresh = client.post("/api/v1/auth/refresh")
    assert post_refresh.status_code == 200, (
        f"Researcher refresh failed after participant login: {post_refresh.text}. "
        "Bug reproduced — participant cookie must have overwritten researcher cookie."
    )
    token = post_refresh.json()["access_token"]
    payload = decode_token(token)
    assert payload["role"] in ("admin", "researcher"), (
        f"Expected researcher role; got {payload['role']!r}. "
        "Researcher refresh endpoint returned a participant-role token."
    )


def test_participant_refresh_endpoint_returns_participant_token(
    client: TestClient,
    participant: dict[str, Any],
) -> None:
    """POST /auth/participant/refresh returns a participant-role access token."""
    p_resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "realm-test-pw"},
    )
    assert p_resp.status_code == 200, p_resp.text

    ref = client.post("/api/v1/auth/participant/refresh")
    assert ref.status_code == 200, ref.text
    payload = decode_token(ref.json()["access_token"])
    assert payload["role"] == "participant"


def test_realms_refresh_independently(
    client: TestClient,
    researcher_headers: dict[str, str],
    participant: dict[str, Any],
) -> None:
    """Both realms can refresh independently; cookies do not interfere."""
    # Participant logs in.
    p_resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "realm-test-pw"},
    )
    assert p_resp.status_code == 200, p_resp.text

    # Researcher realm refresh still works.
    r_ref = client.post("/api/v1/auth/refresh")
    assert r_ref.status_code == 200, r_ref.text
    r_role = decode_token(r_ref.json()["access_token"])["role"]
    assert r_role in ("admin", "researcher")

    # Participant realm refresh works independently.
    p_ref = client.post("/api/v1/auth/participant/refresh")
    assert p_ref.status_code == 200, p_ref.text
    p_role = decode_token(p_ref.json()["access_token"])["role"]
    assert p_role == "participant"


# ---------------------------------------------------------------------------
# MAC-134: defense-in-depth — wrong token role on wrong endpoint
# ---------------------------------------------------------------------------

def test_researcher_endpoint_rejects_participant_token_in_cookie(
    client: TestClient,
    participant: dict[str, Any],
) -> None:
    """POST /auth/refresh with a participant-role refresh token must return 403.

    We place a real participant refresh token in the researcher cookie slot to
    simulate the old bug (where a participant login would overwrite the
    researcher cookie).
    """
    # Participant logs in — sets 'participant_refresh_token' in the cookie jar.
    p_resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "realm-guard-pw"},
    )
    assert p_resp.status_code == 200, p_resp.text

    # Read the real participant token from the jar and inject it under the
    # researcher cookie name.
    pt_value = client.cookies.get(PARTICIPANT_REFRESH_COOKIE_NAME)
    assert pt_value is not None, "Participant refresh cookie was not set after login"
    client.cookies.set(REFRESH_COOKIE_NAME, pt_value)

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 403, (
        f"Expected 403 but got {resp.status_code}. "
        "Researcher endpoint must reject participant-role tokens."
    )


def test_participant_endpoint_rejects_researcher_token_in_cookie(
    client: TestClient,
) -> None:
    """POST /auth/participant/refresh with a researcher-role token must return 403."""
    # Researcher logs in — sets 'refresh_token' in the cookie jar.
    r_resp = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r_resp.status_code == 200, r_resp.text

    # Read the researcher token and inject it under the participant cookie name.
    rt_value = client.cookies.get(REFRESH_COOKIE_NAME)
    assert rt_value is not None, "Researcher refresh cookie was not set after login"
    client.cookies.set(PARTICIPANT_REFRESH_COOKIE_NAME, rt_value)

    resp = client.post("/api/v1/auth/participant/refresh")
    assert resp.status_code == 403, (
        f"Expected 403 but got {resp.status_code}. "
        "Participant endpoint must reject researcher-role tokens."
    )


# ---------------------------------------------------------------------------
# MAC-135: participant refresh without cookie returns 401
# ---------------------------------------------------------------------------

def test_participant_refresh_without_cookie_returns_401(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/participant/refresh")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# MAC-136: researcher cookie name must not equal participant cookie name
# ---------------------------------------------------------------------------

def test_cookie_names_are_distinct() -> None:
    assert REFRESH_COOKIE_NAME != PARTICIPANT_REFRESH_COOKIE_NAME


# ---------------------------------------------------------------------------
# MAC-137: set-password response sets participant cookie, not researcher cookie
# ---------------------------------------------------------------------------

def test_participant_set_password_sets_participant_cookie_not_researcher_cookie(
    client: TestClient,
    participant: dict[str, Any],
) -> None:
    resp = client.post(
        "/api/v1/auth/participant/set-password",
        json={"code": participant["code"], "password": "cookie-name-test-pw"},
    )
    assert resp.status_code == 200, resp.text
    set_cookie = resp.headers.get("set-cookie", "")
    # The Set-Cookie header starts with the cookie name followed immediately by "=".
    assert set_cookie.startswith(PARTICIPANT_REFRESH_COOKIE_NAME + "="), (
        f"Expected Set-Cookie to start with {PARTICIPANT_REFRESH_COOKIE_NAME!r}= "
        f"but got: {set_cookie!r}"
    )
    # Must NOT start with the researcher cookie name (would indicate wrong cookie was set).
    assert not set_cookie.startswith(REFRESH_COOKIE_NAME + "="), (
        f"Participant set-password must not set {REFRESH_COOKIE_NAME!r} cookie"
    )


def test_researcher_login_sets_researcher_cookie_not_participant_cookie(
    client: TestClient,
) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    set_cookie = resp.headers.get("set-cookie", "")
    assert REFRESH_COOKIE_NAME + "=" in set_cookie
    assert PARTICIPANT_REFRESH_COOKIE_NAME + "=" not in set_cookie
