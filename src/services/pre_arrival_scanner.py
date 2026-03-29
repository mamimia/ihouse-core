"""
Phase 232 — Guest Pre-Arrival Automation Chain
Phase 1013 — Default Self Check-in Integration

pre_arrival_scanner: daily job that finds bookings with check-in in 1–3 days,
auto-creates pre-arrival tasks, and auto-drafts a check-in message (draft only).

Phase 1013 addition — Mode-Aware Routing:
  Reads property's self_checkin_config.mode to determine the correct path:

  mode='disabled' or mode='late_only' (staffed properties):
    → Normal staffed flow: create CHECKIN_PREP + GUEST_WELCOME tasks, build draft.
    → Late Self Check-in is triggered separately by admin action, not the scanner.

  mode='default' (self check-in properties):
    → Skip CHECKIN_PREP + GUEST_WELCOME tasks (no physical staff check-in needed).
    → If no staffed override on the booking: auto-issue SELF_CHECKIN token,
      set self_checkin_status='approved', send portal link to guest.
    → If staffed override active: skip portal issuance, fall through to staffed tasks.
    → Access code is NOT included in the draft — guest gets it at check-in time.

Design:
  - Called by the scheduler (Job 4, daily at 06:00 UTC) via services/scheduler.py.
  - Also callable manually for testing/backfill.
  - Idempotent: queries pre_arrival_queue to skip already-processed bookings.
  - Best-effort per booking: exception on one booking never aborts the scan.
  - Never sends any message directly — portal link dispatch is delegated.

Public entry point:
    run_pre_arrival_scan(db=None) -> dict
        Returns: { bookings_found, bookings_processed, bookings_skipped,
                   tasks_created, drafts_written, self_checkin_issued }
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Active lifecycle statuses to include in the scan
_ACTIVE_STATUSES = ("active",)

# Days ahead to scan (check-in between today+1 and today+LOOKAHEAD_DAYS)
_LOOKAHEAD_DAYS = 3


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Heuristic check-in draft builder (no LLM dependency)
# ---------------------------------------------------------------------------

def _build_checkin_draft(
    guest_name: Optional[str],
    property_name: Optional[str],
    check_in: str,
    check_out: str,
    access_code: Optional[str] = None,
) -> str:
    """
    Build a minimal check-in instructions draft.
    Used for the pre_arrival_queue draft_preview — heuristic only,
    no LLM call to keep the scanner fast and side-effect-free.
    """
    name_greeting = f"Dear {guest_name}," if guest_name else "Dear Guest,"
    prop_ref = f" at {property_name}" if property_name else ""
    access_line = f"\n\nEntry code: {access_code}" if access_code else ""
    return (
        f"{name_greeting}\n\n"
        f"We look forward to welcoming you{prop_ref} on {check_in}.\n"
        f"Your stay runs from {check_in} to {check_out}.{access_line}\n\n"
        f"Please don't hesitate to reach out if you need anything before your arrival."
    )


def _get_property_self_checkin_config(db: Any, tenant_id: str, property_id: str) -> dict:
    """
    Fetch the self_checkin_config for a property.
    Returns mode and step config, with safe defaults.
    """
    try:
        res = (
            db.table("properties")
            .select("self_checkin_config")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            cfg = rows[0].get("self_checkin_config") or {}
            return cfg if isinstance(cfg, dict) else {}
    except Exception:
        pass
    return {"mode": "disabled"}


def _issue_self_checkin_for_default_booking(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
    guest_name: str,
    guest_phone: Optional[str],
    guest_email: Optional[str],
    property_name: Optional[str],
    sc_config: dict,
) -> bool:
    """
    Auto-issue self check-in portal link for a Default-mode booking.

    Phase 1013 — this is the scanner's replacement for staffed task creation
    when property mode is 'default'.

    Actions:
      1. Issue SELF_CHECKIN access token
      2. Set booking_state.self_checkin_status = 'approved'
      3. Set self_checkin_approved_by = 'system:pre_arrival', self_checkin_approved = True
      4. Store token hash + portal link on booking
      5. Dispatch portal link via SMS/email (best-effort)

    Returns True if successful (token issued + state updated), False on failure.
    """
    try:
        from api.self_checkin_router import (
            _issue_self_checkin_token,
            _dispatch_portal_link,
        )

        ttl_hours = sc_config.get("max_token_ttl_hours") or 72
        portal_url, token_hash, exp = _issue_self_checkin_token(
            db=db,
            tenant_id=tenant_id,
            booking_id=booking_id,
            guest_email=guest_email or "",
            ttl_hours=int(ttl_hours),
        )

        now = datetime.now(tz=timezone.utc).isoformat()
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

        db.table("booking_state").update({
            "self_checkin_status": "approved",
            "self_checkin_approved": True,
            "self_checkin_approved_by": "system:pre_arrival",
            "self_checkin_approved_at": now,
            "self_checkin_reason": "property_default_self_checkin",
            "self_checkin_token_hash": token_hash,
            "self_checkin_portal_url": portal_url,
            "self_checkin_portal_sent_at": now,
            "self_checkin_config": sc_config,  # snapshot property config at time of issuance
            "updated_at_ms": now_ms,
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Dispatch portal link to guest
        if sc_config.get("auto_send_portal_link", True):
            _dispatch_portal_link(
                db=db,
                tenant_id=tenant_id,
                portal_url=portal_url,
                guest_name=guest_name or "Guest",
                property_name=property_name or property_id,
                mode="default",
                to_phone=guest_phone,
                to_email=guest_email,
            )

        logger.info(
            "pre_arrival_scanner: default_sc issued for booking=%s property=%s portal=%s",
            booking_id, property_id, portal_url,
        )
        return True

    except Exception as exc:
        logger.warning(
            "pre_arrival_scanner: default_sc issuance failed booking=%s: %s",
            booking_id, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Task creation helper (create CHECKIN_PREP + GUEST_WELCOME via upsert)
# Staffed properties only — NOT called for Default Self Check-in mode.
# ---------------------------------------------------------------------------

def _create_pre_arrival_tasks(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: str,
    check_in: str,
    guest_name: Optional[str],
) -> list[str]:
    """
    Upsert CHECKIN_PREP and (if guest_name known) GUEST_WELCOME tasks.

    Returns list of task_ids written (may be empty on failure).
    Uses upsert on task_id for idempotency — safe to call twice.
    """
    from tasks.task_model import Task, TaskKind, TaskPriority
    now = datetime.now(tz=timezone.utc).isoformat()
    written: list[str] = []

    kinds_to_create: list[tuple[TaskKind, str]] = [
        (
            TaskKind.CHECKIN_PREP,
            f"CHECKIN_PREP — pre-arrival preparation (auto, Phase 232)",
        ),
    ]
    if guest_name:
        kinds_to_create.append((
            TaskKind.GUEST_WELCOME,
            f"GUEST_WELCOME — welcome setup for {guest_name} (auto, Phase 232)",
        ))

    for kind, description in kinds_to_create:
        try:
            task = Task.build(
                kind=kind,
                tenant_id=tenant_id,
                booking_id=booking_id,
                property_id=property_id,
                due_date=check_in,
                title=f"{kind.value} — {property_id[:16]}",
                created_at=now,
                priority=TaskPriority.HIGH,
                description=description,
            )
            row = {
                "task_id":        task.task_id,
                "tenant_id":      task.tenant_id,
                "kind":           task.kind.value,
                "status":         task.status.value,
                "priority":       task.priority.value,
                "urgency":        task.urgency,
                "worker_role":    task.worker_role.value,
                "ack_sla_minutes": task.ack_sla_minutes,
                "booking_id":     task.booking_id,
                "property_id":    task.property_id,
                "due_date":       task.due_date,
                "title":          task.title,
                "description":    task.description,
                "created_at":     task.created_at,
                "updated_at":     task.updated_at,
                "notes":          [],
                "canceled_reason": None,
            }
            db.table("tasks").upsert(row, on_conflict="task_id").execute()
            written.append(task.task_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pre_arrival_scanner: failed to create %s task for booking_id=%s: %s",
                kind.value, booking_id, exc,
            )
    return written


# ---------------------------------------------------------------------------
# Queue write helper
# ---------------------------------------------------------------------------

def _already_processed(db: Any, tenant_id: str, booking_id: str, check_in_date: str) -> bool:
    """Return True if this booking has already been processed today for this check_in."""
    try:
        result = (
            db.table("pre_arrival_queue")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("check_in", check_in_date)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:  # noqa: BLE001
        return False  # if we can't check, don't skip — try to process


def _write_queue_row(
    db: Any,
    tenant_id: str,
    booking_id: str,
    property_id: Optional[str],
    check_in: str,
    tasks_created: list[str],
    draft_written: bool,
    draft_preview: Optional[str],
) -> None:
    """Insert or update a queue row for this booking. Idempotent via unique constraint."""
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        db.table("pre_arrival_queue").upsert(
            {
                "tenant_id":     tenant_id,
                "booking_id":    booking_id,
                "property_id":   property_id,
                "check_in":      check_in,
                "tasks_created": tasks_created,
                "draft_written": draft_written,
                "draft_preview": (draft_preview or "")[:500],
                "scanned_at":    now,
            },
            on_conflict="tenant_id,booking_id,check_in",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pre_arrival_scanner: failed to write queue row booking_id=%s: %s",
            booking_id, exc,
        )


# ---------------------------------------------------------------------------
# Main scanner function
# ---------------------------------------------------------------------------

def run_pre_arrival_scan(db: Optional[Any] = None) -> dict:
    """
    Scan booking_state for bookings with check-in in 1–3 days.

    For each unprocessed booking:
      1. Create CHECKIN_PREP + GUEST_WELCOME tasks (upsert, idempotent)
      2. Build a heuristic check-in draft (no LLM, no network call)
      3. Write a row to pre_arrival_queue

    Returns:
        {
            "bookings_found": int,
            "bookings_processed": int,
            "bookings_skipped": int,
            "tasks_created": int,
            "drafts_written": int,
            "self_checkin_issued": int,
        }
    """
    try:
        if db is None:
            db = _get_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("pre_arrival_scanner: cannot connect to DB — %s", exc)
        return {
            "bookings_found": 0,
            "bookings_processed": 0,
            "bookings_skipped": 0,
            "tasks_created": 0,
            "drafts_written": 0,
            "self_checkin_issued": 0,
        }

    today = date.today()
    date_from = (today + timedelta(days=1)).isoformat()
    date_to = (today + timedelta(days=_LOOKAHEAD_DAYS)).isoformat()

    try:
        result = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, property_id, check_in, check_out, "
                "status, guest_name, guest_phone, guest_email, "
                "self_checkin_staff_override"
            )
            .gte("check_in", date_from)
            .lte("check_in", date_to)
            .in_("status", list(_ACTIVE_STATUSES))
            .limit(200)
            .execute()
        )
        bookings = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("pre_arrival_scanner: booking_state query failed: %s", exc)
        return {
            "bookings_found": 0,
            "bookings_processed": 0,
            "bookings_skipped": 0,
            "tasks_created": 0,
            "drafts_written": 0,
        }

    bookings_found = len(bookings)
    bookings_processed = 0
    bookings_skipped = 0
    total_tasks = 0
    total_drafts = 0
    total_self_checkin_issued = 0

    for booking in bookings:
        booking_id = booking.get("booking_id", "")
        tenant_id  = booking.get("tenant_id", "")
        property_id = booking.get("property_id")
        check_in   = booking.get("check_in", "")
        check_out  = booking.get("check_out", "")
        guest_name = booking.get("guest_name")
        guest_phone = booking.get("guest_phone")
        guest_email = booking.get("guest_email")

        if not (booking_id and tenant_id and check_in):
            continue

        # Idempotency check
        if _already_processed(db, tenant_id, booking_id, check_in):
            bookings_skipped += 1
            continue

        # Phase 887d: Approved-Only Lifecycle Rule.
        # Never create tasks for bookings on non-approved properties.
        # A property that is pending, draft, rejected, or archived is not
        # operationally live — its bookings must not generate worker tasks.
        if property_id:
            try:
                prop_status_result = (
                    db.table("properties")
                    .select("status")
                    .eq("property_id", property_id)
                    .limit(1)
                    .execute()
                )
                prop_status_rows = prop_status_result.data or []
                if not prop_status_rows or prop_status_rows[0].get("status") != "approved":
                    logger.info(
                        "pre_arrival_scanner: skipping booking_id=%s — "
                        "property_id=%s is not approved (status=%s)",
                        booking_id, property_id,
                        prop_status_rows[0].get("status") if prop_status_rows else "not_found",
                    )
                    bookings_skipped += 1
                    continue
            except Exception:  # noqa: BLE001
                pass  # if we can't verify, continue (safe default — let it process)

        try:
            # Phase 1013: detect property self_checkin mode
            sc_config: dict = {}
            sc_mode = "disabled"
            if property_id:
                sc_config = _get_property_self_checkin_config(db, tenant_id, property_id)
                sc_mode = sc_config.get("mode") or "disabled"

            # Check for per-booking staffed override
            staff_override = booking.get("self_checkin_staff_override") or False

            # === DEFAULT SELF CHECK-IN path ===
            if sc_mode == "default" and not staff_override:
                # Skip CHECKIN_PREP/GUEST_WELCOME — no physical check-in needed.
                # Auto-issue SELF_CHECKIN token + portal link.

                # Fetch property name for notification message
                property_name: Optional[str] = None
                if property_id:
                    try:
                        pn_res = (
                            db.table("properties")
                            .select("display_name, name")
                            .eq("property_id", property_id)
                            .limit(1)
                            .execute()
                        )
                        if pn_res.data:
                            property_name = (
                                pn_res.data[0].get("display_name")
                                or pn_res.data[0].get("name")
                            )
                    except Exception:
                        pass

                issued = _issue_self_checkin_for_default_booking(
                    db=db,
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id or "",
                    guest_name=guest_name,
                    guest_phone=guest_phone,
                    guest_email=guest_email,
                    property_name=property_name,
                    sc_config=sc_config,
                )

                _write_queue_row(
                    db=db,
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id,
                    check_in=check_in,
                    tasks_created=[],
                    draft_written=False,
                    draft_preview=f"[self_checkin:default] portal_issued={issued}",
                )

                if issued:
                    total_self_checkin_issued += 1
                bookings_processed += 1

            else:
                # === STAFFED / LATE_ONLY / DISABLED path ===
                # (also used if Default-mode but staff override is set)

                # 1. Create tasks
                task_ids = _create_pre_arrival_tasks(
                    db=db,
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id or "",
                    check_in=check_in,
                    guest_name=guest_name,
                )

                # 2. Fetch property for access_code (best-effort)
                access_code: Optional[str] = None
                property_name = None
                if property_id:
                    try:
                        prop_result = (
                            db.table("properties")
                            .select("name, access_code")
                            .eq("property_id", property_id)
                            .limit(1)
                            .execute()
                        )
                        if prop_result.data:
                            access_code = prop_result.data[0].get("access_code")
                            property_name = prop_result.data[0].get("name")
                    except Exception:  # noqa: BLE001
                        pass

                # 3. Build check-in draft
                draft = _build_checkin_draft(
                    guest_name=guest_name,
                    property_name=property_name,
                    check_in=check_in,
                    check_out=check_out or "",
                    access_code=access_code,
                )

                # 4. Write queue row
                _write_queue_row(
                    db=db,
                    tenant_id=tenant_id,
                    booking_id=booking_id,
                    property_id=property_id,
                    check_in=check_in,
                    tasks_created=task_ids,
                    draft_written=True,
                    draft_preview=draft,
                )

                total_tasks += len(task_ids)
                total_drafts += 1
                bookings_processed += 1

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pre_arrival_scanner: error processing booking_id=%s: %s",
                booking_id, exc,
            )

    logger.info(
        "pre_arrival_scanner: found=%d processed=%d skipped=%d tasks=%d drafts=%d sc_issued=%d",
        bookings_found, bookings_processed, bookings_skipped,
        total_tasks, total_drafts, total_self_checkin_issued,
    )

    return {
        "bookings_found":       bookings_found,
        "bookings_processed":   bookings_processed,
        "bookings_skipped":     bookings_skipped,
        "tasks_created":        total_tasks,
        "drafts_written":       total_drafts,
        "self_checkin_issued":  total_self_checkin_issued,
    }
