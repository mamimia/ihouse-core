"""
Phase 985 — OCR API Router
============================

Endpoints for OCR processing within the 3 allowed worker wizard flows.

Endpoints:
    POST /worker/ocr/process          — Submit image for OCR
    GET  /worker/ocr/result/{id}      — Poll OCR result
    GET  /worker/ocr/prefill/{booking_id}/{capture_type} — Fetch latest OCR result for wizard pre-fill
    PATCH /worker/ocr/result/{id}/confirm — Worker confirms extracted fields
    PATCH /worker/ocr/result/{id}/correct — Worker corrects a field
    POST /admin/ocr/test-connection    — Admin tests a provider connection
    GET  /admin/ocr/provider-config    — List provider config for tenant
    GET  /admin/ocr/review-queue       — List pending OCR results for admin

Scope enforcement:
    The scope guard fires at the START of /process, before any provider
    call, before any DB write, before any queue operation.
    Out-of-scope capture_type → HTTP 422 SCOPE_VIOLATION.
    Azure/local quota cannot be consumed by out-of-scope calls.

Auth: JWT required on all endpoints (jwt_auth).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.auth import jwt_auth, jwt_identity
from api.error_models import ErrorCode, make_error_response, make_success_response
from ocr.scope_guard import validate_capture_type, OcrScopeViolation

logger = logging.getLogger(__name__)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


# ─── DB + OCR helpers ─────────────────────────────────────────────

def _get_supabase_client() -> Any:
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


async def _get_tenant_provider_configs(db: Any, tenant_id: str) -> list:
    """Fetch tenant OCR provider configs, sorted by priority ASC."""
    resp = (
        db.table("ocr_provider_config")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("enabled", True)
        .order("priority", desc=False)
        .execute()
    )
    return resp.data or []


def _save_ocr_result(db: Any, tenant_id: str, result_data: dict) -> str:
    """Persist an OcrResult to ocr_results table. Returns the new row ID."""
    row_id = str(uuid.uuid4())
    db.table("ocr_results").insert({
        "id": row_id,
        "tenant_id": tenant_id,
        **result_data,
    }).execute()
    return row_id


def _get_ocr_result(db: Any, tenant_id: str, result_id: str) -> Optional[dict]:
    """Fetch a single OCR result row, enforcing tenant isolation."""
    resp = (
        db.table("ocr_results")
        .select("*")
        .eq("id", result_id)
        .eq("tenant_id", tenant_id)
        .maybe_single()
        .execute()
    )
    return resp.data


# ─── POST /worker/ocr/process ─────────────────────────────────────

@router.post("/worker/ocr/process")
async def process_ocr(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
):
    """
    Submit an image for OCR processing.

    Required body fields:
        capture_type   — MUST be one of the 3 allowed types (scope guard enforced)
        image_data     — Base64-encoded image bytes (with or without data URI prefix)
        booking_id     — The booking this capture belongs to
        document_type  — Optional: 'PASSPORT', 'NATIONAL_ID', 'DRIVING_LICENSE'

    Returns:
        { result_id, status, extracted_fields, field_confidences,
          overall_confidence, requires_review, quality_warnings }

    On scope violation:
        HTTP 422 SCOPE_VIOLATION (before any provider call)

    On provider failure:
        HTTP 200 with status='failed' — worker falls back to manual entry
        OCR failure is never blocking (INV-OCR-04)
    """
    capture_type = (body.get("capture_type") or "").strip()
    image_data = body.get("image_data") or ""
    booking_id = (body.get("booking_id") or "").strip()
    document_type = (body.get("document_type") or "").strip().upper() or None

    # ── Validate required fields ──────────────────────────────────
    if not capture_type:
        return make_error_response(422, "VALIDATION_ERROR", "capture_type is required")

    if not image_data:
        return make_error_response(422, "VALIDATION_ERROR", "image_data is required")

    if not booking_id:
        return make_error_response(422, "VALIDATION_ERROR", "booking_id is required")

    # ── SCOPE GUARD — runs BEFORE any provider call ───────────────
    # This is the product boundary: no OCR for anything outside the 3 allowed types.
    # No Azure quota, no local compute, no DB write happens if this fails.
    try:
        capture_type = validate_capture_type(capture_type)
    except OcrScopeViolation as exc:
        logger.warning(
            "OCR scope violation blocked: capture_type='%s' tenant=%s booking=%s",
            capture_type, tenant_id, booking_id,
        )
        return make_error_response(
            422,
            "SCOPE_VIOLATION",
            f"OCR not allowed for capture_type='{exc.capture_type}'. "
            f"Only identity_document_capture, checkin_opening_meter_capture, "
            f"checkout_closing_meter_capture are permitted.",
        )

    # ── Decode image ──────────────────────────────────────────────
    import base64 as b64mod

    try:
        raw = image_data
        if "," in raw:
            raw = raw.split(",", 1)[1]
        image_bytes = b64mod.b64decode(raw)
    except Exception:
        return make_error_response(422, "VALIDATION_ERROR", "image_data is not valid base64")

    # ── Build OCR request ─────────────────────────────────────────
    from ocr.provider_base import OcrRequest
    from ocr.fallback import process_ocr_request

    request = OcrRequest(
        image_bytes=image_bytes,
        capture_type=capture_type,
        document_type=document_type,
        booking_id=booking_id,
        tenant_id=tenant_id,
    )

    # ── Get tenant provider config ────────────────────────────────
    db = _get_supabase_client()
    tenant_configs = await _get_tenant_provider_configs(db, tenant_id)

    # ── Run OCR through provider chain ───────────────────────────
    ocr_result = await process_ocr_request(request, tenant_configs=tenant_configs)

    # ── Persist result ────────────────────────────────────────────
    confidence_report = ocr_result.confidence_report
    status = "failed" if ocr_result.status.value == "failed" else "pending_review"

    result_row = {
        "booking_id": booking_id,
        "capture_type": capture_type,
        "document_type": ocr_result.document_type,
        "provider_used": ocr_result.provider_name,
        "extracted_fields": ocr_result.extracted_fields,
        "field_confidences": ocr_result.field_confidences,
        "overall_confidence": ocr_result.overall_confidence,
        "status": status,
        "image_quality_score": ocr_result.image_quality_score,
        "quality_warnings": [w.value for w in ocr_result.quality_warnings],
        "processing_time_ms": ocr_result.processing_time_ms,
        "error_message": ocr_result.error_message,
    }

    try:
        result_id = _save_ocr_result(db, tenant_id, result_row)
    except Exception as exc:
        logger.exception("Failed to save OCR result: %s", exc)
        # Still return the OCR data — don't fail the worker because DB write failed
        result_id = None

    return make_success_response({
        "result_id": result_id,
        "capture_type": capture_type,
        "status": ocr_result.status.value,
        "provider_used": ocr_result.provider_name,
        "document_type": ocr_result.document_type,
        "extracted_fields": ocr_result.extracted_fields,
        "field_confidences": ocr_result.field_confidences,
        "overall_confidence": round(ocr_result.overall_confidence, 4),
        "requires_review": confidence_report.requires_review,
        "low_confidence_fields": confidence_report.low_confidence_fields,
        "quality_warnings": [w.value for w in ocr_result.quality_warnings],
        "image_quality_score": ocr_result.image_quality_score,
        "processing_time_ms": ocr_result.processing_time_ms,
        "error_message": ocr_result.error_message,
        # INV-OCR-02: always signal that worker review is required
        "review_required": True,
    })


# ─── GET /worker/ocr/result/{result_id} ───────────────────────────

@router.get("/worker/ocr/result/{result_id}")
async def get_ocr_result(
    result_id: str = Path(...),
    tenant_id: str = Depends(jwt_auth),
):
    """
    Poll or retrieve an OCR result by ID (tenant-isolated).

    Returns the same shape as /process response, plus:
        - status (current: pending_review / confirmed / corrected / rejected / failed)
        - corrected_fields (if worker has corrected)
        - reviewed_by / reviewed_at
    """
    db = _get_supabase_client()
    row = _get_ocr_result(db, tenant_id, result_id)

    if not row:
        return make_error_response(404, ErrorCode.NOT_FOUND, f"OCR result '{result_id}' not found")

    return make_success_response({
        "result_id": row["id"],
        "booking_id": row["booking_id"],
        "capture_type": row["capture_type"],
        "document_type": row.get("document_type"),
        "provider_used": row["provider_used"],
        "status": row["status"],
        "extracted_fields": row.get("extracted_fields") or {},
        "field_confidences": row.get("field_confidences") or {},
        "overall_confidence": row.get("overall_confidence"),
        "corrected_fields": row.get("corrected_fields"),
        "quality_warnings": row.get("quality_warnings") or [],
        "image_quality_score": row.get("image_quality_score"),
        "processing_time_ms": row.get("processing_time_ms"),
        "reviewed_by": row.get("reviewed_by"),
        "reviewed_at": row.get("reviewed_at"),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
        # INV-OCR-02: always require review
        "review_required": True,
    })


# ─── PATCH /worker/ocr/result/{result_id}/confirm ────────────────

@router.patch("/worker/ocr/result/{result_id}/confirm")
async def confirm_ocr_result(
    result_id: str = Path(...),
    body: dict = None,
    identity: dict = Depends(jwt_identity),
):
    """
    Worker confirms OCR-extracted fields as correct (no corrections needed).

    Body: optional { confirmed_fields: {field: value} }

    Sets status = 'confirmed', records reviewer.
    This does NOT save to the product entities — the caller (wizard step)
    is responsible for submitting to save-guest-identity or checkin-settlement.
    """
    tenant_id = identity.get("tenant_id", "")
    user_id = identity.get("user_id", "")
    body = body or {}

    db = _get_supabase_client()
    row = _get_ocr_result(db, tenant_id, result_id)
    if not row:
        return make_error_response(404, ErrorCode.NOT_FOUND, f"OCR result '{result_id}' not found")

    if row["status"] in ("confirmed", "corrected"):
        # Idempotent: already reviewed
        return make_success_response({"result_id": result_id, "status": row["status"]})

    now = datetime.now(timezone.utc).isoformat()
    db.table("ocr_results").update({
        "status": "confirmed",
        "reviewed_by": user_id,
        "reviewed_at": now,
    }).eq("id", result_id).eq("tenant_id", tenant_id).execute()

    return make_success_response({
        "result_id": result_id,
        "status": "confirmed",
        "reviewed_by": user_id,
        "reviewed_at": now,
    })


# ─── PATCH /worker/ocr/result/{result_id}/correct ────────────────

@router.patch("/worker/ocr/result/{result_id}/correct")
async def correct_ocr_result(
    result_id: str = Path(...),
    body: dict = None,
    identity: dict = Depends(jwt_identity),
):
    """
    Worker corrects one or more OCR-extracted fields.

    Required body: { corrections: { field_name: corrected_value, ... } }

    Sets status = 'corrected', records corrected_fields and reviewer.
    corrected_fields is the authoritative version — it supersedes extracted_fields
    for any key present in corrections.
    """
    tenant_id = identity.get("tenant_id", "")
    user_id = identity.get("user_id", "")
    body = body or {}

    corrections = body.get("corrections") or {}
    if not corrections or not isinstance(corrections, dict):
        return make_error_response(
            422, "VALIDATION_ERROR",
            "corrections dict is required with at least one field"
        )

    db = _get_supabase_client()
    row = _get_ocr_result(db, tenant_id, result_id)
    if not row:
        return make_error_response(404, ErrorCode.NOT_FOUND, f"OCR result '{result_id}' not found")

    now = datetime.now(timezone.utc).isoformat()

    # Merge with existing corrected_fields if any
    existing_corrections = row.get("corrected_fields") or {}
    merged = {**existing_corrections, **corrections}

    db.table("ocr_results").update({
        "status": "corrected",
        "corrected_fields": merged,
        "reviewed_by": user_id,
        "reviewed_at": now,
    }).eq("id", result_id).eq("tenant_id", tenant_id).execute()

    return make_success_response({
        "result_id": result_id,
        "status": "corrected",
        "corrected_fields": merged,
        "reviewed_by": user_id,
        "reviewed_at": now,
    })


# ─── POST /admin/ocr/test-connection ─────────────────────────────

@router.post("/admin/ocr/test-connection")
async def test_ocr_connection(
    body: dict,
    identity: dict = Depends(jwt_identity),
):
    """
    Admin: test a specific OCR provider connection.

    Required body: { provider_name: str }

    For Azure: makes a real lightweight GET to the Azure model info endpoint
    (no image, no quota cost). Proves the credential + endpoint combination.

    For local providers: checks Tesseract binary availability.

    Returns: { success, message, response_time_ms, provider_name }
    """
    tenant_id = identity.get("tenant_id", "")
    role = identity.get("role", "")

    if role not in ("admin", "manager"):
        return make_error_response(403, ErrorCode.FORBIDDEN, "Admin or manager role required")

    provider_name = (body.get("provider_name") or "").strip()
    if not provider_name:
        return make_error_response(422, "VALIDATION_ERROR", "provider_name is required")

    # Build provider from DB config (for Azure: real credentials)
    db = _get_supabase_client()
    config_resp = (
        db.table("ocr_provider_config")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("provider_name", provider_name)
        .maybe_single()
        .execute()
    )
    config_row = config_resp.data

    # Build provider with credentials if we have them
    provider = _build_provider_for_test(provider_name, config_row)
    if not provider:
        return make_error_response(
            404, ErrorCode.NOT_FOUND,
            f"Provider '{provider_name}' not recognized"
        )

    from ocr.fallback import test_provider as _test
    # Register temporarily just for this test call
    from ocr.provider_router import get_registry
    registry = get_registry()
    registry.register(provider)

    result = await _test(provider_name)

    # Update last_test_at + last_test_result in DB
    _update_test_result(db, tenant_id, provider_name, result)

    return make_success_response(result)


def _build_provider_for_test(provider_name: str, config_row: Optional[dict]):
    """Build a provider instance for connection test."""
    if provider_name == "azure_document_intelligence":
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider, make_azure_provider_from_db_config
        if config_row:
            return make_azure_provider_from_db_config(config_row)
        return AzureDocumentIntelligenceProvider()  # unconfigured → will fail cleanly

    elif provider_name == "local_mrz":
        from ocr.providers.local_mrz import LocalMrzProvider
        return LocalMrzProvider()

    elif provider_name == "local_meter":
        from ocr.providers.local_meter import LocalMeterProvider
        return LocalMeterProvider()

    elif provider_name == "local_tesseract":
        from ocr.providers.local_tesseract import LocalTesseractProvider
        return LocalTesseractProvider()

    return None


def _update_test_result(db: Any, tenant_id: str, provider_name: str, result: dict) -> None:
    """Update last_test_at and last_test_result in ocr_provider_config."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        status = "success" if result.get("success") else f"error: {result.get('message', '')[:100]}"
        db.table("ocr_provider_config").update({
            "last_test_at": now,
            "last_test_result": status,
            "updated_at": now,
        }).eq("tenant_id", tenant_id).eq("provider_name", provider_name).execute()
    except Exception as exc:
        logger.warning("Failed to update test result in DB: %s", exc)


