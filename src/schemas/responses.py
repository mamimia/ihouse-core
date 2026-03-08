"""
OpenAPI Response Schema Models — Phase 63
==========================================

Pydantic models for all HTTP response bodies.
Used exclusively for OpenAPI documentation generation.
Actual responses are still returned via JSONResponse for performance,
but FastAPI uses these schemas to generate the /docs spec.
"""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness check response."""
    status: str = Field(..., description="'ok' | 'degraded' | 'unhealthy'")
    version: str = Field(..., description="Application version (semver)")
    env: str = Field(..., description="Deployment environment")
    checks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-check results: supabase ping, DLQ count",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "0.1.0",
                "env": "production",
                "checks": {
                    "supabase": {"status": "ok", "latency_ms": 12},
                    "dlq": {"status": "ok", "unprocessed_count": 0},
                },
            }
        }
    }


class WebhookAcceptedResponse(BaseModel):
    """Returned when an OTA webhook event is successfully ingested."""
    status: str = Field("ACCEPTED", description="Always 'ACCEPTED' on success")
    idempotency_key: str = Field(
        ...,
        description="Deterministic key for this event: {provider}:{event_type}:{reservation_id}",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ACCEPTED",
                "idempotency_key": "bookingcom:reservation_create:RES-001",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Generic error response used for 403, 500."""
    error: str = Field(..., description="Machine-readable error code")

    model_config = {"json_schema_extra": {"example": {"error": "SIGNATURE_VERIFICATION_FAILED"}}}


class ValidationErrorResponse(BaseModel):
    """Returned when OTA payload fails structural validation."""
    error: str = Field("PAYLOAD_VALIDATION_FAILED", description="Error type")
    codes: List[str] = Field(
        ...,
        description="List of validation error codes (all failures returned — not fail-fast)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "PAYLOAD_VALIDATION_FAILED",
                "codes": ["RESERVATION_ID_REQUIRED", "OCCURRED_AT_INVALID"],
            }
        }
    }


class RateLimitErrorResponse(BaseModel):
    """Returned when the per-tenant rate limit is exceeded."""
    error: str = Field("RATE_LIMIT_EXCEEDED", description="Error type")
    retry_after_seconds: int = Field(
        ...,
        description="Number of seconds to wait before retrying",
        ge=1,
    )

    model_config = {
        "json_schema_extra": {
            "example": {"error": "RATE_LIMIT_EXCEEDED", "retry_after_seconds": 42}
        }
    }
