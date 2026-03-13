"""
Phase 276 — Supabase Auth JWT Integration Contract Tests
=========================================================

Tests for the updated auth.py and new /auth/supabase-verify endpoint.

Groups:
  A — IHOUSE_DEV_MODE=true bypasses (4 tests)
  B — IHOUSE_JWT_SECRET absent + not dev mode → 503 (3 tests)
  C — Supabase Auth token accepted (aud=authenticated) (5 tests)
  D — Internal self-issued token still accepted (3 tests)
  E — POST /auth/supabase-verify endpoint (7 tests)
  F — decode_jwt_claims helper (3 tests)

Total: 25 tests
"""
from __future__ import annotations

import time
import os
import pytest
import jwt
from fastapi.testclient import TestClient

from api.auth import verify_jwt, decode_jwt_claims, _DEV_TENANT
from fastapi.security import HTTPAuthorizationCredentials

_SECRET = "phase276-test-secret-32bytes-long!!"
_ALGORITHM = "HS256"


def _make_creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _issue(payload: dict, secret: str = _SECRET) -> str:
    base = {"iat": int(time.time()), "exp": int(time.time()) + 3600}
    base.update(payload)
    return jwt.encode(base, secret, algorithm=_ALGORITHM)


def _supabase_token(sub: str = "uuid-abc123", email: str = "user@test.com") -> str:
    """Build a Supabase-style JWT."""
    return _issue({"sub": sub, "aud": "authenticated", "role": "authenticated", "email": email})


def _internal_token(tenant_id: str = "my-tenant") -> str:
    """Build an internal-style JWT (from /auth/token)."""
    return _issue({"sub": tenant_id})


# ===========================================================================
# Group A — IHOUSE_DEV_MODE=true bypasses
# ===========================================================================

class TestGroupADevMode:
    def test_a1_dev_mode_returns_dev_tenant(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
        monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)
        result = verify_jwt(None)
        assert result == _DEV_TENANT

    def test_a2_dev_mode_ignores_credentials(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
        creds = _make_creds("some-random-token")
        result = verify_jwt(creds)
        assert result == _DEV_TENANT

    def test_a3_dev_mode_false_does_not_bypass(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DEV_MODE", "false")
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _internal_token()
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "my-tenant"

    def test_a4_dev_mode_absent_does_not_bypass(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _internal_token()
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "my-tenant"


# ===========================================================================
# Group B — No secret, not dev mode → 503
# ===========================================================================

class TestGroupBNoSecret:
    def test_b1_no_secret_no_dev_mode_raises_503(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(None)
        assert exc_info.value.status_code == 503

    def test_b2_503_detail_contains_auth_not_configured(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(None)
        assert "AUTH_NOT_CONFIGURED" in exc_info.value.detail

    def test_b3_503_detail_mentions_dev_mode(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(None)
        assert "IHOUSE_DEV_MODE" in exc_info.value.detail


# ===========================================================================
# Group C — Supabase Auth token (aud=authenticated) accepted
# ===========================================================================

class TestGroupCSupabaseToken:
    def test_c1_supabase_token_accepted(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = _supabase_token(sub="user-uuid-001")
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "user-uuid-001"

    def test_c2_supabase_token_sub_returned(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = _supabase_token(sub="supabase-user-xyz")
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "supabase-user-xyz"

    def test_c3_token_with_role_authenticated_accepted(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        # role=authenticated but no aud — still valid
        token = _issue({"sub": "role-only-user", "role": "authenticated"})
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "role-only-user"

    def test_c4_wrong_secret_supabase_token_raises_403(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = jwt.encode(
            {"sub": "hacker", "aud": "authenticated", "exp": int(time.time()) + 3600},
            "wrong-secret", algorithm=_ALGORITHM
        )
        creds = _make_creds(token)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(creds)
        assert exc_info.value.status_code == 403

    def test_c5_expired_supabase_token_raises_403(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = jwt.encode(
            {"sub": "user", "aud": "authenticated", "exp": int(time.time()) - 1},
            _SECRET, algorithm=_ALGORITHM
        )
        creds = _make_creds(token)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(creds)
        assert exc_info.value.status_code == 403


# ===========================================================================
# Group D — Internal self-issued token still works
# ===========================================================================

class TestGroupDInternalToken:
    def test_d1_internal_token_accepted(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = _internal_token("my-internal-tenant")
        creds = _make_creds(token)
        result = verify_jwt(creds)
        assert result == "my-internal-tenant"

    def test_d2_internal_token_sub_returned(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = _internal_token("tenant-abcdef")
        creds = _make_creds(token)
        assert verify_jwt(creds) == "tenant-abcdef"

    def test_d3_internal_token_missing_sub_raises_403(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
        token = _issue({"data": "no-sub"})
        creds = _make_creds(token)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt(creds)
        assert exc_info.value.status_code == 403


# ===========================================================================
# Group E — POST /auth/supabase-verify endpoint
# ===========================================================================

class TestGroupESupabaseVerifyEndpoint:
    @pytest.fixture
    def client(self):
        from main import app
        return TestClient(app)

    def test_e1_valid_supabase_token_returns_200(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _supabase_token(sub="e1-user", email="e1@test.com")
        resp = client.post("/auth/supabase-verify", json={"token": token})
        assert resp.status_code == 200

    def test_e2_response_contains_valid_true(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _supabase_token(sub="e2-user")
        resp = client.post("/auth/supabase-verify", json={"token": token})
        assert resp.json()["data"]["valid"] is True

    def test_e3_response_token_type_supabase(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _supabase_token(sub="e3-user")
        resp = client.post("/auth/supabase-verify", json={"token": token})
        assert resp.json()["data"]["token_type"] == "supabase"

    def test_e4_internal_token_type_internal(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _internal_token("e4-tenant")
        resp = client.post("/auth/supabase-verify", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["data"]["token_type"] == "internal"

    def test_e5_invalid_token_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        resp = client.post("/auth/supabase-verify", json={"token": "not-a-valid-jwt"})
        assert resp.status_code == 403

    def test_e6_no_secret_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("IHOUSE_JWT_SECRET", raising=False)
        resp = client.post("/auth/supabase-verify", json={"token": "any"})
        assert resp.status_code == 503

    def test_e7_sub_in_response(self, client, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
        token = _supabase_token(sub="e7-uuid", email="e7@test.com")
        resp = client.post("/auth/supabase-verify", json={"token": token})
        data = resp.json()["data"]
        assert data["sub"] == "e7-uuid"


# ===========================================================================
# Group F — decode_jwt_claims helper
# ===========================================================================

class TestGroupFDecodeHelper:
    def test_f1_valid_token_returns_claims(self):
        token = _issue({"sub": "f1-user", "custom": "value"})
        claims = decode_jwt_claims(token, _SECRET)
        assert claims["sub"] == "f1-user"
        assert claims["custom"] == "value"

    def test_f2_invalid_token_returns_empty_dict(self):
        claims = decode_jwt_claims("bad-token", _SECRET)
        assert claims == {}

    def test_f3_wrong_secret_returns_empty_dict(self):
        token = _issue({"sub": "f3-user"})
        claims = decode_jwt_claims(token, "wrong-secret")
        assert claims == {}
