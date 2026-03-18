"""
Phase 844 v3 — Admin Owners Router

Manages owner entities and their property assignments.
Owners are separate from system auth users (role=owner).
This is an admin-managed profile + linkage surface.

Endpoints:
    GET    /admin/owners                       — list all owners with property counts
    POST   /admin/owners                       — create owner
    PATCH  /admin/owners/{owner_id}            — update owner
    DELETE /admin/owners/{owner_id}            — delete owner
    GET    /admin/owners/{owner_id}/properties — list assigned properties
    POST   /admin/owners/{owner_id}/properties — assign property to owner
    DELETE /admin/owners/{owner_id}/properties/{property_id} — remove linkage
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/owners", tags=["admin-owners"])


def _db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ---------------------------------------------------------------------------
# GET /admin/owners
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List all owners with property counts (Phase 844)",
    responses={200: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_owners(tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    try:
        db = _db()
        owners_res = (
            db.table("owners")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("name")
            .execute()
        )
        owners: List[Dict] = owners_res.data or []

        if not owners:
            return JSONResponse(status_code=200, content={"owners": []})

        # Fetch property linkages for all owners
        owner_ids = [o["id"] for o in owners]
        po_res = (
            db.table("property_owners")
            .select("owner_id, property_id")
            .in_("owner_id", owner_ids)
            .execute()
        )
        po_rows: List[Dict] = po_res.data or []

        # Build property list per owner
        from collections import defaultdict
        props_by_owner: Dict[str, List[str]] = defaultdict(list)
        for po in po_rows:
            props_by_owner[po["owner_id"]].append(po["property_id"])

        for o in owners:
            o["property_ids"] = props_by_owner.get(o["id"], [])
            o["property_count"] = len(o["property_ids"])

        return JSONResponse(status_code=200, content={"owners": owners})

    except Exception as exc:
        logger.exception("list_owners: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /admin/owners
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Create owner (Phase 844)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_owner(body: Dict[str, Any], tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    name = str(body.get("name") or "").strip()
    if not name:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'name' is required."})

    row = {
        "tenant_id": tenant_id,
        "name": name,
        "phone": str(body.get("phone") or "").strip() or None,
        "email": str(body.get("email") or "").strip() or None,
        "notes": str(body.get("notes") or "").strip() or None,
    }

    try:
        db = _db()
        res = db.table("owners").insert(row).execute()
        owner = res.data[0] if res.data else {}
        owner["property_ids"] = []
        owner["property_count"] = 0
        owner["skipped_properties"] = []
        owner["warnings"] = []

        # Optionally assign initial property_ids — enforce one-owner-per-property
        initial_props: List[str] = body.get("property_ids") or []
        if initial_props and owner.get("id"):
            # Check which properties already have an owner
            existing = db.table("property_owners") \
                .select("property_id") \
                .in_("property_id", initial_props) \
                .execute()
            already_owned = {r["property_id"] for r in (existing.data or [])}
            assignable = [pid for pid in initial_props if pid not in already_owned]
            skipped = [pid for pid in initial_props if pid in already_owned]

            if skipped:
                owner["skipped_properties"] = [
                    {"property_id": pid, "reason": "already has an owner"}
                    for pid in skipped
                ]
                owner["warnings"].append(
                    f"{len(skipped)} propert{'ies were' if len(skipped) > 1 else 'y was'} "
                    f"not assigned because {'they' if len(skipped) > 1 else 'it'} already "
                    f"{'have' if len(skipped) > 1 else 'has'} an owner."
                )

            if assignable:
                try:
                    po_rows = [{"owner_id": owner["id"], "property_id": pid}
                               for pid in assignable]
                    db.table("property_owners").insert(po_rows).execute()
                    owner["property_ids"] = assignable
                    owner["property_count"] = len(assignable)
                except Exception as link_exc:
                    logger.exception("create_owner: property linkage failed: %s", link_exc)
                    owner["warnings"].append(
                        "Owner was created but property assignment failed. "
                        "Please assign properties manually from the owner card."
                    )

        return JSONResponse(status_code=201, content=owner)

    except Exception as exc:
        logger.exception("create_owner: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /admin/owners/{owner_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/{owner_id}",
    summary="Update owner (Phase 844)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_owner(owner_id: str, body: Dict[str, Any],
                       tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    allowed_fields = {"name", "phone", "email", "notes"}
    patch = {k: v for k, v in body.items() if k in allowed_fields}
    if not patch:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "No valid fields to update."})

    try:
        db = _db()
        res = (
            db.table("owners")
            .update(patch)
            .eq("id", owner_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not res.data:
            return make_error_response(status_code=404, code="NOT_FOUND")
        return JSONResponse(status_code=200, content=res.data[0])
    except Exception as exc:
        logger.exception("update_owner: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /admin/owners/{owner_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{owner_id}",
    summary="Delete owner (Phase 844)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_owner(owner_id: str, tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    try:
        db = _db()
        res = (
            db.table("owners").delete()
            .eq("id", owner_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not res.data:
            return make_error_response(status_code=404, code="NOT_FOUND")
        return JSONResponse(status_code=200, content={"deleted": True, "owner_id": owner_id})
    except Exception as exc:
        logger.exception("delete_owner: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /admin/owners/{owner_id}/properties
# ---------------------------------------------------------------------------

@router.post(
    "/{owner_id}/properties",
    summary="Assign property to owner (Phase 844)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def assign_property(owner_id: str, body: Dict[str, Any],
                          tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    property_id = str(body.get("property_id") or "").strip()
    if not property_id:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'property_id' is required."})
    try:
        db = _db()
        # Verify owner belongs to caller's tenant
        owner_check = db.table("owners").select("id").eq("id", owner_id).eq("tenant_id", tenant_id).execute()
        if not owner_check.data:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Owner not found."})
        # Enforce one-owner-per-property rule
        existing = db.table("property_owners") \
            .select("owner_id") \
            .eq("property_id", property_id) \
            .execute()
        if existing.data:
            current_owner_id = existing.data[0]["owner_id"]
            if current_owner_id == owner_id:
                # Already assigned to this owner — idempotent return
                return JSONResponse(status_code=200,
                                   content={"owner_id": owner_id, "property_id": property_id,
                                            "note": "already assigned"})
            return make_error_response(
                status_code=409,
                code=ErrorCode.CONFLICT,
                extra={"detail": "Property already has an owner. Remove the existing owner first.",
                       "existing_owner_id": current_owner_id}
            )
        res = db.table("property_owners").insert({
            "owner_id": owner_id, "property_id": property_id,
        }).execute()
        return JSONResponse(status_code=201, content=res.data[0] if res.data else {})
    except Exception as exc:
        logger.exception("assign_property: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /admin/owners/{owner_id}/properties/{property_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{owner_id}/properties/{property_id}",
    summary="Remove property assignment from owner (Phase 844)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def remove_property(owner_id: str, property_id: str,
                          tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    try:
        db = _db()
        # Verify owner belongs to caller's tenant
        owner_check = db.table("owners").select("id").eq("id", owner_id).eq("tenant_id", tenant_id).execute()
        if not owner_check.data:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Owner not found."})
        res = (
            db.table("property_owners").delete()
            .eq("owner_id", owner_id)
            .eq("property_id", property_id)
            .execute()
        )
        if not res.data:
            return make_error_response(status_code=404, code="NOT_FOUND")
        return JSONResponse(status_code=200, content={"removed": True})
    except Exception as exc:
        logger.exception("remove_property: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
