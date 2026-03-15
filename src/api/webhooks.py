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
    5.  ingest_provider_event_with_dlq  → full write pipeline:
        a. process_ota_event → canonical envelope
        b. skill_fn(payload) → emitted events
        c. apply_fn(envelope, emitted) → Supabase apply_envelope RPC
        d. DLQ routing on non-APPLIED status
        e. Financial facts, tasks, outbound sync (best-effort)
    6.  Any unexpected exception  → 500

HTTP status codes (locked):
    200  ACCEPTED          — envelope created AND persisted via apply_envelope
    400  PAYLOAD_VALIDATION_FAILED  — structural/semantic validation error
    403  SIGNATURE_VERIFICATION_FAILED — HMAC mismatch or unknown provider
    500  INTERNAL_ERROR    — unexpected exception (never surfaces internals)

Note on tenant_id:
    Phase 61: sourced from JWT Bearer token (sub claim) via verify_jwt Depends.
    Dev mode: if IHOUSE_JWT_SECRET not set, returns 'dev-tenant' with warning.
    JWT-based auth: missing/invalid token → 403 AUTH_FAILED.

Rate limiting (Phase 62):
    Per-tenant sliding window via rate_limit Depends.
    Configurable via IHOUSE_RATE_LIMIT_RPM (default 60/min).
    Returns 429 with Retry-After on excess.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.rate_limiter import rate_limit

