"""
Phase 862 (Canonical Auth P7) — Canonical Role Registry
=========================================================

Single source of truth for all valid role values in the system.

All files that validate roles MUST import from this module.
Do NOT define local _VALID_ROLES sets elsewhere.

The role hierarchy (from highest to lowest access):
    admin           — full tenant governance
    manager         — operational management (legacy term for ops_manager)
    ops             — operational team member
    owner           — property owner (business visibility)
    worker          — general staff
    cleaner         — housekeeping staff
    checkin         — check-in staff
    checkout        — check-out staff
    maintenance     — maintenance staff

System-level access classes (not tenant roles):
    identity_only   — authenticated but no tenant membership

Future additions (not yet implemented):
    submitter       — property intake / Get Started users
    ops_manager     — explicit operational manager (replacing 'manager')
    guest           — temporary stay-scoped access
"""
from __future__ import annotations

# ─── Canonical Role Set ───
# Every role that can appear in tenant_permissions.role
CANONICAL_ROLES: frozenset[str] = frozenset({
    "admin",
    "manager",
    "ops",
    "owner",
    "worker",
    "cleaner",
    "checkin",
    "checkout",
    "maintenance",
})

# Roles that get full access to all UI surfaces
FULL_ACCESS_ROLES: frozenset[str] = frozenset({"admin", "manager"})

# Roles that represent operational staff (task-assignable)
STAFF_ROLES: frozenset[str] = frozenset({
    "worker", "cleaner", "checkin", "checkout", "maintenance", "ops",
})

# Roles that can be assigned via admin invite
INVITABLE_ROLES: frozenset[str] = CANONICAL_ROLES - frozenset({"admin"})

# ─── System Access Classes ───
# These are NOT tenant roles — they describe identity-level access
# for users who may not have any tenant_permissions row.
IDENTITY_ONLY = "identity_only"  # Phase 862 P28
