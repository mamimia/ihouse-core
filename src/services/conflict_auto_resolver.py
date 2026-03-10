"""
Phase 207 — Conflict Auto-Resolution Engine

Pure orchestration module: runs the conflict detector for a booking's property
and persists ConflictTask artifacts if overlaps are found.

Architecture:
- Called from service.py after BOOKING_CREATED APPLIED and BOOKING_AMENDED APPLIED.
- Also called from the manual endpoint POST /conflicts/auto-check/{booking_id}.
- Never raises — all errors are logged and swallowed (best-effort pattern).
- No direct DB writes — delegates to conflict_resolution_writer.write_resolution().
- Never modifies the conflict_detector.py (Phase 86 invariant preserved).

Policy (hardcoded — Phase 207):
    statuses_blocking:        ["ACTIVE"]
    allow_admin_override:     False
    conflict_task_type_id:    "CONFLICT_AUTO_REVIEW"
    override_request_type_id: "CONFLICT_AUTO_OVERRIDE"

Return value: ConflictAutoCheckResult (never None)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from adapters.ota.conflict_detector import (
    ConflictKind,
    ConflictSeverity,
    detect_conflicts,
)
from services.conflict_resolution_writer import write_resolution

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy (locked for Phase 207)
# ---------------------------------------------------------------------------

_AUTO_POLICY = {
    "statuses_blocking":        ["ACTIVE"],
    "allow_admin_override":     False,
    "conflict_task_type_id":    "CONFLICT_AUTO_REVIEW",
    "override_request_type_id": "CONFLICT_AUTO_OVERRIDE",
}

_ACTOR = {
    "actor_id": "system:conflict_auto_resolver",
    "role":     "system",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ConflictAutoCheckResult:
    """
    Result of an automatic conflict check for a single booking.

    conflicts_found:   Number of DATE_OVERLAP conflicts found involving this
                       booking's property (not necessarily this booking).
    artifacts_written: Number of ConflictTask rows written to
                       conflict_resolution_queue.
    partial:           True if the underlying detect_conflicts scan was
                       incomplete (DB query failure).
    """
    conflicts_found: int
    artifacts_written: int
    partial: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _build_artifact(
    booking_id: str,
    property_id: str,
    conflicts_found: List[str],
    request_id: str,
) -> dict:
    """Build a ConflictTask artifact dict matching write_resolution() schema."""
    return {
        "artifact_type":  "ConflictTask",
        "type_id":        _AUTO_POLICY["conflict_task_type_id"],
        "status":         "Open",
        "priority":       "High",
        "property_id":    property_id,
        "booking_id":     booking_id,
        "conflicts_found": conflicts_found,
        "request_id":     request_id,
    }


def _build_audit_event(
    booking_id: str,
    property_id: str,
    conflicts: List[str],
    enforced_status: str,
    artifacts: list,
    request_id: str,
    now_utc: str,
) -> dict:
    """Build an AuditEvent dict matching write_resolution() schema."""
    return {
        "event_type":     "AuditEvent",
        "request_id":     request_id,
        "now_utc":        now_utc,
        "actor_id":       _ACTOR["actor_id"],
        "role":           _ACTOR["role"],
        "entity_type":    "booking",
        "entity_id":      booking_id,
        "action":         "booking_conflict_auto_resolve",
        "candidate": {
            "property_id": property_id,
        },
        "conflicts_found":  conflicts,
        "enforced_status":  enforced_status,
        "artifacts":        [{"artifact_type": a.get("artifact_type", "")} for a in artifacts],
        "denial_code":      "",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_auto_check(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
    event_kind: str = "BOOKING_CREATED",
    now_utc: Optional[str] = None,
) -> ConflictAutoCheckResult:
    """
    Run the conflict auto-check for a given booking/property.

    Calls `detect_conflicts()`, filters to DATE_OVERLAP conflicts on the same
    property, then writes a ConflictTask artifact for each unique clash pair
    involving `booking_id`.

    Args:
        db:           Supabase client (or compatible mock).
        tenant_id:    Authenticated tenant scope.
        booking_id:   The booking just created/amended.
        property_id:  The property this booking belongs to.
        event_kind:   "BOOKING_CREATED" | "BOOKING_AMENDED" (informational).
        now_utc:      ISO 8601 UTC timestamp. Defaults to now.

    Returns:
        ConflictAutoCheckResult — never raises.
    """
    if now_utc is None:
        now_utc = _now_utc()

    try:
        # Step 1: Scan all active bookings for tenant
        report = detect_conflicts(db, tenant_id)

        # Step 2: Filter to DATE_OVERLAP conflicts on this property involving this booking
        relevant_conflicts = [
            c for c in report.conflicts
            if (
                c.kind == ConflictKind.DATE_OVERLAP
                and c.severity == ConflictSeverity.ERROR
                and c.property_id == property_id
                and (c.booking_id_a == booking_id or c.booking_id_b == booking_id)
            )
        ]

        if not relevant_conflicts:
            return ConflictAutoCheckResult(
                conflicts_found=0,
                artifacts_written=0,
                partial=report.partial,
            )

        # Step 3: Collect all conflicting peers
        peer_ids: List[str] = []
        for c in relevant_conflicts:
            peer = c.booking_id_b if c.booking_id_a == booking_id else c.booking_id_a
            if peer and peer not in peer_ids:
                peer_ids.append(peer)

        # Step 4: Build one ConflictTask artifact with all peers
        request_id = str(uuid.uuid4())
        artifact = _build_artifact(
            booking_id=booking_id,
            property_id=property_id,
            conflicts_found=peer_ids,
            request_id=request_id,
        )
        audit = _build_audit_event(
            booking_id=booking_id,
            property_id=property_id,
            conflicts=peer_ids,
            enforced_status="PendingResolution",
            artifacts=[artifact],
            request_id=request_id,
            now_utc=now_utc,
        )

        # Step 5: Persist via write_resolution (best-effort)
        artifacts_written, _ = write_resolution(
            db=db,
            tenant_id=tenant_id,
            artifacts_to_create=[artifact],
            events_to_emit=[audit],
        )

        logger.info(
            "conflict_auto_resolver: %s booking=%s property=%s"
            " conflicts=%d peers=%s artifacts_written=%d",
            event_kind, booking_id, property_id,
            len(relevant_conflicts), peer_ids, artifacts_written,
        )

        return ConflictAutoCheckResult(
            conflicts_found=len(relevant_conflicts),
            artifacts_written=artifacts_written,
            partial=report.partial,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "conflict_auto_resolver: run_auto_check failed booking=%s: %s",
            booking_id, exc,
        )
        return ConflictAutoCheckResult(
            conflicts_found=0,
            artifacts_written=0,
            partial=True,
        )
