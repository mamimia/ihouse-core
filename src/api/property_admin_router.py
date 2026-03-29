"""
Phase 396 — Property Admin Approval Dashboard

Admin endpoints for managing properties submitted through the onboarding wizard.

Endpoints:
    GET    /admin/properties                   — list all properties (filterable)
    GET    /admin/properties/{property_id}     — single property detail
    PATCH  /admin/properties/{property_id}     — update mutable property fields (Phase 397)
    POST   /admin/properties/{property_id}/approve  — approve a pending property
    POST   /admin/properties/{property_id}/reject   — reject a pending property
    POST   /admin/properties/{property_id}/archive  — archive a property

Rules:
    - JWT auth required on all endpoints.
    - All queries are tenant-scoped via tenant_id from JWT.
    - State transitions: pending → approved | rejected; approved → archived.
    - All mutations are audit-logged via admin_audit_log.
    - Channel map data is included in detail responses.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin-properties"])

# Valid property statuses and allowed transitions
_VALID_STATUSES = frozenset({"pending", "approved", "rejected", "archived"})
_APPROVE_FROM = frozenset({"pending"})
_REJECT_FROM = frozenset({"pending"})
_ARCHIVE_FROM = frozenset({"approved"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Audit helper (reuses admin_router.write_audit_event pattern)
# ---------------------------------------------------------------------------

def _write_audit_event(
    db: Any,
    *,
    tenant_id: str,
    actor: str,
    action: str,
    property_id: str,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
) -> bool:
    """Append property admin action to admin_audit_log. Best-effort."""
    row: dict = {
        "tenant_id": tenant_id,
        "actor_user_id": actor,
        "action": action,
        "target_type": "property",
        "target_id": property_id,
        "metadata": {},
    }
    if before_state is not None:
        row["before_state"] = before_state
    if after_state is not None:
        row["after_state"] = after_state
    try:
        db.table("admin_audit_log").insert(row).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_write_audit_event failed tenant=%s action=%s: %s",
            tenant_id, action, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Property select columns
# ---------------------------------------------------------------------------

_PROPERTY_COLS = (
    "property_id, tenant_id, display_name, timezone, base_currency, "
    "property_type, city, country, max_guests, bedrooms, beds, bathrooms, "
    "address, description, source_url, source_platform, "
    "status, approved_at, approved_by, archived_at, archived_by, "
    "created_at, self_checkin_config"
)


def _serialize_property(row: dict) -> dict:
    """Normalize a property row for API response."""
    return {
        "property_id": row.get("property_id"),
        "tenant_id": row.get("tenant_id"),
        "display_name": row.get("display_name"),
        "timezone": row.get("timezone", "UTC"),
        "base_currency": row.get("base_currency", "USD"),
        "property_type": row.get("property_type"),
        "city": row.get("city"),
        "country": row.get("country"),
        "max_guests": row.get("max_guests"),
        "bedrooms": row.get("bedrooms"),
        "beds": row.get("beds"),
        "bathrooms": row.get("bathrooms"),
        "address": row.get("address"),
        "description": row.get("description"),
        "source_url": row.get("source_url"),
        "source_platform": row.get("source_platform"),
        "status": row.get("status", "pending"),
        "approved_at": row.get("approved_at"),
        "approved_by": row.get("approved_by"),
        "archived_at": row.get("archived_at"),
        "archived_by": row.get("archived_by"),
        "created_at": row.get("created_at"),
        # Phase 1019: Self check-in mode — needed for badge in Properties list
        "self_checkin_config": row.get("self_checkin_config"),
    }


# ---------------------------------------------------------------------------
# GET /admin/properties — list all properties
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties",
    tags=["admin-properties"],
    summary="List properties with optional filters (Phase 396)",
    description=(
        "Returns all properties for this tenant.\\n\\n"
        "Filterable by `status` (pending/approved/rejected/archived), "
        "`search` (ilike on display_name, property_id, city).\\n\\n"
        "Ordered by created_at DESC. Default limit 100, max 500."
    ),
    responses={
        200: {"description": "Properties list"},
        400: {"description": "Invalid filter value"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_properties(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /admin/properties — list with filters."""
    if status is not None and status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Invalid status '{status}'. Valid: {sorted(_VALID_STATUSES)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("properties")
            .select(_PROPERTY_COLS)
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )

        if status is not None:
            query = query.eq("status", status)

        if search is not None and search.strip():
            # Supabase ilike filter on display_name
            query = query.ilike("display_name", f"%{search.strip()}%")

        result = query.execute()
        rows = result.data or []

        # Count totals for pagination
        count_query = (
            db.table("properties")
            .select("property_id", count="exact")
            .eq("tenant_id", tenant_id)
        )
        if status is not None:
            count_query = count_query.eq("status", status)
        count_result = count_query.execute()
        total = count_result.count if hasattr(count_result, "count") and count_result.count is not None else len(rows)

        # Status summary
        summary_rows = (
            db.table("properties")
            .select("status")
            .eq("tenant_id", tenant_id)
            .execute()
        ).data or []

        status_counts: Dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0, "archived": 0}
        for r in summary_rows:
            s = r.get("status", "pending")
            if s in status_counts:
                status_counts[s] += 1

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/properties error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "properties": [_serialize_property(r) for r in rows],
            "count": len(rows),
            "total": total,
            "offset": offset,
            "limit": limit,
            "status_summary": status_counts,
        },
    )


