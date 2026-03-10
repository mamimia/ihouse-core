"""
Phase 186 — Contract Tests: Auth Logout

Tests for POST /auth/logout in src/api/auth_router.py.

Groups:
    A — happy path: 200, correct body, Set-Cookie clears token
    B — no auth required: works without Bearer token, with wrong token, with expired token
    C — existing POST /auth/token still works (no regression)
    D — CORS / header correctness
"""
from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    # Save originals to restore after module tests complete — prevents leaking
    # the JWT secret into subsequent test files in the full suite.
    _orig_secret = os.environ.get("IHOUSE_JWT_SECRET")
    _orig_pw = os.environ.get("IHOUSE_DEV_PASSWORD")
    os.environ["IHOUSE_JWT_SECRET"] = os.environ.get("IHOUSE_JWT_SECRET", "test-logout-secret-min32chars!!")
    os.environ["IHOUSE_DEV_PASSWORD"] = os.environ.get("IHOUSE_DEV_PASSWORD", "dev")
    from main import app
    yield TestClient(app, raise_server_exceptions=True)
    # Restore originals
    if _orig_secret is None:
        os.environ.pop("IHOUSE_JWT_SECRET", None)
    else:
        os.environ["IHOUSE_JWT_SECRET"] = _orig_secret
    if _orig_pw is None:
        os.environ.pop("IHOUSE_DEV_PASSWORD", None)
    else:
        os.environ["IHOUSE_DEV_PASSWORD"] = _orig_pw


@pytest.fixture(scope="module")
def valid_token():
    secret = os.environ.get("IHOUSE_JWT_SECRET", "test-logout-secret-min32chars!!")
    payload = {"sub": "t-1", "iat": int(time.time()), "exp": int(time.time()) + 86400}
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Group A — happy path
# ---------------------------------------------------------------------------

class TestGroupALogoutHappyPath:

    def test_a1_returns_200(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 200

    def test_a2_body_contains_message(self, client):
        resp = client.post("/auth/logout")
        body = resp.json()
        assert "message" in body
        assert "logged out" in body["message"].lower()

    def test_a3_set_cookie_clears_ihouse_token(self, client):
        resp = client.post("/auth/logout")
        cookie_header = resp.headers.get("set-cookie", "")
        assert "ihouse_token" in cookie_header
        # Max-Age=0 means expire immediately (delete)
        assert "max-age=0" in cookie_header.lower() or "max-age=0" in cookie_header

    def test_a4_set_cookie_path_is_root(self, client):
        resp = client.post("/auth/logout")
        cookie_header = resp.headers.get("set-cookie", "").lower()
        assert "path=/" in cookie_header

    def test_a5_response_is_json(self, client):
        resp = client.post("/auth/logout")
        content_type = resp.headers.get("content-type", "")
        assert "application/json" in content_type


# ---------------------------------------------------------------------------
# Group B — no auth required
# ---------------------------------------------------------------------------

class TestGroupBNoAuthRequired:

    def test_b1_works_without_any_auth_header(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 200

    def test_b2_works_with_invalid_bearer_token(self, client):
        resp = client.post("/auth/logout", headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code == 200

    def test_b3_works_with_expired_bearer_token(self, client):
        secret = os.environ.get("IHOUSE_JWT_SECRET", "test-logout-secret-min32chars!!")
        expired_payload = {"sub": "t-1", "iat": 0, "exp": 1}   # expired in the past
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
        resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 200

    def test_b4_works_with_no_body(self, client):
        resp = client.post("/auth/logout", content=b"")
        assert resp.status_code == 200

    def test_b5_idempotent_second_call(self, client):
        r1 = client.post("/auth/logout")
        r2 = client.post("/auth/logout")
        assert r1.status_code == 200
        assert r2.status_code == 200


# ---------------------------------------------------------------------------
# Group C — no regression on POST /auth/token
# ---------------------------------------------------------------------------

class TestGroupCTokenNoRegression:

    def test_c1_token_endpoint_still_200(self, client):
        resp = client.post("/auth/token", json={"tenant_id": "t-1", "secret": "dev"})
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_c2_token_endpoint_401_on_wrong_secret(self, client):
        resp = client.post("/auth/token", json={"tenant_id": "t-1", "secret": "wrong"})
        assert resp.status_code == 401

    def test_c3_logout_does_not_affect_token_issuance(self, client):
        client.post("/auth/logout")   # logout first
        # Can still get a new token immediately after
        resp = client.post("/auth/token", json={"tenant_id": "t-1", "secret": "dev"})
        assert resp.status_code == 200
        assert "token" in resp.json()


# ---------------------------------------------------------------------------
# Group D — endpoint registration
# ---------------------------------------------------------------------------

class TestGroupDEndpointRegistration:

    def test_d1_route_exists_in_openapi(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        assert "/auth/logout" in paths

    def test_d2_route_accepts_post(self, client):
        resp = client.get("/openapi.json")
        methods = resp.json()["paths"].get("/auth/logout", {})
        assert "post" in methods

    def test_d3_logout_in_auth_tag(self, client):
        resp = client.get("/openapi.json")
        logout_spec = resp.json()["paths"].get("/auth/logout", {}).get("post", {})
        assert "auth" in logout_spec.get("tags", [])
