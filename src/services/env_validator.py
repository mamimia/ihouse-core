"""
iHouse Core — Environment Variable Validator
Phase 466 — Environment Configuration Audit

Validates that all required env vars are set before the app starts.
Call validate_production_env() from main.py during startup.
"""

import os
import sys
import logging

logger = logging.getLogger("ihouse.env_validator")


# Required in production (IHOUSE_DEV_MODE != "true")
REQUIRED_PRODUCTION = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "IHOUSE_JWT_SECRET",
    "IHOUSE_GUEST_TOKEN_SECRET",
    "IHOUSE_ACCESS_TOKEN_SECRET",
]

# Required always (dev or production)
REQUIRED_ALWAYS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
]

# Recommended but not fatal if missing
RECOMMENDED = [
    "IHOUSE_TENANT_ID",
    "IHOUSE_API_KEY",
    "IHOUSE_ENV",
    "IHOUSE_BOOTSTRAP_SECRET",  # Phase 761 — first admin creation
    "SENTRY_DSN",
]

# Security constraints
SECURITY_RULES = {
    "IHOUSE_JWT_SECRET": {"min_length": 32, "label": "JWT secret"},
    "IHOUSE_GUEST_TOKEN_SECRET": {"min_length": 32, "label": "Guest token secret"},
    "IHOUSE_ACCESS_TOKEN_SECRET": {"min_length": 32, "label": "Access token secret"},
}


def validate_production_env() -> list[str]:
    """
    Validate environment variables for production readiness.

    Returns list of warnings. Raises SystemExit if critical vars missing
    and IHOUSE_DEV_MODE is not "true".
    """
    is_dev = os.environ.get("IHOUSE_DEV_MODE", "").lower() == "true"
    warnings: list[str] = []
    errors: list[str] = []

    # Check required vars
    required = REQUIRED_ALWAYS if is_dev else REQUIRED_PRODUCTION
    for var in required:
        if not os.environ.get(var):
            errors.append(f"MISSING REQUIRED: {var}")

    # Check dev mode in production
    env_label = os.environ.get("IHOUSE_ENV", "development")
    if env_label == "production" and is_dev:
        errors.append(
            "SECURITY: IHOUSE_DEV_MODE=true with IHOUSE_ENV=production — "
            "this disables JWT auth and is NEVER allowed in production"
        )

    # Check security constraints
    if not is_dev:
        for var, rules in SECURITY_RULES.items():
            value = os.environ.get(var, "")
            if value and len(value) < rules["min_length"]:
                warnings.append(
                    f"WEAK: {rules['label']} ({var}) is only {len(value)} chars "
                    f"(minimum {rules['min_length']})"
                )

    # Check recommended vars
    for var in RECOMMENDED:
        if not os.environ.get(var):
            warnings.append(f"RECOMMENDED: {var} is not set")

    # Log results
    for w in warnings:
        logger.warning("ENV VALIDATION: %s", w)
    for e in errors:
        logger.error("ENV VALIDATION: %s", e)

    # Fatal in production
    if errors and not is_dev:
        logger.critical(
            "ENV VALIDATION FAILED — %d errors. "
            "Set all required vars or use IHOUSE_DEV_MODE=true for development.",
            len(errors),
        )
        print(
            f"\\n❌ Environment validation failed ({len(errors)} errors):\\n"
            + "\\n".join(f"  - {e}" for e in errors),
            file=sys.stderr,
        )
        sys.exit(1)

    return warnings