# ---------------------------------------------------------------------------
# GET /admin/properties/{property_id} — detail
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties/{property_id}",
    tags=["admin-properties"],
    summary="Property detail with channel mappings (Phase 396)",
    description=(
        "Returns full property detail including channel_map entries.\\n\\n"
        "Tenant-scoped. Returns 404 if property not found for this tenant."
    ),
    responses={
        200: {"description": "Property detail with channels"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Property not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_detail(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /admin/properties/{property_id} — detail + channels."""
    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch property
        prop_result = (
            db.table("properties")
            .select(_PROPERTY_COLS)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_result.data or []

        if not prop_rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"detail": f"Property '{property_id}' not found."},
            )

        prop = _serialize_property(prop_rows[0])

        # Fetch channel_map entries
        cm_result = (
            db.table("channel_map")
            .select("provider, external_channel_id, active, source_url")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        channels = cm_result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/properties/%s error tenant=%s: %s", property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    prop["channels"] = channels
    return JSONResponse(status_code=200, content=prop)


# ---------------------------------------------------------------------------
# POST /admin/properties/{property_id}/approve
# ---------------------------------------------------------------------------

@router.post(
    "/admin/properties/{property_id}/approve",
    tags=["admin-properties"],
    summary="Approve a pending property (Phase 396)",
    description=(
        "Transitions a property from `pending` → `approved`.\\n\\n"
        "Sets `approved_at` and `approved_by`. Audit-logged."
    ),
    responses={
        200: {"description": "Property approved"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Property not found"},
        409: {"description": "Property is not in pending status"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """POST /admin/properties/{property_id}/approve.

    Approves the property AND auto-provisions a channel_map entry (Phase 404).
    """
    result = await _transition_property(
        property_id=property_id,
        tenant_id=tenant_id,
        target_status="approved",
        allowed_from=_APPROVE_FROM,
        action="approve_property",
        extra_fields={
            "approved_at": datetime.now(tz=timezone.utc).isoformat(),
            "approved_by": tenant_id,
        },
        client=client,
    )

    # Phase 404: Post-approval channel map provisioning
    if result.status_code == 200:
        try:
            db = client if client is not None else _get_supabase_client()

            # Check if channel_map already exists for this property
            existing = (
                db.table("property_channel_map")
                .select("property_id")
                .eq("property_id", property_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )

            if not (existing.data or []):
                # Auto-create a default channel map entry
                db.table("property_channel_map").insert({
                    "property_id": property_id,
                    "tenant_id": tenant_id,
                    "channels": [],  # Empty — admin will configure channels later
                    "sync_enabled": False,  # Not auto-enabled — explicit action needed
                    "provisioned_at": datetime.now(tz=timezone.utc).isoformat(),
                    "provisioned_by": "system:auto_approve",
                }).execute()

                logger.info(
                    "approve: auto-provisioned channel_map for property=%s tenant=%s",
                    property_id, tenant_id,
                )

                # Update response to flag channel provisioning
                import json
                body = json.loads(result.body)
                body["channel_map_provisioned"] = True
                result = JSONResponse(status_code=200, content=body)

        except Exception as exc:
            logger.warning(
                "approve: channel_map auto-provision failed for property=%s: %s",
                property_id, exc,
            )
            # Non-fatal: approval stands even if channel map fails

    return result


# ---------------------------------------------------------------------------
# POST /admin/properties/{property_id}/reject
# ---------------------------------------------------------------------------

@router.post(
    "/admin/properties/{property_id}/reject",
    tags=["admin-properties"],
    summary="Reject a pending property (Phase 396)",
    description=(
        "Transitions a property from `pending` → `rejected`.\\n\\n"
        "Audit-logged."
    ),
    responses={
        200: {"description": "Property rejected"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Property not found"},
        409: {"description": "Property is not in pending status"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def reject_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """POST /admin/properties/{property_id}/reject."""
    return await _transition_property(
        property_id=property_id,
        tenant_id=tenant_id,
        target_status="rejected",
        allowed_from=_REJECT_FROM,
        action="reject_property",
        extra_fields={},
        client=client,
    )


# ---------------------------------------------------------------------------
# POST /admin/properties/{property_id}/archive
# ---------------------------------------------------------------------------

@router.post(
    "/admin/properties/{property_id}/archive",
    tags=["admin-properties"],
    summary="Archive an approved property (Phase 396)",
    description=(
        "Transitions a property from `approved` → `archived`.\\n\\n"
        "Sets `archived_at` and `archived_by`. Audit-logged."
    ),
    responses={
        200: {"description": "Property archived"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Property not found"},
        409: {"description": "Property is not in approved status"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def archive_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """POST /admin/properties/{property_id}/archive."""
    return await _transition_property(
        property_id=property_id,
        tenant_id=tenant_id,
        target_status="archived",
        allowed_from=_ARCHIVE_FROM,
        action="archive_property",
        extra_fields={
            "archived_at": datetime.now(tz=timezone.utc).isoformat(),
            "archived_by": tenant_id,
        },
        client=client,
    )


# ---------------------------------------------------------------------------
# Shared transition logic
# ---------------------------------------------------------------------------

# Mutable fields that can be updated via PATCH
_MUTABLE_FIELDS = frozenset({
    "display_name", "timezone", "base_currency",
    "property_type", "city", "country",
    "max_guests", "bedrooms", "beds", "bathrooms",
    "address", "description",
})

# Statuses that allow editing
_EDITABLE_FROM = frozenset({"pending", "approved"})


# ---------------------------------------------------------------------------
# PATCH /admin/properties/{property_id} — edit mutable fields (Phase 397)
# ---------------------------------------------------------------------------

@router.patch(
    "/admin/properties/{property_id}",
    tags=["admin-properties"],
    summary="Update mutable property fields (Phase 397)",
    description=(
        "Updates mutable fields on a property.\\n\\n"
        "Only properties with status `pending` or `approved` can be edited.\\n\\n"
        "Immutable fields (`property_id`, `tenant_id`, `status`) are ignored.\\n\\n"
        "Audit-logged."
    ),
    responses={
        200: {"description": "Property updated"},
        400: {"description": "No valid fields in body"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Property not found"},
        409: {"description": "Property status does not allow editing"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def patch_property(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """PATCH /admin/properties/{property_id} — edit mutable fields."""
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    # Filter to mutable fields only
    update_data: Dict[str, Any] = {}
    for key, value in body.items():
        if key in _MUTABLE_FIELDS:
            # Type coercions for numeric fields
            if key in ("max_guests", "bedrooms", "beds"):
                if value is not None:
                    try:
                        update_data[key] = int(value)
                    except (ValueError, TypeError):
                        continue
                else:
                    update_data[key] = None
            elif key == "bathrooms":
                if value is not None:
                    try:
                        update_data[key] = float(value)
                    except (ValueError, TypeError):
                        continue
                else:
                    update_data[key] = None
            elif isinstance(value, str):
                update_data[key] = value.strip() or None
            else:
                update_data[key] = value

    if not update_data:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"No valid mutable fields provided. Allowed: {sorted(_MUTABLE_FIELDS)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch current state
        prop_result = (
            db.table("properties")
            .select(_PROPERTY_COLS)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_result.data or []

        if not prop_rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"detail": f"Property '{property_id}' not found."},
            )

        current = prop_rows[0]
        current_status = current.get("status", "pending")

        if current_status not in _EDITABLE_FROM:
            return make_error_response(
                status_code=409,
                code="CONFLICT",
                extra={
                    "detail": (
                        f"Cannot edit property — status is '{current_status}'. "
                        f"Only {sorted(_EDITABLE_FROM)} properties can be edited."
                    ),
                    "current_status": current_status,
                },
            )

        # Apply update
        updated_result = (
            db.table("properties")
            .update(update_data)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        updated_rows = updated_result.data or []
        updated = updated_rows[0] if updated_rows else {**current, **update_data}

        # Build before/after for audit
        before = {k: current.get(k) for k in update_data}
        after = {k: update_data[k] for k in update_data}

        _write_audit_event(
            db,
            tenant_id=tenant_id,
            actor=tenant_id,
            action="edit_property",
            property_id=property_id,
            before_state=before,
            after_state=after,
        )

        return JSONResponse(
            status_code=200,
            content={
                "property_id": property_id,
                "updated_fields": list(update_data.keys()),
                "detail": _serialize_property(updated),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PATCH /admin/properties/%s error tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


async def _transition_property(
    *,
    property_id: str,
    tenant_id: str,
    target_status: str,
    allowed_from: frozenset,
    action: str,
    extra_fields: dict,
    client: Optional[Any] = None,
) -> JSONResponse:
    """Generic property state transition with audit logging."""
    try:
        db = client if client is not None else _get_supabase_client()

        # 1. Fetch current state
        prop_result = (
            db.table("properties")
            .select(_PROPERTY_COLS)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_result.data or []

        if not prop_rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"detail": f"Property '{property_id}' not found."},
            )

        current = prop_rows[0]
        current_status = current.get("status", "pending")

        # 2. Validate transition
        if current_status not in allowed_from:
            return make_error_response(
                status_code=409,
                code="CONFLICT",
                extra={
                    "detail": (
                        f"Cannot {action.replace('_', ' ')} — property is '{current_status}', "
                        f"expected one of: {sorted(allowed_from)}."
                    ),
                    "current_status": current_status,
                },
            )

        # 3. Apply transition
        update_data: Dict[str, Any] = {"status": target_status}
        update_data.update(extra_fields)

        updated_result = (
            db.table("properties")
            .update(update_data)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        updated_rows = updated_result.data or []
        updated = updated_rows[0] if updated_rows else {**current, **update_data}

        # 4. Audit log
        _write_audit_event(
            db,
            tenant_id=tenant_id,
            actor=tenant_id,
            action=action,
            property_id=property_id,
            before_state={"status": current_status},
            after_state={"status": target_status},
        )

        return JSONResponse(
            status_code=200,
            content={
                "property_id": property_id,
                "previous_status": current_status,
                "status": target_status,
                "detail": _serialize_property(updated),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "%s error property=%s tenant=%s: %s",
            action, property_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
