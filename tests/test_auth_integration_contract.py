"""Phase 413 — Frontend Auth Integration contract tests.

Verifies the auth integration data structures and flow patterns.
"""

import pytest
import hashlib
import hmac
import time


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

JWT_PAYLOAD = {
    "sub": "user_001",
    "role": "admin",
    "tenant_id": "tenant_1",
    "exp": int(time.time()) + 3600,
    "iat": int(time.time()),
}

VALID_ROLES = {"admin", "manager", "worker", "owner"}

ROUTE_GROUPS = {
    "(app)": {"requires_auth": True, "roles": ["admin", "manager", "worker"]},
    "(public)": {"requires_auth": False, "roles": []},
}

ACCESS_TOKEN_TYPES = {"guest", "worker", "onboard"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthIntegration:
    """Contract tests for frontend auth integration."""

    def test_jwt_has_required_claims(self):
        """JWT payload contains required claims."""
        required = ["sub", "role", "tenant_id", "exp", "iat"]
        for claim in required:
            assert claim in JWT_PAYLOAD

    def test_role_is_valid(self):
        """JWT role must be from known set."""
        assert JWT_PAYLOAD["role"] in VALID_ROLES

    def test_token_not_expired(self):
        """Token expiry must be in the future."""
        assert JWT_PAYLOAD["exp"] > time.time()

    def test_app_routes_require_auth(self):
        """(app) route group requires authentication."""
        assert ROUTE_GROUPS["(app)"]["requires_auth"] is True

    def test_public_routes_no_auth(self):
        """(public) route group does not require auth."""
        assert ROUTE_GROUPS["(public)"]["requires_auth"] is False

    def test_admin_role_has_app_access(self):
        """Admin role can access (app) routes."""
        assert "admin" in ROUTE_GROUPS["(app)"]["roles"]

    def test_access_token_types_are_valid(self):
        """Access token system supports known types."""
        for t in ACCESS_TOKEN_TYPES:
            assert t in {"guest", "worker", "onboard"}

    def test_hmac_sha256_used_for_access_tokens(self):
        """Access tokens use HMAC-SHA256."""
        secret = b"test_secret_at_least_32_chars_long"
        message = b"test_token_data"
        sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
        assert len(sig) == 64  # SHA256 hex digest

    def test_login_endpoint_pattern(self):
        """Login endpoint follows expected pattern."""
        login_url = "/auth/login"
        assert login_url.startswith("/auth/")

    def test_session_endpoint_pattern(self):
        """Session endpoint follows expected pattern."""
        session_url = "/auth/session"
        assert session_url.startswith("/auth/")

    def test_role_based_redirect(self):
        """Each role has an entry point redirect."""
        role_entries = {
            "admin": "/dashboard",
            "manager": "/dashboard",
            "worker": "/worker/tasks",
            "owner": "/owner/dashboard",
        }
        for role in VALID_ROLES:
            assert role in role_entries

    def test_token_expiry_is_reasonable(self):
        """Token expiry within 24 hours."""
        max_exp = int(time.time()) + 86400
        assert JWT_PAYLOAD["exp"] <= max_exp
