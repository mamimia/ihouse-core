"""
Phase 237 — Integration Test Configuration

Markers and fixtures for the integration test suite.

Guard: integration tests are SKIPPED unless IHOUSE_ENV=staging.
This ensures that running `pytest` normally (without staging env)
never triggers real DB calls.
"""
from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks test as an integration test (requires staging Supabase)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip all integration tests unless IHOUSE_ENV=staging."""
    if os.getenv("IHOUSE_ENV") != "staging":
        skip = pytest.mark.skip(reason="Integration tests require IHOUSE_ENV=staging")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def supabase_client():
    """Real Supabase client — only usable in staging."""
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@pytest.fixture(scope="session")
def base_url():
    """API base URL for staging."""
    port = os.getenv("PORT", "8000")
    return f"http://localhost:{port}"


@pytest.fixture(scope="session")
def auth_headers():
    """JWT headers for staging — uses IHOUSE_JWT_SECRET to sign a test token."""
    import jwt as _jwt

    secret = os.getenv("IHOUSE_JWT_SECRET", "staging-test-secret-replace-with-32-chars-min")
    token = _jwt.encode(
        {"sub": "staging-test-tenant", "role": "manager"},
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def tenant_id():
    return "staging-test-tenant"
