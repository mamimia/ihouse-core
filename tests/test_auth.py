"""
Contract tests for Phase 61 — JWT Auth (src/api/auth.py).

Uses verify_jwt() directly (not via HTTP) for unit-level contract testing.
HTTP-level JWT tests are covered via test_webhook_endpoint.py (dev-mode).

Coverage:
    1.  Valid JWT → returns tenant_id from `sub` claim
    2.  Missing credentials (None) + secret set → 403
    3.  Malformed token (not 3 parts) → 403
    4.  Wrong secret → 403
    5.  Expired token → 403
    6.  Dev mode (no secret) → returns "dev-tenant"
    7.  Token with no `sub` claim → 403
    8.  Empty `sub` claim → 403
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import verify_jwt, _DEV_TENANT, _ALGORITHM, _ENV_VAR

_SECRET = "test-jwt-secret-for-phase-61"


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_token(
    sub: str | None = "tenant-abc",
    secret: str = _SECRET,
    exp_delta: timedelta | None = timedelta(hours=1),
    algorithm: str = _ALGORITHM,
    extra_claims: dict | None = None,
) -> str:
    payload: dict = {}
    if sub is not None:
        payload["sub"] = sub
    if exp_delta is not None:
        payload["exp"] = datetime.now(timezone.utc) + exp_delta
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# Test 1: Valid JWT → returns tenant_id (sub claim)
# ---------------------------------------------------------------------------

def test_valid_jwt_returns_tenant_id(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
    token = _make_token(sub="tenant-from-jwt")
    creds = _make_credentials(token)
    result = verify_jwt(creds)
    assert result == "tenant-from-jwt"


# ---------------------------------------------------------------------------
# Test 2: Missing credentials (None) + secret set → 403
# ---------------------------------------------------------------------------

def test_missing_credentials_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    monkeypatch.delenv("IHOUSE_DEV_MODE", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(None)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test 3: Malformed token (not a valid JWT) → 403
# ---------------------------------------------------------------------------

def test_malformed_token_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    creds = _make_credentials("not.a.valid.jwt.token.here")
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(creds)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test 4: Wrong secret → 403
# ---------------------------------------------------------------------------

def test_wrong_secret_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, "correct-secret")
    token = _make_token(secret="wrong-secret")
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(creds)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test 5: Expired token → 403
# ---------------------------------------------------------------------------

def test_expired_token_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    token = _make_token(exp_delta=timedelta(seconds=-1))
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(creds)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test 6: Dev mode (no secret set) → returns "dev-tenant"
# ---------------------------------------------------------------------------

def test_dev_mode_returns_dev_tenant(monkeypatch):
    monkeypatch.delenv(_ENV_VAR, raising=False)
    # Phase 276: dev mode now requires explicit IHOUSE_DEV_MODE=true
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")
    # In dev mode, credentials are not checked at all
    result = verify_jwt(None)
    assert result == _DEV_TENANT


# ---------------------------------------------------------------------------
# Test 7: Token with no `sub` claim → 403
# ---------------------------------------------------------------------------

def test_no_sub_claim_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    token = _make_token(sub=None)  # no sub claim
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(creds)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Test 8: Empty `sub` claim → 403
# ---------------------------------------------------------------------------

def test_empty_sub_claim_raises_403(monkeypatch):
    monkeypatch.setenv(_ENV_VAR, _SECRET)
    token = _make_token(sub="   ")  # whitespace-only
    creds = _make_credentials(token)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(creds)
    assert exc_info.value.status_code == 403
