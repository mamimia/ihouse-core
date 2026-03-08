"""
OTA Webhook Ingestion — FastAPI Router
======================================

Exposes a single endpoint:

    POST /webhooks/{provider}

The endpoint is the HTTP boundary for all incoming OTA webhook events.

Flow:
    1.  Read raw body bytes (BEFORE json.loads — required by signature verifier)
    2.  verify_webhook_signature  → 403 SignatureVerificationError
    3.  json.loads(raw_body)      → payload dict
    4.  validate_ota_payload      → 400 if invalid
    5.  ingest_provider_event     → 200 with idempotency_key
    6.  Any unexpected exception  → 500

HTTP status codes (locked):
    200  ACCEPTED          — envelope created, idempotency_key returned
    400  PAYLOAD_VALIDATION_FAILED  — structural/semantic validation error
    403  SIGNATURE_VERIFICATION_FAILED — HMAC mismatch or unknown provider
    500  INTERNAL_ERROR    — unexpected exception (never surfaces internals)

Note on tenant_id:
    Currently sourced from payload["tenant_id"] — already validated as
    non-empty by validate_ota_payload before reaching the service call.
    JWT-based auth is deferred to a later phase and will not require
    changes to the ingestion logic below.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from adapters.ota.payload_validator import validate_ota_payload
from adapters.ota.service import ingest_provider_event
from adapters.ota.signature_verifier import (
    SignatureVerificationError,
    get_signature_header_name,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /webhooks/{provider}
# ---------------------------------------------------------------------------

@router.post("/webhooks/{provider}")
async def receive_webhook(provider: str, request: Request) -> JSONResponse:
    """
    Receive and ingest an OTA provider webhook event.

    Args:
        provider: OTA provider slug (bookingcom, expedia, airbnb, agoda, tripcom)
        request:  Incoming HTTP request — raw body is read before JSON parsing

    Returns:
        JSONResponse with status code and body as described in module docstring.
    """
    # ------------------------------------------------------------------
    # Step 1 — Read raw body (must happen before json.loads)
    # ------------------------------------------------------------------
    raw_body: bytes = await request.body()

    # ------------------------------------------------------------------
    # Step 2 — Signature verification
    # ------------------------------------------------------------------
    try:
        header_name = get_signature_header_name(provider)
        signature_header = request.headers.get(header_name, "")
        verify_webhook_signature(
            provider=provider,
            raw_body=raw_body,
            signature_header=signature_header,
        )
    except ValueError as exc:
        # Unknown provider — reject at signature layer
        logger.warning("[%s] Unknown provider: %s", provider, exc)
        return JSONResponse(
            status_code=403,
            content={
                "error": "SIGNATURE_VERIFICATION_FAILED",
                "detail": str(exc),
            },
        )
    except SignatureVerificationError as exc:
        logger.warning("[%s] Signature verification failed: %s", provider, exc.reason)
        return JSONResponse(
            status_code=403,
            content={
                "error": "SIGNATURE_VERIFICATION_FAILED",
                "detail": exc.reason,
            },
        )

    # ------------------------------------------------------------------
    # Step 3 — Parse JSON body
    # ------------------------------------------------------------------
    try:
        payload: Dict[str, Any] = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[%s] Invalid JSON body: %s", provider, exc)
        return JSONResponse(
            status_code=400,
            content={
                "error": "PAYLOAD_VALIDATION_FAILED",
                "codes": ["PAYLOAD_MUST_BE_DICT"],
            },
        )

    # ------------------------------------------------------------------
    # Step 4 — Payload boundary validation
    # ------------------------------------------------------------------
    validation = validate_ota_payload(provider=provider, payload=payload)
    if not validation.valid:
        logger.info(
            "[%s] Payload validation failed: %s",
            provider,
            validation.errors,
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "PAYLOAD_VALIDATION_FAILED",
                "codes": validation.errors,
            },
        )

    # ------------------------------------------------------------------
    # Step 5 — Extract tenant_id (guaranteed non-empty by validator)
    # ------------------------------------------------------------------
    tenant_id: str = str(payload["tenant_id"]).strip()

    # ------------------------------------------------------------------
    # Step 6 — Ingest through the canonical OTA pipeline
    # ------------------------------------------------------------------
    try:
        envelope = ingest_provider_event(
            provider=provider,
            payload=payload,
            tenant_id=tenant_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Unexpected error during ingestion: %s", provider, exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR"},
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ACCEPTED",
            "idempotency_key": envelope.idempotency_key,
        },
    )
