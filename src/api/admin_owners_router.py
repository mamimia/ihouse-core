"""
Phase 844 v3 — Admin Owners Router
Phase 1021-B — Owner model unification: user_id link support

Manages owner entities and their property assignments.

Design (Phase 1021):
  An Owner record is the canonical BUSINESS/FINANCIAL profile for a property owner.
  It may optionally be linked to a login account (tenant_permissions.user_id).

  - owners.user_id = NULL       → contact-only owner, no app login (valid and intentional)
  - owners.user_id = <JWT sub>  → explicitly linked to a login account by an admin

  This link is NEVER auto-created. Admin sets it intentionally.

Endpoints:
    GET    /admin/owners                         — list all owners with property counts
    GET    /admin/owners/by-user/{user_id}       — get owner profile linked to a login account [Phase 1021]
    GET    /admin/owners/linkable-staff          — list owner-role staff not yet linked [Phase 1021]
    POST   /admin/owners                         — create owner
    PATCH  /admin/owners/{owner_id}              — update owner (incl. user_id link/unlink) [Phase 1021]
    DELETE /admin/owners/{owner_id}              — delete owner
    GET    /admin/owners/{owner_id}/properties   — list assigned properties
    POST   /admin/owners/{owner_id}/properties   — assign property to owner
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


def _enrich_owners(db: Any, owners: List[Dict]) -> List[Dict]:
    """
    Given a list of owner rows, attach:
      - property_ids / property_count from property_owners
      - linked_account (display_name + is_active) from tenant_permissions when user_id is set
    """
    if not owners:
        return owners

    owner_ids = [o["id"] for o in owners]

    # Property linkages
    po_res = (
        db.table("property_owners")
        .select("owner_id, property_id")
        .in_("owner_id", owner_ids)
        .execute()
    )
    from collections import defaultdict
    props_by_owner: Dict[str, List[str]] = defaultdict(list)
    for po in (po_res.data or []):
        props_by_owner[po["owner_id"]].append(po["property_id"])

    # Linked staff accounts (for owners that have user_id set)
    linked_user_ids = [o["user_id"] for o in owners if o.get("user_id")]
    staff_by_user: Dict[str, Dict] = {}
    if linked_user_ids:
        try:
            tp_res = (
                db.table("tenant_permissions")
                .select("user_id, display_name, is_active, comm_preference")
                .in_("user_id", linked_user_ids)
                .execute()
            )
            for row in (tp_res.data or []):
                comm = row.get("comm_preference") or {}
                staff_by_user[row["user_id"]] = {
                    "user_id": row["user_id"],
                    "display_name": row.get("display_name") or "",
                    "email": comm.get("email") or "",
                    "is_active": row.get("is_active", True),
                }
        except Exception as exc:
            logger.warning("_enrich_owners: failed to fetch linked staff: %s", exc)

    for o in owners:
        o["property_ids"] = props_by_owner.get(o["id"], [])
        o["property_count"] = len(o["property_ids"])
        uid = o.get("user_id")
        o["linked_account"] = staff_by_user.get(uid) if uid else None

    return owners


# ---------------------------------------------------------------------------
# GET /admin/owners
# ---------------------------------------------------------------------------

@router.get(
    "",
    summary="List all owners with property counts and linked account info (Phase 844 / 1021)",
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
        owners = _enrich_owners(db, owners)
        return JSONResponse(status_code=200, content={"owners": owners})
    except Exception as exc:
        logger.exception("list_owners: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/owners/by-user/{user_id}  [Phase 1021]
# ---------------------------------------------------------------------------

@router.get(
    "/by-user/{user_id}",
    summary="Get the owner profile linked to a given login account [Phase 1021]",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_owner_by_user(user_id: str, tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    try:
        db = _db()
        res = (
            db.table("owners")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return JSONResponse(status_code=404, content={"linked": False})
        owners = _enrich_owners(db, [res.data])
        return JSONResponse(status_code=200, content={"linked": True, "owner": owners[0]})
    except Exception as exc:
        logger.exception("get_owner_by_user: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/owners/linkable-staff  [Phase 1021]
# ---------------------------------------------------------------------------

@router.get(
    "/linkable-staff",
    summary="List owner-role staff accounts not yet linked to an owner profile [Phase 1021]",
    responses={200: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_linkable_staff(tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    """
    Returns tenant_permissions rows where role='owner' and user_id is NOT
    already linked to an owners profile. Used for the 'Link to Staff Account'
    dropdown in the Owners UI.
    """
    try:
        db = _db()
        # All owner-role staff
        tp_res = (
            db.table("tenant_permissions")
            .select("user_id, display_name, is_active, comm_preference")
            .eq("tenant_id", tenant_id)
            .eq("role", "owner")
            .execute()
        )
        all_owner_staff = tp_res.data or []

        # Already-linked user_ids
        linked_res = (
            db.table("owners")
            .select("user_id")
            .eq("tenant_id", tenant_id)
            .not_.is_("user_id", "null")
            .execute()
        )
        already_linked = {r["user_id"] for r in (linked_res.data or []) if r.get("user_id")}

        linkable = []
        for row in all_owner_staff:
            uid = row.get("user_id")
            if uid and uid not in already_linked:
                comm = row.get("comm_preference") or {}
                linkable.append({
                    "user_id": uid,
                    "display_name": row.get("display_name") or "",
                    "email": comm.get("email") or "",
                    "is_active": row.get("is_active", True),
                })

        return JSONResponse(status_code=200, content={"staff": linkable})
    except Exception as exc:
        logger.exception("list_linkable_staff: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /admin/owners
# ---------------------------------------------------------------------------

@router.post(
    "",
    summary="Create owner (Phase 844 / 1021)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_owner(body: Dict[str, Any], tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    name = str(body.get("name") or "").strip()
    if not name:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'name' is required."})

    # Phase 1021: optional user_id link at creation time
    user_id_raw = str(body.get("user_id") or "").strip() or None

    row: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "name": name,
        "phone": str(body.get("phone") or "").strip() or None,
        "email": str(body.get("email") or "").strip() or None,
        "notes": str(body.get("notes") or "").strip() or None,
        "user_id": user_id_raw,
    }

    try:
        db = _db()

        # Guard: user_id uniqueness (partial index enforces at DB level, but give a clean error)
        if user_id_raw:
            existing_link = (
                db.table("owners")
                .select("id, name")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id_raw)
                .execute()
            )
            if existing_link.data:
                return make_error_response(
                    status_code=409, code=ErrorCode.CONFLICT,
                    extra={"detail": f"That account is already linked to owner '{existing_link.data[0]['name']}'."}
                )

        res = db.table("owners").insert(row).execute()
        owner = res.data[0] if res.data else {}
        owner["skipped_properties"] = []
        owner["warnings"] = []

        # Optionally assign initial property_ids — enforce one-owner-per-property
        initial_props: List[str] = body.get("property_ids") or []
        if initial_props and owner.get("id"):
            existing_po = db.table("property_owners") \
                .select("property_id") \
                .in_("property_id", initial_props) \
                .execute()
            already_owned = {r["property_id"] for r in (existing_po.data or [])}
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
        else:
            owner["property_ids"] = []
            owner["property_count"] = 0

        # Resolve linked_account for response
        owner["linked_account"] = None
        if user_id_raw:
            try:
                tp = (
                    db.table("tenant_permissions")
                    .select("user_id, display_name, is_active, comm_preference")
                    .eq("user_id", user_id_raw)
                    .maybe_single()
                    .execute()
                )
                if tp.data:
                    comm = tp.data.get("comm_preference") or {}
                    owner["linked_account"] = {
                        "user_id": user_id_raw,
                        "display_name": tp.data.get("display_name") or "",
                        "email": comm.get("email") or "",
                        "is_active": tp.data.get("is_active", True),
                    }
            except Exception:
                pass

        return JSONResponse(status_code=201, content=owner)

    except Exception as exc:
        logger.exception("create_owner: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /admin/owners/{owner_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/{owner_id}",
    summary="Update owner profile, incl. user_id link/unlink (Phase 844 / 1021)",
    responses={200: {}, 404: {}, 409: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_owner(owner_id: str, body: Dict[str, Any],
                       tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    """
    Phase 1021: In addition to name/phone/email/notes, this endpoint now accepts:
      - user_id: "<JWT sub>"  → link this owner profile to a login account
      - user_id: null         → explicit unlink (admin intent required)

    The sentinel string "__unlink__" is also accepted from the frontend to
    differentiate "explicitly set to null" from "field not sent".
    """
    allowed_scalar = {"name", "phone", "email", "notes"}
    patch: Dict[str, Any] = {k: v for k, v in body.items() if k in allowed_scalar}

    # Phase 1021: handle user_id link/unlink explicitly
    user_id_in_body = "user_id" in body
    new_user_id: Optional[str] = None
    unlinking = False

    if user_id_in_body:
        raw = body["user_id"]
        if raw is None or raw == "__unlink__":
            # Explicit unlink
            patch["user_id"] = None
            unlinking = True
        else:
            new_user_id = str(raw).strip() or None
            if new_user_id:
                patch["user_id"] = new_user_id
            else:
                patch["user_id"] = None
                unlinking = True

    if not patch:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "No valid fields to update."})

    try:
        db = _db()

        # Guard: if setting a new user_id, check it isn't already linked to another owner
        if new_user_id and not unlinking:
            existing_link = (
                db.table("owners")
                .select("id, name")
                .eq("tenant_id", tenant_id)
                .eq("user_id", new_user_id)
                .neq("id", owner_id)  # exclude self
                .execute()
            )
            if existing_link.data:
                return make_error_response(
                    status_code=409, code=ErrorCode.CONFLICT,
                    extra={"detail": f"That account is already linked to owner '{existing_link.data[0]['name']}'."}
                )

        res = (
            db.table("owners")
            .update(patch)
            .eq("id", owner_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        if not res.data:
            return make_error_response(status_code=404, code="NOT_FOUND")

        owner = res.data[0]
        owners = _enrich_owners(db, [owner])
        result = owners[0]

        # Phase 1021: attach unlink_warning if admin just unlinked
        if unlinking:
            result["unlink_warning"] = (
                "This owner profile has been unlinked from the login account. "
                "Note: the user's owner portal property access (if any) was NOT removed automatically. "
                "Manage portal access separately from the Linked Account & Portal Access section."
            )

        return JSONResponse(status_code=200, content=result)
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
        owner_check = db.table("owners").select("id").eq("id", owner_id).eq("tenant_id", tenant_id).execute()
        if not owner_check.data:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Owner not found."})
        existing = db.table("property_owners") \
            .select("owner_id") \
            .eq("property_id", property_id) \
            .execute()
        if existing.data:
            current_owner_id = existing.data[0]["owner_id"]
            if current_owner_id == owner_id:
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
