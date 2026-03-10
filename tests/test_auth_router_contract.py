"""
Phase 179 — Contract tests for POST /auth/token

Groups:
    A — happy path (token issued, fields correct)
    B — wrong secret (401)
    C — missing IHOUSE_JWT_SECRET (503)
    D — validation (missing tenant_id)
    E — token integrity (verify with jwt.decode)
"""
from __future__ import annotations

import os
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from main import app  # PYTHONPATH=src

client = TestClient(app)

_SECRET = "test-secret-for-179"
_PASSWORD = "dev"
_TENANT = "tenant-abc"


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    """Set IHOUSE_JWT_SECRET and IHOUSE_DEV_PASSWORD for every test in this module."""
    monkeypatch.setenv("IHOUSE_JWT_SECRET", _SECRET)
    monkeypatch.setenv("IHOUSE_DEV_PASSWORD", _PASSWORD)

# ---------------------------------------------------------------------------
# Group A — Happy path
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_returns_200(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.status_code == 200

    def test_a2_response_has_token_field(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert "token" in resp.json()

    def test_a3_response_has_tenant_id(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.json()["tenant_id"] == _TENANT

    def test_a4_response_has_expires_in(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.json()["expires_in"] == 86_400

    def test_a5_token_is_string(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert isinstance(resp.json()["token"], str)
        assert len(resp.json()["token"]) > 20

    def test_a6_strips_tenant_whitespace(self):
        resp = client.post("/auth/token", json={"tenant_id": f"  {_TENANT}  ", "secret": _PASSWORD})
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == _TENANT


# ---------------------------------------------------------------------------
# Group B — Wrong secret
# ---------------------------------------------------------------------------

class TestGroupBWrongSecret:

    def test_b1_wrong_secret_returns_401(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": "wrongpassword"})
        assert resp.status_code == 401

    def test_b2_wrong_secret_returns_unauthorized_code(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": "bad"})
        assert resp.json()["error"] == "UNAUTHORIZED"

    def test_b3_empty_secret_rejected(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": ""})
        assert resp.status_code == 401

    def test_b4_no_token_issued_on_wrong_secret(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": "nope"})
        assert "token" not in resp.json()


# ---------------------------------------------------------------------------
# Group C — Missing JWT secret (503)
# ---------------------------------------------------------------------------

class TestGroupCMissingJwtSecret:

    def test_c1_no_jwt_secret_returns_503(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "")
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.status_code == 503

    def test_c2_no_jwt_secret_auth_not_configured_code(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "")
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.json()["error"] == "AUTH_NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# Group D — Validation
# ---------------------------------------------------------------------------

class TestGroupDValidation:

    def test_d1_empty_tenant_id_rejected(self):
        resp = client.post("/auth/token", json={"tenant_id": "", "secret": _PASSWORD})
        assert resp.status_code == 422

    def test_d2_whitespace_only_tenant_id_rejected(self):
        resp = client.post("/auth/token", json={"tenant_id": "   ", "secret": _PASSWORD})
        assert resp.status_code == 422

    def test_d3_missing_tenant_id_field_rejected(self):
        resp = client.post("/auth/token", json={"secret": _PASSWORD})
        assert resp.status_code == 422

    def test_d4_missing_secret_field_rejected(self):
        resp = client.post("/auth/token", json={"tenant_id": _TENANT})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Group E — Token integrity
# ---------------------------------------------------------------------------

class TestGroupETokenIntegrity:

    def _get_token(self) -> str:
        resp = client.post("/auth/token", json={"tenant_id": _TENANT, "secret": _PASSWORD})
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_e1_token_decodes_with_correct_secret(self):
        token = self._get_token()
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
        assert payload["sub"] == _TENANT

    def test_e2_token_sub_matches_tenant_id(self):
        token = self._get_token()
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
        assert payload["sub"] == _TENANT

    def test_e3_token_has_exp_claim(self):
        token = self._get_token()
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
        assert "exp" in payload
        assert payload["exp"] > int(time.time())

    def test_e4_token_expires_in_24h(self):
        token = self._get_token()
        payload = jwt.decode(token, _SECRET, algorithms=["HS256"])
        ttl = payload["exp"] - payload["iat"]
        assert ttl == 86_400

    def test_e5_token_rejected_with_wrong_secret(self):
        token = self._get_token()
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, "wrong-secret", algorithms=["HS256"])
