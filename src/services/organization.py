"""
Organization Service — Phase 296
==================================

Pure service module for multi-tenant organization operations.

Rules:
- tenant_id (JWT sub) is NEVER replaced — the org layer is additive.
- All mutation functions return plain dicts (no custom exceptions from DB layer).
- Org creation automatically adds the creator as org_admin in org_members.
- tenant_org_map is maintained via DB trigger on org_members (sync_tenant_org_map).

Tables:
    organizations  — org_id, name, slug, created_by, created_at
    org_members    — org_id, tenant_id, role, invited_by
    tenant_org_map — tenant_id → org_id (read-optimized, trigger-maintained)
"""
from __future__ import annotations

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]$")


def _slugify(name: str) -> str:
    """Derive a URL-safe slug from an org name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:63]


def _is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------

def create_organization(
    db: Any,
    name: str,
    creator_tenant_id: str,
    description: str | None = None,
    slug: str | None = None,
) -> dict:
    """
    Create a new organization and enroll the creator as org_admin.

    Returns the created organization dict on success, or raises ValueError
    on validation failure or slug conflict.

    Args:
        db:                Supabase client.
        name:              Human-readable org name (1–100 chars).
        creator_tenant_id: JWT sub claim of the creating user.
        description:       Optional org description.
        slug:              Optional custom slug; auto-derived from name if omitted.

    Returns:
        dict with keys: org_id, name, slug, description, created_by, created_at
    """
    if not name or not name.strip():
        raise ValueError("Organization name must not be empty")
    if len(name) > 100:
        raise ValueError("Organization name must be ≤ 100 characters")

    derived_slug = slug.strip().lower() if slug else _slugify(name)
    if not _is_valid_slug(derived_slug):
        raise ValueError(
            f"Invalid slug '{derived_slug}'. "
            "Must be 3-63 characters, lowercase alphanumeric, hyphens and underscores. "
            "Must start and end with alphanumeric."
        )

    org_payload = {
        "name": name.strip(),
        "slug": derived_slug,
        "description": description,
        "created_by": creator_tenant_id,
    }

    try:
        res = db.table("organizations").insert(org_payload).execute()
    except Exception as exc:
        msg = str(exc)
        if "organizations_slug_key" in msg or "unique" in msg.lower():
            raise ValueError(f"Slug '{derived_slug}' is already taken. Choose a different name or slug.")
        logger.exception("Organization create error: %s", msg)
        raise

    org = res.data[0] if res.data else {}

    # Enroll creator as org_admin in org_members
    # (trigger sync_tenant_org_map will handle tenant_org_map automatically)
    member_payload = {
        "org_id": org["org_id"],
        "tenant_id": creator_tenant_id,
        "role": "org_admin",
        "invited_by": None,
    }
    try:
        db.table("org_members").insert(member_payload).execute()
    except Exception as exc:
        logger.exception("Failed to enroll creator in org_members: %s", exc)
        # Don't raise — org exists, membership failure is recoverable

    return org


def get_organization(db: Any, org_id: str) -> dict | None:
    """Fetch a single organization by org_id. Returns None if not found."""
    res = db.table("organizations").select("*").eq("org_id", org_id).execute()
    return res.data[0] if res.data else None


def get_org_for_tenant(db: Any, tenant_id: str) -> dict | None:
    """
    Look up the org that a tenant_id belongs to via tenant_org_map.
    Returns None if the tenant is not part of any org.
    """
    res = (
        db.table("tenant_org_map")
        .select("org_id, role")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        return None
    row = res.data[0]

    org = get_organization(db, row["org_id"])
    if org:
        org["caller_role"] = row["role"]
    return org


def list_orgs_for_tenant(db: Any, tenant_id: str) -> list[dict]:
    """
    Return all orgs a tenant belongs to (typically 0 or 1).
    Joins tenant_org_map → organizations.
    """
    res = (
        db.table("tenant_org_map")
        .select("org_id, role")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        return []

    results = []
    for row in res.data:
        org = get_organization(db, row["org_id"])
        if org:
            org["caller_role"] = row["role"]
            results.append(org)
    return results


# ---------------------------------------------------------------------------
# Membership CRUD
# ---------------------------------------------------------------------------

def add_org_member(
    db: Any,
    org_id: str,
    new_tenant_id: str,
    role: str,
    invited_by: str,
) -> dict:
    """
    Add a new member to an organization.

    Args:
        db:             Supabase client.
        org_id:         UUID of the target org.
        new_tenant_id:  tenant_id of the user to add.
        role:           'org_admin' | 'manager' | 'member'
        invited_by:     tenant_id of the inviting org_admin.

    Returns:
        The created org_members row.

    Raises:
        ValueError on invalid role or duplicate membership.
    """
    valid_roles = ("org_admin", "manager", "member")
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {valid_roles}")

    payload = {
        "org_id": org_id,
        "tenant_id": new_tenant_id,
        "role": role,
        "invited_by": invited_by,
    }
    try:
        res = db.table("org_members").insert(payload).execute()
    except Exception as exc:
        msg = str(exc)
        if "org_members_org_id_tenant_id_key" in msg or "unique" in msg.lower():
            raise ValueError(f"Tenant '{new_tenant_id}' is already a member of this org.")
        logger.exception("add_org_member error: %s", msg)
        raise

    return res.data[0] if res.data else {}


def list_org_members(db: Any, org_id: str) -> list[dict]:
    """Return all members of an organization."""
    res = (
        db.table("org_members")
        .select("id, tenant_id, role, invited_by, joined_at")
        .eq("org_id", org_id)
        .order("joined_at")
        .execute()
    )
    return res.data or []


def remove_org_member(db: Any, org_id: str, tenant_id: str) -> bool:
    """
    Remove a member from an org.
    Returns True if a row was deleted, False if not found.
    """
    res = (
        db.table("org_members")
        .delete()
        .eq("org_id", org_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return bool(res.data)


def is_org_admin(db: Any, org_id: str, tenant_id: str) -> bool:
    """
    Return True if the given tenant_id has the 'org_admin' role in the org.
    Best-effort: returns False on any error.
    """
    try:
        res = (
            db.table("org_members")
            .select("role")
            .eq("org_id", org_id)
            .eq("tenant_id", tenant_id)
            .eq("role", "org_admin")
            .execute()
        )
        return bool(res.data)
    except Exception:  # noqa: BLE001
        return False
