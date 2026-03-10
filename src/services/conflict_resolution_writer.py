"""
Phase 184 — Conflict Resolution Writer

Persists the output of core.skills.booking_conflict_resolver.skill.run()
to the conflict_resolution_queue table.

Writes ONE row per artifact in artifacts_to_create (ConflictTask or OverrideRequest).
AuditEvent from events_to_emit is written to admin_audit_log if available.

Design:
  - Best-effort on AuditEvent write — never blocks if admin_audit_log is absent.
  - ConflictTask / OverrideRequest writes use upsert on the idempotency index
    (booking_id, request_id, artifact_type) — safe to call on replay.
  - Never raises — all DB errors are logged as WARNING and swallowed,
    returning a partial count.
  - Returns (artifacts_written, audit_written) counts.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def write_resolution(
    *,
    db: Any,
    tenant_id: str,
    artifacts_to_create: List[Dict[str, Any]],
    events_to_emit: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Persist ConflictTask + OverrideRequest artifacts and the AuditEvent.

    Args:
        db:                  Supabase client.
        tenant_id:           Tenant scope for every row written.
        artifacts_to_create: List of artifact dicts from skill.run() output.
        events_to_emit:      List of AuditEvent dicts from skill.run() output.

    Returns:
        (artifacts_written, audit_written): counts of successfully written rows.
    """
    artifacts_written: int = 0
    audit_written: int = 0

    # --- Write ConflictTask + OverrideRequest ---
    for artifact in artifacts_to_create:
        art_type = artifact.get("artifact_type", "")
        if art_type not in {"ConflictTask", "OverrideRequest"}:
            logger.warning("conflict_resolution_writer: unknown artifact_type=%s — skipping", art_type)
            continue

        row = {
            "conflict_id":            str(uuid.uuid4()),
            "tenant_id":              tenant_id,
            "artifact_type":          art_type,
            "type_id":                artifact.get("type_id"),
            "status":                 "Open",
            "priority":               artifact.get("priority"),
            "property_id":            artifact.get("property_id", ""),
            "booking_id":             artifact.get("booking_id", ""),
            "conflicts_found":        artifact.get("conflicts_found", []),
            "request_id":             artifact.get("request_id", ""),
            "required_approver_role": artifact.get("required_approver_role"),
        }

        try:
            (
                db.table("conflict_resolution_queue")
                .upsert(row, on_conflict="booking_id,request_id,artifact_type")
                .execute()
            )
            artifacts_written += 1
        except Exception as exc:
            logger.warning(
                "conflict_resolution_writer: DB write failed for %s booking=%s: %s",
                art_type, row["booking_id"], exc,
            )

    # --- Write AuditEvent (best-effort) ---
    for event in events_to_emit:
        if event.get("event_type") != "AuditEvent":
            continue
        try:
            audit_row = {
                "audit_id":    str(uuid.uuid4()),
                "tenant_id":   tenant_id,
                "request_id":  event.get("request_id"),
                "actor_id":    event.get("actor_id"),
                "role":        event.get("role"),
                "action":      event.get("action", "booking_conflict_resolve"),
                "entity_type": event.get("entity_type", "booking"),
                "entity_id":   event.get("entity_id"),
                "payload":     event,
            }
            db.table("admin_audit_log").insert(audit_row).execute()
            audit_written += 1
        except Exception as exc:
            logger.warning(
                "conflict_resolution_writer: AuditEvent write failed: %s", exc
            )

    return artifacts_written, audit_written
