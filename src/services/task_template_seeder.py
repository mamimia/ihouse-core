"""
Phase 489 — Task Template Seed Service

Seeds the task_templates table with default operational task templates.
These templates drive the task automator to create appropriate tasks
for each booking event type.

Currently task_templates = 0 rows. This fills that gap.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.task_template_seeder")

# Default templates for a property management operation
DEFAULT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "title": "Standard Cleaning",
        "kind": "CLEANING",
        "priority": "high",
        "estimated_minutes": 120,
        "trigger_event": "BOOKING_CHECKED_OUT",
        "instructions": (
            "Full clean after guest checkout: linens, bathroom, kitchen, "
            "floors, restock amenities, take photos."
        ),
    },
    {
        "title": "Pre-Arrival Inspection",
        "kind": "CHECKIN_PREP",
        "priority": "high",
        "estimated_minutes": 30,
        "trigger_event": "BOOKING_CREATED",
        "instructions": (
            "Verify property is ready for guest arrival: check AC, water, "
            "WiFi, amenities stocked, key/lockbox instructions prepared."
        ),
    },
    {
        "title": "Guest Welcome",
        "kind": "GUEST_WELCOME",
        "priority": "normal",
        "estimated_minutes": 45,
        "trigger_event": "BOOKING_CREATED",
        "instructions": (
            "Welcome guest on arrival: provide property tour, explain "
            "house rules, share local recommendations, confirm check-out time."
        ),
    },
    {
        "title": "Maintenance Check",
        "kind": "MAINTENANCE",
        "priority": "normal",
        "estimated_minutes": 60,
        "trigger_event": None,
        "instructions": (
            "Monthly property maintenance: check HVAC filters, plumbing, "
            "electrical, pool/garden, report any issues."
        ),
    },
    {
        "title": "VIP Setup",
        "kind": "VIP_PREP",
        "priority": "critical",
        "estimated_minutes": 60,
        "trigger_event": "BOOKING_CREATED",
        "instructions": (
            "VIP guest preparation: premium amenities, welcome basket, "
            "flowers, handwritten note, priority response on all requests."
        ),
    },
    {
        "title": "Linen Rotation",
        "kind": "HOUSEKEEPING",
        "priority": "low",
        "estimated_minutes": 45,
        "trigger_event": None,
        "instructions": (
            "Rotate and inspect linens: replace worn items, deep clean "
            "mattress protectors, restock linen closet."
        ),
    },
]


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def seed_default_templates(
    tenant_id: str,
    *,
    dry_run: bool = False,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Seed default task templates for a tenant.

    Args:
        tenant_id: The tenant to seed templates for.
        dry_run: If True, return what would be created without writing.
        db: Optional Supabase client (uses default if not provided).

    Returns:
        Summary dict with created_count, skipped_count.
    """
    if db is None:
        db = _get_db()

    stats = {
        "total_templates": len(DEFAULT_TEMPLATES),
        "created": 0,
        "skipped_existing": 0,
        "errors": 0,
        "dry_run": dry_run,
        "templates": [],
    }

    # Check existing templates for this tenant
    existing_result = (
        db.table("task_templates")
        .select("kind")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    existing_kinds = {r["kind"] for r in (existing_result.data or [])}

    for template in DEFAULT_TEMPLATES:
        if template["kind"] in existing_kinds:
            stats["skipped_existing"] += 1
            continue

        row = {
            "tenant_id": tenant_id,
            "title": template["title"],
            "kind": template["kind"],
            "priority": template["priority"],
            "estimated_minutes": template["estimated_minutes"],
            "trigger_event": template["trigger_event"],
            "instructions": template["instructions"],
            "active": True,
        }

        stats["templates"].append({
            "kind": template["kind"],
            "title": template["title"],
        })

        if dry_run:
            stats["created"] += 1
            continue

        try:
            db.table("task_templates").insert(row).execute()
            stats["created"] += 1
        except Exception as exc:
            logger.warning("task_template_seeder: insert error for %s: %s",
                           template["kind"], exc)
            stats["errors"] += 1

    logger.info("Task template seed complete: %s",
                {k: v for k, v in stats.items() if k != "templates"})
    return stats
