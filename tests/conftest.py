"""
tests/conftest.py — Phase 283 — Test Suite Isolation

Session-scoped and function-scoped fixtures that ensure environment
variables do not leak between test files.

Root cause (Phase 282 finding):
    Several test files set IHOUSE_DEV_MODE, IHOUSE_JWT_SECRET, and
    IHOUSE_WEBHOOK_SECRET_* at module level or via os.environ directly.
    This leaks env state to every subsequent test in the same session.

Solution:
    1. Set IHOUSE_DEV_MODE=true at session start (the test suite
       was designed to run with dev mode — tests that need to verify
       auth-disabled behavior explicitly use monkeypatch.setenv/delenv).
    2. After each test function, restore the sensitive env vars to the
       session-start state — removing any that were added and resetting
       any that were changed. This guarantees every test starts with
       identical env state regardless of test ordering.
"""
from __future__ import annotations

import os
import warnings
import pytest

# Phase 816 — Suppress InsecureKeyLengthWarning in test output.
# Tests use intentionally short HMAC keys; the warning is noise, not a real concern.
warnings.filterwarnings("ignore", message=".*HMAC key.*below the minimum recommended length.*", category=DeprecationWarning)
try:
    from jwt.exceptions import InsecureKeyLengthWarning  # type: ignore[attr-defined]
    warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)
except ImportError:
    pass  # older PyJWT versions don't have this category

# Session-start defaults: these env vars must be set before any test imports
# router modules (which read env at import time via FastAPI dependency injection).
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_RATE_LIMIT_RPM", "0")  # disable rate limiter in tests
os.environ["IHOUSE_DRY_RUN"] = "false"  # force false — tests using dry-run must opt in via monkeypatch
os.environ["IHOUSE_ENVELOPE_DISABLED"] = "true"  # Phase 570 — envelope middleware tested independently in test_phases_570_574

# Env vars that MUST be cleaned between every test function.
_SENSITIVE_VARS = [
    "IHOUSE_DEV_MODE",
    "IHOUSE_DRY_RUN",
    "IHOUSE_ENVELOPE_DISABLED",
    "IHOUSE_LINE_SECRET",
    "OPENAI_API_KEY",
    "AIRBNB_API_KEY",
    "BOOKINGCOM_API_KEY",
    "EXPEDIA_API_KEY",
    "VRBO_API_KEY",
]

# Pattern prefix for webhook secrets (IHOUSE_WEBHOOK_SECRET_*)
_WEBHOOK_SECRET_PREFIX = "IHOUSE_WEBHOOK_SECRET_"


@pytest.fixture(autouse=True, scope="session")
def _capture_env_snapshot():
    """Capture env snapshot once at session start (after defaults above)."""
    snapshot = {}
    for var in _SENSITIVE_VARS:
        if var in os.environ:
            snapshot[var] = os.environ[var]
        else:
            snapshot[var] = None

    for key in list(os.environ):
        if key.startswith(_WEBHOOK_SECRET_PREFIX):
            snapshot[key] = os.environ[key]

    yield snapshot


@pytest.fixture(autouse=True)
def _clean_env_per_test(_capture_env_snapshot):
    """
    After each test: restore sensitive env vars to session-start state.
    This runs for EVERY test function automatically.
    """
    snapshot = _capture_env_snapshot

    yield  # test runs here

    # --- Restore after test ---

    # 1. Restore or remove sensitive vars
    for var in _SENSITIVE_VARS:
        original = snapshot.get(var)
        if original is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = original

    # 2. Remove any webhook secrets that were added during the test
    for key in list(os.environ):
        if key.startswith(_WEBHOOK_SECRET_PREFIX):
            if key not in snapshot:
                del os.environ[key]
            else:
                os.environ[key] = snapshot[key]