from adapters.ota.payload_validator import validate_ota_payload
from adapters.ota.service import ingest_provider_event_with_dlq
from adapters.ota.signature_verifier import (
    SignatureVerificationError,
    get_signature_header_name,
    verify_webhook_signature,
)
from schemas.responses import (
    ErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorResponse,
    WebhookAcceptedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# apply_fn / skill_fn factories — wiring the canonical write pipeline
# ---------------------------------------------------------------------------

def _build_apply_fn() -> Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Build the apply_fn that calls the Supabase apply_envelope RPC.

    Returns a callable: (envelope_dict, emitted_events) -> {"status": "APPLIED" | ...}
    """
    from supabase import create_client  # type: ignore[import]

    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    def _apply(envelope_dict: Dict[str, Any], emitted: List[Dict[str, Any]]) -> Dict[str, Any]:
        response = client.rpc(
            "apply_envelope",
            {
                "p_envelope": envelope_dict,
                "p_emit": emitted,
            },
        ).execute()

        if not response.data:
            raise RuntimeError("apply_envelope RPC returned no result")

        # response.data can be a list or a dict — normalize
        data = response.data
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        if isinstance(data, dict):
            return data
        return {"status": str(data)}

    return _apply


def _build_skill_router() -> Callable[[str, Dict[str, Any]], Any]:
    """
    Build a universal skill_router(event_type, payload) that routes
    to the correct core skill module via skill_exec_registry.core.json.

    Returns a callable: (event_type, payload) -> SkillOutput
    """
    from pathlib import Path

    registry_path = Path(__file__).resolve().parent.parent / "core" / "skill_exec_registry.core.json"
    with open(registry_path, encoding="utf-8") as f:
        skill_exec_registry: Dict[str, str] = json.load(f)

    def _route(event_type: str, payload: Dict[str, Any]) -> Any:
        module_path = skill_exec_registry.get(event_type)
        if not module_path:
            raise ValueError(f"No skill registered for event type: {event_type}")
        mod = importlib.import_module(module_path)
        run_fn = getattr(mod, "run", None)
        if not callable(run_fn):
            raise ValueError(f"Skill module {module_path} has no run() function")
        return run_fn(payload)

    return _route


# ---------------------------------------------------------------------------
# POST /webhooks/{provider}
# ---------------------------------------------------------------------------

@router.post(
    "/webhooks/{provider}",
    tags=["webhooks"],
    summary="Ingest OTA provider webhook event",
    response_model=WebhookAcceptedResponse,
    responses={
        200: {
            "model": WebhookAcceptedResponse,
            "description": "Event accepted and persisted via apply_envelope",
        },
        400: {
            "model": ValidationErrorResponse,
            "description": "Payload validation failed — all errors returned (not fail-fast)",
        },
        403: {
            "model": ErrorResponse,
            "description": "Signature verification failed or JWT auth rejected",
        },
        429: {
            "model": RateLimitErrorResponse,
            "description": "Per-tenant rate limit exceeded — see Retry-After header",
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying",
                    "schema": {"type": "integer"},
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Unexpected internal error — no internal details leaked",
        },
    },
    openapi_extra={
        "security": [{"BearerAuth": []}],
        "x-provider-notes": (
            "Signature header name is provider-specific: "
            "X-Booking-Signature / X-Expedia-Signature / X-Airbnb-Signature / "
            "X-Agoda-Signature / X-TripCom-Signature"
        ),
    },
)
async def receive_webhook(
    provider: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    _: None = Depends(rate_limit),
) -> JSONResponse:
    """
    Receive and ingest an OTA provider webhook event.

    **Supported providers:** `bookingcom` · `expedia` · `airbnb` · `agoda` · `tripcom`

    **Authentication:** Bearer JWT token required (HMAC-HS256, `sub` claim = `tenant_id`).
    In development mode (`IHOUSE_JWT_SECRET` not set), auth is bypassed.

    **Signature verification:** Each provider uses a dedicated HMAC-SHA256 signature header.
    Secret is read from `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` env var.
    In development mode (secret not set), verification is skipped.

    **Rate limiting:** 60 req/min per tenant (configurable via `IHOUSE_RATE_LIMIT_RPM`).
    Responds with `429` and `Retry-After` header on excess.
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
    # Step 5 — tenant_id comes from JWT Depends (already resolved above)
    # ------------------------------------------------------------------
    # tenant_id is injected by jwt_auth — no extraction from payload needed

    # ------------------------------------------------------------------
    # Step 6 — Ingest through the FULL canonical OTA pipeline
    #
    # Phase 784: switched from ingest_provider_event (envelope-only, no DB write)
    # to ingest_provider_event_with_dlq which chains:
    #   a. process_ota_event → canonical envelope
    #   b. skill_fn(payload) → emitted events via core skill
    #   c. apply_fn(envelope, emitted) → Supabase apply_envelope RPC
    #   d. DLQ routing on non-APPLIED status
    #   e. Financial facts, tasks, outbound sync (best-effort)
    # ------------------------------------------------------------------
    try:
        # Build the apply_fn that calls the Supabase apply_envelope RPC
        apply_fn = _build_apply_fn()

        # Phase 784: Use skill_router instead of pre-classifying.
        # process_ota_event inside ingest_provider_event_with_dlq already
        # classifies the event and sets envelope.type. The skill_router
        # receives (event_type, payload) and routes to the correct skill.
        skill_router = _build_skill_router()

        result = ingest_provider_event_with_dlq(
            provider=provider,
            payload=payload,
            tenant_id=tenant_id,
            apply_fn=apply_fn,
            skill_router=skill_router,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("[%s] Unexpected error during ingestion: %s", provider, exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR"},
        )

    # Extract idempotency_key from envelope for the response
    # ingest_provider_event_with_dlq returns a dict with status
    idempotency_key = result.get("idempotency_key", "") if isinstance(result, dict) else ""

    # If the result doesn't contain an idempotency_key, generate one from payload
    if not idempotency_key:
        from adapters.ota.pipeline import process_ota_event
        try:
            envelope = process_ota_event(
                provider=provider,
                payload=payload,
                tenant_id=tenant_id,
            )
            idempotency_key = envelope.idempotency_key or ""
        except Exception:
            idempotency_key = ""

    return JSONResponse(
        status_code=200,
        content={
            "status": "ACCEPTED",
            "idempotency_key": idempotency_key,
        },
    )