# ─── GET /admin/ocr/provider-config ──────────────────────────────

@router.get("/admin/ocr/provider-config")
async def get_provider_config(
    identity: dict = Depends(jwt_identity),
):
    """
    Admin: get all OCR provider configs for the tenant.
    API keys are MASKED in the response (INV-OCR-03).
    Returns has_endpoint/has_api_key booleans so Admin UI can show configured state.
    """
    tenant_id = identity.get("tenant_id", "")
    role = identity.get("role", "")

    if role not in ("admin", "manager"):
        return make_error_response(403, ErrorCode.FORBIDDEN, "Admin or manager role required")

    db = _get_supabase_client()
    resp = (
        db.table("ocr_provider_config")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("priority", desc=False)
        .execute()
    )

    # Sanitize: mask api_key, show has_endpoint / has_api_key booleans
    configs = []
    for row in (resp.data or []):
        config_json = row.get("config") or {}
        if isinstance(config_json, str):
            import json as _json
            try:
                config_json = _json.loads(config_json)
            except Exception:
                config_json = {}

        api_key = config_json.get("api_key", "")
        endpoint = config_json.get("endpoint", "")

        sanitized = {
            "id": row.get("id"),
            "provider_name": row.get("provider_name"),
            "enabled": row.get("enabled", False),
            "priority": row.get("priority", 99),
            "is_primary": row.get("is_primary", False),
            "is_fallback": row.get("is_fallback", False),
            "last_test_at": row.get("last_test_at"),
            "last_test_result": row.get("last_test_result"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            # Masked config info — never expose raw values
            "has_endpoint": bool(endpoint),
            "has_api_key": bool(api_key),
            "endpoint_preview": (endpoint[:30] + "…") if len(endpoint) > 30 else endpoint if endpoint else "",
            "api_key_preview": (api_key[:4] + "****" + api_key[-4:]) if len(api_key) >= 8 else ("****" if api_key else ""),
        }
        configs.append(sanitized)

    return make_success_response(configs)


# ─── PUT /admin/ocr/provider-config/{provider_name} ─────────────

@router.put("/admin/ocr/provider-config/{provider_name}")
async def upsert_provider_config(
    provider_name: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
):
    """
    Admin: create or update an OCR provider config.

    Body fields:
        enabled      — bool
        priority     — int (lower = higher priority)
        is_primary   — bool
        is_fallback  — bool
        config       — { endpoint, api_key, timeout } (sensitive — stored in JSONB)

    If config.api_key is "****" or empty, the existing key is preserved
    (allows saving non-credential fields without rotating the key).

    INV-OCR-03: credentials are stored in DB only, never logged, never
    returned except as masked previews.
    """
    tenant_id = identity.get("tenant_id", "")
    role = identity.get("role", "")

    if role not in ("admin", "manager"):
        return make_error_response(403, ErrorCode.FORBIDDEN, "Admin or manager role required")

    _KNOWN_PROVIDERS = {"azure_document_intelligence", "local_mrz", "local_meter", "local_tesseract"}
    if provider_name not in _KNOWN_PROVIDERS:
        return make_error_response(422, "VALIDATION_ERROR",
                                   f"Unknown provider '{provider_name}'. Known: {', '.join(sorted(_KNOWN_PROVIDERS))}")

    now = datetime.now(timezone.utc).isoformat()
    db = _get_supabase_client()

    # Check if row exists for this tenant + provider
    existing_resp = (
        db.table("ocr_provider_config")
        .select("id, config")
        .eq("tenant_id", tenant_id)
        .eq("provider_name", provider_name)
        .maybe_single()
        .execute()
    )
    existing = existing_resp.data

    # Build config JSONB — preserve existing api_key if not provided
    incoming_config = body.get("config") or {}
    if existing:
        old_config = existing.get("config") or {}
        if isinstance(old_config, str):
            import json as _json
            try:
                old_config = _json.loads(old_config)
            except Exception:
                old_config = {}
        # Preserve existing api_key if incoming is masked or empty
        new_api_key = incoming_config.get("api_key", "")
        if not new_api_key or new_api_key == "****" or "****" in new_api_key:
            incoming_config["api_key"] = old_config.get("api_key", "")
        # Preserve existing endpoint if not provided
        if not incoming_config.get("endpoint"):
            incoming_config["endpoint"] = old_config.get("endpoint", "")

    row_data = {
        "enabled": bool(body.get("enabled", False)),
        "priority": int(body.get("priority", 99)),
        "is_primary": bool(body.get("is_primary", False)),
        "is_fallback": bool(body.get("is_fallback", False)),
        "config": incoming_config,
        "updated_at": now,
    }

    if existing:
        # Update
        db.table("ocr_provider_config").update(row_data).eq("id", existing["id"]).execute()
        logger.info("OCR config updated: tenant=%s provider=%s", tenant_id, provider_name)
    else:
        # Insert
        row_data["tenant_id"] = tenant_id
        row_data["provider_name"] = provider_name
        row_data["created_at"] = now
        db.table("ocr_provider_config").insert(row_data).execute()
        logger.info("OCR config created: tenant=%s provider=%s", tenant_id, provider_name)

    return make_success_response({
        "provider_name": provider_name,
        "saved": True,
    })


# ─── DELETE /admin/ocr/provider-config/{provider_name} ───────────

@router.delete("/admin/ocr/provider-config/{provider_name}")
async def delete_provider_config(
    provider_name: str,
    identity: dict = Depends(jwt_identity),
):
    """
    Admin: remove an OCR provider config for this tenant.
    This disables the provider entirely — it won't be used in the fallback chain.
    """
    tenant_id = identity.get("tenant_id", "")
    role = identity.get("role", "")

    if role not in ("admin", "manager"):
        return make_error_response(403, ErrorCode.FORBIDDEN, "Admin or manager role required")

    db = _get_supabase_client()
    db.table("ocr_provider_config").delete().eq(
        "tenant_id", tenant_id
    ).eq("provider_name", provider_name).execute()

    logger.info("OCR config deleted: tenant=%s provider=%s", tenant_id, provider_name)

    return make_success_response({
        "provider_name": provider_name,
        "deleted": True,
    })


# ─── GET /worker/ocr/prefill/{booking_id}/{capture_type} ─────────

@router.get("/worker/ocr/prefill/{booking_id}/{capture_type}")
async def get_ocr_prefill(
    booking_id: str = Path(...),
    capture_type: str = Path(...),
    tenant_id: str = Depends(jwt_auth),
):
    """
    Fetch the latest OCR result for a booking + capture type, ready for wizard pre-fill.

    Called by the wizard step immediately after OCR processing, or when
    the worker returns to the step (e.g., network interruption recovery).

    Returns the merged pre-fill fields:
        - If status=corrected: corrected_fields merged over extracted_fields
        - If status=confirmed/pending_review: extracted_fields only
        - If no OCR result: empty {} (wizard shows blank form)

    The wizard MUST always allow manual edit of every pre-filled field (INV-OCR-02).
    This endpoint never blocks — missing OCR result returns 200 with empty prefill.

    Also returns:
        - result_id: to pass back to save-guest-identity or checkin-settlement as ocr_result_id
        - ocr_status: pending_review / confirmed / corrected / failed / none
        - low_confidence_fields: list of field names where confidence < 0.85
    """
    db = _get_supabase_client()

    # Fetch most recent non-failed OCR result for this booking+capture_type
    resp = (
        db.table("ocr_results")
        .select(
            "id, status, extracted_fields, field_confidences, "
            "corrected_fields, overall_confidence, quality_warnings, "
            "document_type, provider_used, created_at, error_message"
        )
        .eq("tenant_id", tenant_id)
        .eq("booking_id", booking_id)
        .eq("capture_type", capture_type)
        .neq("status", "failed")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = resp.data or []

    if not rows:
        # No OCR result — wizard shows blank form (non-blocking)
        return make_success_response({
            "booking_id": booking_id,
            "capture_type": capture_type,
            "result_id": None,
            "ocr_status": "none",
            "prefill_fields": {},
            "field_confidences": {},
            "low_confidence_fields": [],
            "quality_warnings": [],
            "overall_confidence": None,
            "document_type": None,
            "provider_used": None,
            "review_required": True,
        })

    row = rows[0]
    extracted = row.get("extracted_fields") or {}
    corrected = row.get("corrected_fields") or {}
    confidences = row.get("field_confidences") or {}

    # Merge: corrected_fields wins over extracted_fields
    prefill = {**extracted, **corrected}

    # Low confidence fields (threshold: 0.85)
    LOW_CONFIDENCE_THRESHOLD = 0.85
    low_confidence = [
        field for field, conf in confidences.items()
        if float(conf) < LOW_CONFIDENCE_THRESHOLD
    ]

    return make_success_response({
        "booking_id": booking_id,
        "capture_type": capture_type,
        "result_id": row["id"],
        "ocr_status": row["status"],
        "prefill_fields": prefill,
        "field_confidences": confidences,
        "low_confidence_fields": low_confidence,
        "quality_warnings": row.get("quality_warnings") or [],
        "overall_confidence": row.get("overall_confidence"),
        "document_type": row.get("document_type"),
        "provider_used": row.get("provider_used"),
        # INV-OCR-02: always require worker to review every pre-filled field
        "review_required": True,
    })


# ─── GET /admin/ocr/review-queue ──────────────────────────────────
@router.get("/admin/ocr/review-queue")
async def get_review_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    capture_type_filter: Optional[str] = Query(None, alias="capture_type"),
    limit: int = Query(50, ge=1, le=200),
    identity: dict = Depends(jwt_identity),
):
    """
    Admin: list OCR results needing review.

    Default: status=pending_review, sorted by created_at DESC.
    Filterable by status + capture_type.
    """
    tenant_id = identity.get("tenant_id", "")
    role = identity.get("role", "")

    if role not in ("admin", "manager"):
        return make_error_response(403, ErrorCode.FORBIDDEN, "Admin or manager role required")

    db = _get_supabase_client()

    query = (
        db.table("ocr_results")
        .select(
            "id, booking_id, capture_type, document_type, provider_used, "
            "status, overall_confidence, quality_warnings, created_at, "
            "reviewed_by, reviewed_at, error_message"
        )
        .eq("tenant_id", tenant_id)
    )

    if status_filter:
        query = query.eq("status", status_filter)
    else:
        query = query.eq("status", "pending_review")

    if capture_type_filter:
        query = query.eq("capture_type", capture_type_filter)

    resp = (
        query
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return make_success_response(
        resp.data or [],
        meta={"count": len(resp.data or [])},
    )
