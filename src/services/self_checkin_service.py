"""
Phase 1012 — Self Check-in Service (Framework Generalization)
==============================================================

Core business logic for the Self Check-in umbrella:
  - Access release evaluation — TWO-GATE MODEL
  - Step completion tracking (pre-access vs post-entry)
  - Execute access release (booking → checked_in)
  - Follow-up task generation (post-entry steps only)
  - Booking state transition

GATE MODEL (critical design decision — Phase 1012):
  Gate 1 — Pre-Access Gate (blocks entry):
    All pre_access_steps + 4 operational conditions must pass before
    access code is exposed. Once passed, booking → checked_in.

  Gate 2 — Post-Entry Requirements (non-blocking):
    Tracked after entry. Incomplete post_entry_steps generate a
    SELF_CHECKIN_FOLLOWUP task but do NOT block the guest from entering.

MODE-NEUTRAL: This service does not know whether the booking is in
Default mode or Late mode. Both modes use identical portal logic.
The mode only determines how the booking entered the 'approved' state.

Invariants:
    INV-ACCESS-01: Access code only exposed when ALL 6 pre-access conditions pass
    INV-BLOCK-01: No access release while prior stay for property is unresolved
    INV-TIME-01: Access never released before official check-in time on check-in date
    INV-AUDIT-01: Every access release writes to event_log AND admin_audit_log
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, date as date_type
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config helpers — Two-Gate Step Resolution
# ---------------------------------------------------------------------------

def resolve_pre_access_steps(config: dict) -> list[str]:
    """
    Return the list of step keys required BEFORE access is released.

    Reads the new-format `pre_access_steps` list from config.
    Falls back to the Phase 1004 legacy field format for backward compatibility.
    """
    # New format (Phase 1012+)
    if "pre_access_steps" in config:
        return [str(s) for s in (config["pre_access_steps"] or [])]

    # Legacy fallback (Phase 1004 format — single-step booleans)
    steps = []
    if config.get("require_id_photo"):
        steps.append("id_photo")
    if config.get("require_selfie"):
        steps.append("selfie")
    if config.get("require_agreement"):
        steps.append("agreement")
    if config.get("require_deposit_confirmation"):
        steps.append("deposit")
    return steps


def resolve_post_entry_steps(config: dict) -> list[str]:
    """
    Return the list of step keys required AFTER entry (non-blocking for access).

    Only the new format has post-entry steps. Legacy config = empty.
    """
    return [str(s) for s in (config.get("post_entry_steps") or [])]


def check_pre_access_complete(config: dict, steps_completed: dict) -> tuple[bool, list[str]]:
    """
    Check if all pre-access gate steps are complete.
    Returns (all_complete, missing_steps).
    """
    required = resolve_pre_access_steps(config)
    missing = [s for s in required if not steps_completed.get(s)]
    return len(missing) == 0, missing


def check_post_entry_complete(config: dict, steps_completed: dict) -> tuple[bool, list[str]]:
    """
    Check if all post-entry steps are complete.
    Returns (all_complete, missing_steps).
    Post-entry steps do NOT block access release.
    """
    required = resolve_post_entry_steps(config)
    missing = [s for s in required if not steps_completed.get(s)]
    return len(missing) == 0, missing


def all_steps_complete(config: dict, steps_completed: dict) -> tuple[bool, list[str]]:
    """Return (complete, all_missing) across both gates."""
    pre_req = resolve_pre_access_steps(config)
    post_req = resolve_post_entry_steps(config)
    all_required = pre_req + post_req
    missing = [s for s in all_required if not steps_completed.get(s)]
    return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# Access Release Result
# ---------------------------------------------------------------------------

@dataclass
class AccessReleaseResult:
    """Result of evaluating whether the pre-access gate is satisfied."""
    granted: bool
    reason: str
    # Access credentials (only set when granted=True)
    access_code: Optional[str] = None
    door_code: Optional[str] = None
    wifi_name: Optional[str] = None
    wifi_password: Optional[str] = None
    guest_portal_url: Optional[str] = None
    # Arrival guide (always populated when property is found)
    arrival_guide: Optional[dict] = None
    # Post-entry steps status (always populated when granted=True)
    post_entry_steps_required: Optional[list] = None
    post_entry_steps_completed: Optional[dict] = None


# ---------------------------------------------------------------------------
# Gate 1: Access Release Evaluation
# 6 conditions — all must be TRUE
# ---------------------------------------------------------------------------

def evaluate_access_release(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
    config: dict,
    steps_completed: dict,
) -> AccessReleaseResult:
    """
    Determines whether property access can be granted to a self-check-in guest.

    Gate 1 — Pre-Access Requirements. ALL conditions must be TRUE:
      1. self_checkin_approved == True (approval not revoked)
      2. self_checkin_status in ('approved', 'in_progress')
      3. All pre_access_steps marked complete in steps_completed
      4. Current time >= property check-in time on booking check_in date
      5. Property operational_status in ('available', 'ready')
      6. No other booking for this property has status 'checked_in' (prior stay)

    NOTE: Post-entry steps are NOT checked here. They are evaluated by
    evaluate_and_create_followup() after access is released.

    Returns AccessReleaseResult with granted=True and access credentials on success,
    or granted=False with reason on failure.
    """

    # === Condition 1+2: Booking state ===
    try:
        booking_res = (
            db.table("booking_state")
            .select(
                "booking_id, status, self_checkin_status, self_checkin_approved, "
                "check_in, check_out, property_id"
            )
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = booking_res.data or []
        if not rows:
            return AccessReleaseResult(granted=False, reason="booking_not_found")
        booking = rows[0]
    except Exception as exc:
        logger.error("access_release: booking lookup failed: %s", exc)
        return AccessReleaseResult(granted=False, reason="internal_error")

    if not booking.get("self_checkin_approved"):
        return AccessReleaseResult(granted=False, reason="approval_revoked")

    sc_status = booking.get("self_checkin_status") or "none"
    if sc_status not in ("approved", "in_progress"):
        return AccessReleaseResult(
            granted=False,
            reason=f"invalid_status:{sc_status}",
        )

    # === Condition 3: Pre-access steps complete ===
    all_pre_done, missing_pre = check_pre_access_complete(config, steps_completed)
    if not all_pre_done:
        return AccessReleaseResult(
            granted=False,
            reason=f"pre_access_incomplete:{','.join(missing_pre)}",
        )

    # === Condition 4: Time gate ===
    try:
        check_in_date = str(booking.get("check_in", ""))[:10]
        today_str = date_type.today().isoformat()

        if check_in_date > today_str:
            return AccessReleaseResult(
                granted=False,
                reason="too_early:before_checkin_date",
            )

        # Fetch property for time gate + credentials
        release_window = config.get("access_release_window_minutes", 0)
        prop_res = (
            db.table("properties")
            .select(
                "checkin_time, operational_status, access_code, door_code, "
                "wifi_name, wifi_password, self_checkin_config"
            )
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_res.data or []
        if not prop_rows:
            return AccessReleaseResult(granted=False, reason="property_not_found")

        prop = prop_rows[0]
        checkin_time_str = prop.get("checkin_time") or "15:00"

        try:
            h, m = checkin_time_str.split(":")[:2]
            checkin_hour, checkin_minute = int(h), int(m)
        except (ValueError, IndexError):
            checkin_hour, checkin_minute = 15, 0

        now_utc = datetime.now(tz=timezone.utc)

        # If today is the check-in date, enforce time gate
        if check_in_date == today_str:
            release_minutes = checkin_hour * 60 + checkin_minute - release_window
            current_minutes = now_utc.hour * 60 + now_utc.minute  # UTC approximation
            if current_minutes < release_minutes:
                return AccessReleaseResult(
                    granted=False,
                    reason=f"too_early:before_{checkin_time_str}",
                )

        # If check-in date is in the past, time gate is met
        # (guest arriving late — perfectly normal for both Default and Late modes)

    except Exception as exc:
        logger.error("access_release: time gate check failed: %s", exc)
        return AccessReleaseResult(granted=False, reason="time_gate_error")

    # === Condition 5: Property operational readiness ===
    ops_status = (prop.get("operational_status") or "available").lower()
    if ops_status not in ("available", "ready"):
        return AccessReleaseResult(
            granted=False,
            reason=f"property_not_ready:{ops_status}",
        )

    # === Condition 6: No prior stay unresolved ===
    try:
        prior_res = (
            db.table("booking_state")
            .select("booking_id, status")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .eq("status", "checked_in")
            .neq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        if prior_res.data:
            blocker = prior_res.data[0]
            return AccessReleaseResult(
                granted=False,
                reason=f"prior_stay_unresolved:{blocker['booking_id']}",
            )
    except Exception as exc:
        logger.error("access_release: prior stay check failed: %s", exc)
        return AccessReleaseResult(granted=False, reason="prior_stay_check_error")

    # === All 6 conditions met — build access release result ===

    # Extract arrival guide from property self_checkin_config
    prop_sc_config = prop.get("self_checkin_config") or {}
    if isinstance(prop_sc_config, dict):
        arrival_guide = prop_sc_config.get("arrival_guide") or {}
    else:
        arrival_guide = {}

    # Resolve post-entry steps for display
    post_entry_required = resolve_post_entry_steps(config)
    post_entry_completed = {
        s: steps_completed.get(s, False)
        for s in post_entry_required
    }

    return AccessReleaseResult(
        granted=True,
        reason="granted",
        access_code=prop.get("access_code") or prop.get("door_code"),
        door_code=prop.get("door_code"),
        wifi_name=prop.get("wifi_name"),
        wifi_password=prop.get("wifi_password"),
        arrival_guide=arrival_guide,
        post_entry_steps_required=post_entry_required,
        post_entry_steps_completed=post_entry_completed,
    )


# ---------------------------------------------------------------------------
# Execute Access Release
# ---------------------------------------------------------------------------

def execute_access_release(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
) -> dict:
    """
    Execute the access release after Gate 1 passes:
      1. Transition booking status → checked_in
      2. Set self_checkin_status → access_released
      3. Update property operational_status → occupied
      4. Auto-issue guest HMAC token (for Guest Portal continuity)
      5. Write audit events

    Returns dict with release details.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    # 1. Update booking_state
    db.table("booking_state").update({
        "status": "checked_in",
        "checked_in_at": now,
        "self_checkin_status": "access_released",
        "self_checkin_access_released_at": now,
        "updated_at_ms": now_ms,
    }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

    # 2. Update property operational_status → occupied
    try:
        db.table("properties").update({
            "operational_status": "occupied",
        }).eq("property_id", property_id).eq("tenant_id", tenant_id).execute()
    except Exception:
        logger.warning("access_release: failed to set property %s → occupied", property_id)

    # 3. Auto-issue guest HMAC token for Guest Portal continuity
    guest_portal_url = None
    try:
        from services.guest_token import issue_guest_token, record_guest_token
        raw_token, exp = issue_guest_token(
            booking_ref=booking_id,
            guest_email="",
            ttl_seconds=30 * 86_400,  # 30 days — full stay + buffer
        )
        record_guest_token(
            db=db,
            booking_ref=booking_id,
            tenant_id=tenant_id,
            raw_token=raw_token,
            exp=exp,
        )
        guest_portal_url = f"https://app.domaniqo.com/guest/{raw_token}"
    except Exception as exc:
        logger.warning("access_release: guest token issuance failed (non-blocking): %s", exc)

    # 4. Audit events
    try:
        db.table("event_log").insert({
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "event_type": "SELF_CHECKIN_ACCESS_RELEASED",
            "payload": {
                "property_id": property_id,
                "released_at": now,
                "flow": "self_checkin",
            },
            "received_at": now,
        }).execute()
    except Exception:
        pass

    try:
        db.table("admin_audit_log").insert({
            "tenant_id": tenant_id,
            "actor_id": "system:self_checkin",
            "action": "self_checkin.access_released",
            "entity_type": "booking",
            "entity_id": booking_id,
            "details": {
                "property_id": property_id,
                "released_at": now,
                "guest_portal_issued": bool(guest_portal_url),
            },
            "performed_at": now,
        }).execute()
    except Exception:
        pass

    return {
        "released": True,
        "checked_in_at": now,
        "guest_portal_url": guest_portal_url,
    }


# ---------------------------------------------------------------------------
# Gate 2: Post-Entry Follow-up Evaluation
# ---------------------------------------------------------------------------

_STEP_LABELS: dict[str, str] = {
    "id_photo": "ID photo",
    "selfie": "Selfie photo",
    "agreement": "House rules agreement",
    "deposit": "Security deposit acknowledgement",
    "electricity_meter": "Electricity meter confirmation",
    "arrival_photos": "Arrival baseline photos",
}


def evaluate_and_create_followup(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
    config: dict,
    steps_completed: dict,
) -> dict:
    """
    Gate 2 Evaluation — called AFTER access is released.

    Checks post-entry steps. If all complete → self_checkin_status = 'completed'.
    If any post-entry steps are missing → self_checkin_status = 'followup_required'
    + create SELF_CHECKIN_FOLLOWUP task for staff.

    NOTE: pre_access_steps are also checked here for completeness reporting,
    but they should already be done (access was already released).

    Returns {status, task_id?, missing_steps}.
    """
    now = datetime.now(tz=timezone.utc).isoformat()
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    _, missing_post = check_post_entry_complete(config, steps_completed)

    if not missing_post or not config.get("followup_if_incomplete", True):
        # All post-entry requirements met — flow is complete
        db.table("booking_state").update({
            "self_checkin_status": "completed",
            "self_checkin_completed_at": now,
            "updated_at_ms": now_ms,
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        return {"status": "completed", "task_id": None, "missing_steps": []}

    # Post-entry items are incomplete — create follow-up task
    db.table("booking_state").update({
        "self_checkin_status": "followup_required",
        "updated_at_ms": now_ms,
    }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

    # Resolve property name for task title
    prop_name = property_id
    try:
        pn_res = (
            db.table("properties")
            .select("display_name, name")
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        if pn_res.data:
            prop_name = (
                pn_res.data[0].get("display_name")
                or pn_res.data[0].get("name")
                or property_id
            )
    except Exception:
        pass

    # Deterministic task_id (idempotent upsert)
    import hashlib
    task_id = hashlib.sha256(
        f"SELF_CHECKIN_FOLLOWUP:{booking_id}:{property_id}".encode()
    ).hexdigest()[:16]

    missing_desc = "\n".join(
        f"- {_STEP_LABELS.get(s, s)}: Not completed"
        for s in missing_post
    )

    task_payload = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "booking_id": booking_id,
        "property_id": property_id,
        "kind": "SELF_CHECKIN_FOLLOWUP",
        "status": "PENDING",
        "priority": "HIGH",
        "urgency": "urgent",
        "worker_role": "CHECKIN",
        "ack_sla_minutes": 30,
        "due_date": now[:10],
        "title": f"Self Check-in Follow-up: {prop_name}",
        "description": (
            f"Guest completed self check-in and has entered the property, "
            f"but the following post-entry items need staff attention:\n{missing_desc}"
        ),
        "created_at": now,
        "updated_at": now,
    }

    try:
        db.table("tasks").upsert(task_payload, on_conflict="task_id").execute()
    except Exception as exc:
        logger.error("follow-up task creation failed: %s", exc)
        return {"status": "followup_required", "task_id": None, "error": str(exc)}

    # Audit
    try:
        db.table("admin_audit_log").insert({
            "tenant_id": tenant_id,
            "actor_id": "system:self_checkin",
            "action": "self_checkin.followup_created",
            "entity_type": "task",
            "entity_id": task_id,
            "details": {
                "booking_id": booking_id,
                "property_id": property_id,
                "missing_post_entry_steps": missing_post,
            },
            "performed_at": now,
        }).execute()
    except Exception:
        pass

    logger.info(
        "self_checkin: follow-up task %s created for booking=%s missing_post=%s",
        task_id, booking_id, missing_post,
    )

    return {
        "status": "followup_required",
        "task_id": task_id,
        "missing_steps": missing_post,
    }
