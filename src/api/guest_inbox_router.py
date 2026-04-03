"""
Guest Inbox Router — Phase 1049 / 1052
=======================================

Operational inbox for the staff member currently assigned to a stay's conversation thread.

Endpoints:
    GET  /manager/guest-messages                           — inbox: all assigned stay-threads
    GET  /manager/guest-messages/{booking_id}              — full thread for one stay
    PATCH /manager/guest-messages/{booking_id}/read        — mark all messages in thread as read
    POST  /manager/guest-messages/{booking_id}/reply       — send a host reply into the thread

Auth: jwt_identity (same pattern as all OM endpoints — supports Act As / Preview As sessions).

Ownership model (Phase 1048 scaffold):
    Queries are scoped by `assigned_om_id = caller's user_id`.
    This field stores user_id (not tenant_id) — all staff share one tenant_id.
    See guest_messaging.py for the full ownership model note.
    Long-term canonical ownership will be guest_conversation_assignments (Phase 1054).

Thread model:
    One thread = one stay (one booking_id).
    The inbox returns one entry per stay-thread, not one entry per message.
    Sorted: unread first, then newest last_message_at.

Reply identity rule (Phase 1052):
    sender_id = caller's user_id  (NOT tenant_id — shared too broadly).
    sender_type = 'host'
    This makes host replies attributable to the specific responding person.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manager/guest-messages", tags=["guest-inbox"])


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_guest_name(raw: Optional[str]) -> str:
    """Return a human-readable guest name, stripping OTA placeholders."""
    if not raw:
        return "Guest"
    lower = raw.lower().strip()
    # Common OTA placeholder patterns
    placeholders = {"airbnb guest", "booking.com guest", "guest", "unknown", "", "n/a"}
    if lower in placeholders:
        return "Guest"
    return raw.strip()


def _build_thread_summary(booking_id: str, messages: List[Dict]) -> Dict:
    """
    Given a list of messages for one booking, build the inbox summary entry.
    Counts unread (read_at IS NULL for guest messages we haven't read yet).
    """
    msgs = sorted(messages, key=lambda m: m.get("created_at") or "")
    last = msgs[-1] if msgs else {}
    unread = sum(1 for m in msgs if not m.get("read_at") and m.get("sender_type") == "guest")
    return {
        "booking_id": booking_id,
        "unread_count": unread,
        "last_message": (last.get("message") or "")[:120],
        "last_message_at": last.get("created_at"),
        "last_sender_type": last.get("sender_type"),
        "messages": msgs,
    }


# ---------------------------------------------------------------------------
# GET /manager/guest-messages — operational inbox
# ---------------------------------------------------------------------------

@router.get("", summary="OM operational guest inbox — all assigned stay-threads (Phase 1049)")
async def get_guest_inbox(
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns all stay-threads currently assigned to the caller.
    One entry per stay (booking_id), not one per message.

    Sort: unread conversations first, then newest last_message_at DESC.
    Each entry includes booking context (property, guest, dates) for triage.

    This is an operational triage surface, not a history viewer.
    """
    # assigned_om_id stores user_id (not tenant_id) — see resolve_conversation_owner
    caller_user_id = str(identity.get("user_id", "")).strip()
    caller_role = str(identity.get("role", "")).strip()
    if not caller_user_id:
        return JSONResponse(status_code=401, content={"error": "CALLER_NOT_IDENTIFIED"})

    try:
        db = client if client is not None else _get_db()

        # --- 1. Fetch all messages assigned to this caller ---
        msg_res = (
            db.table("guest_chat_messages")
            .select("id,booking_id,property_id,sender_type,sender_id,message,read_at,created_at,assigned_om_id")
            .eq("assigned_om_id", caller_user_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = msg_res.data or []
        if not messages:
            return JSONResponse(status_code=200, content={"conversations": []})

        # --- 2. Group messages by booking_id (one thread per stay) ---
        threads: Dict[str, List] = {}
        property_ids = set()
        booking_ids = set()
        for m in messages:
            bid = m["booking_id"]
            threads.setdefault(bid, []).append(m)
            property_ids.add(m["property_id"])
            booking_ids.add(bid)

        # --- 3. Fetch booking context (guest name, dates) ---
        booking_context: Dict[str, Dict] = {}
        if booking_ids:
            bk_res = (
                db.table("booking_state")
                .select("booking_id,guest_name,check_in,check_out,property_id,status")
                .in_("booking_id", list(booking_ids))
                .execute()
            )
            for b in (bk_res.data or []):
                booking_context[b["booking_id"]] = b

        # --- 4. Fetch property display names ---
        prop_names: Dict[str, str] = {}
        if property_ids:
            prop_res = (
                db.table("properties")
                .select("property_id,display_name")
                .in_("property_id", list(property_ids))
                .execute()
            )
            for p in (prop_res.data or []):
                prop_names[p["property_id"]] = p.get("display_name") or p["property_id"]

        # --- 5. Fetch caller display name for context ---
        caller_name = "Staff"
        try:
            name_res = (
                db.table("tenant_permissions")
                .select("display_name")
                .eq("user_id", caller_user_id)
                .limit(1)
                .execute()
            )
            if name_res.data:
                caller_name = name_res.data[0].get("display_name") or "Staff"
        except Exception:
            pass

        # --- 6. Build response: one entry per stay-thread ---
        conversations = []
        for booking_id, msgs in threads.items():
            summary = _build_thread_summary(booking_id, msgs)
            bk = booking_context.get(booking_id, {})
            prop_id = msgs[0]["property_id"] if msgs else ""

            conversations.append({
                "booking_id": booking_id,
                "property_id": prop_id,
                "property_display_name": prop_names.get(prop_id, prop_id),
                "guest_name": _sanitize_guest_name(bk.get("guest_name")),
                "checkin_date": bk.get("check_in"),
                "checkout_date": bk.get("check_out"),
                "booking_status": bk.get("status"),
                "unread_count": summary["unread_count"],
                "last_message": summary["last_message"],
                "last_message_at": summary["last_message_at"],
                "last_sender_type": summary["last_sender_type"],
                "assigned_to": caller_user_id,
                "assigned_to_name": caller_name,
            })

        # --- 7. Sort: unread first, then newest last_message_at ---
        conversations.sort(
            key=lambda c: (
                0 if c["unread_count"] > 0 else 1,
                c["last_message_at"] or "",
            ),
            reverse=True,
        )
        # Fix: secondary sort (newest last) — re-sort with correct direction
        conversations.sort(
            key=lambda c: (
                0 if c["unread_count"] > 0 else 1,
                # Negate the time effect: we want newest last_message_at first within each group
                -(0 if not c["last_message_at"] else 1),
            )
        )
        # Simpler stable sort:
        has_unread = [c for c in conversations if c["unread_count"] > 0]
        no_unread  = [c for c in conversations if c["unread_count"] == 0]
        has_unread.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
        no_unread.sort(key=lambda c: c["last_message_at"] or "", reverse=True)
        conversations = has_unread + no_unread

        return JSONResponse(status_code=200, content={"conversations": conversations})

    except Exception as exc:
        logger.exception("get_guest_inbox error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ---------------------------------------------------------------------------
# GET /manager/guest-messages/{booking_id} — full thread for one stay
# ---------------------------------------------------------------------------

@router.get("/{booking_id}", summary="Full thread for one stay (Phase 1049)")
async def get_guest_thread(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the full message thread for one stay, chronological (oldest first).
    Also returns booking + property context for thread header rendering.

    Scoped: caller must be the assigned_om_id or have role=admin.
    """
    # assigned_om_id stores user_id (not tenant_id) — see resolve_conversation_owner
    caller_user_id = str(identity.get("user_id", "")).strip()
    caller_role = str(identity.get("role", "")).strip()
    if not caller_user_id:
        return JSONResponse(status_code=401, content={"error": "CALLER_NOT_IDENTIFIED"})

    try:
        db = client if client is not None else _get_db()

        # --- Fetch messages for this booking ---
        msg_res = (
            db.table("guest_chat_messages")
            .select("*")
            .eq("booking_id", booking_id)
            .order("created_at", desc=False)
            .execute()
        )
        messages = msg_res.data or []

        # Scope guard: caller must own (their user_id) or be admin
        owned = any(m.get("assigned_om_id") == caller_user_id for m in messages)
        if not owned and caller_role not in ("admin",):
            return JSONResponse(status_code=403, content={"error": "NOT_ASSIGNED"})

        # --- Booking context ---
        bk_data = {}
        try:
            bk_res = (
                db.table("booking_state")
                .select("booking_id,guest_name,check_in,check_out,property_id,status")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )
            if bk_res.data:
                bk_data = bk_res.data[0]
        except Exception:
            pass

        # --- Property name ---
        prop_display = bk_data.get("property_id", "")
        try:
            prop_res = (
                db.table("properties")
                .select("display_name")
                .eq("property_id", prop_display)
                .limit(1)
                .execute()
            )
            if prop_res.data:
                prop_display = prop_res.data[0].get("display_name") or prop_display
        except Exception:
            pass

        # Strip PII from messages before returning
        safe_messages = []
        for m in messages:
            safe_messages.append({
                "id": m["id"],
                "sender_type": m["sender_type"],
                "message": m["message"],
                "read_at": m.get("read_at"),
                "created_at": m.get("created_at"),
            })

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "property_id": bk_data.get("property_id", ""),
            "property_display_name": prop_display,
            "guest_name": _sanitize_guest_name(bk_data.get("guest_name")),
            "checkin_date": bk_data.get("check_in"),
            "checkout_date": bk_data.get("check_out"),
            "booking_status": bk_data.get("status"),
            "messages": safe_messages,
            "unread_count": sum(
                1 for m in messages
                if not m.get("read_at") and m.get("sender_type") == "guest"
            ),
        })

    except Exception as exc:
        logger.exception("get_guest_thread error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ---------------------------------------------------------------------------
# PATCH /manager/guest-messages/{booking_id}/read — mark thread as read
# ---------------------------------------------------------------------------

@router.patch("/{booking_id}/read", summary="Mark all messages in stay as read (Phase 1049)")
async def mark_thread_read(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Marks all guest messages in this stay-thread as read (sets read_at = now()).
    Only messages with sender_type='guest' and read_at IS NULL are updated.
    Caller must be the assigned owner or admin.
    """
    # assigned_om_id stores user_id (not tenant_id) — see resolve_conversation_owner
    caller_user_id = str(identity.get("user_id", "")).strip()
    caller_role = str(identity.get("role", "")).strip()
    if not caller_user_id:
        return JSONResponse(status_code=401, content={"error": "CALLER_NOT_IDENTIFIED"})

    try:
        db = client if client is not None else _get_db()
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        # Scope guard: caller must own this thread or be admin
        check_res = (
            db.table("guest_chat_messages")
            .select("id,assigned_om_id")
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        rows = check_res.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "THREAD_NOT_FOUND"})

        owned = any(r.get("assigned_om_id") == caller_user_id for r in rows)
        if not owned and caller_role not in ("admin",):
            return JSONResponse(status_code=403, content={"error": "NOT_ASSIGNED"})

        # Mark unread guest messages as read
        update_res = (
            db.table("guest_chat_messages")
            .update({"read_at": now_iso})
            .eq("booking_id", booking_id)
            .eq("sender_type", "guest")
            .is_("read_at", "null")
            .execute()
        )
        updated_count = len(update_res.data or [])

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "marked_read": updated_count,
            "read_at": now_iso,
        })

    except Exception as exc:
        logger.exception("mark_thread_read error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ---------------------------------------------------------------------------
# POST /manager/guest-messages/{booking_id}/reply — Phase 1052
# ---------------------------------------------------------------------------

@router.post("/{booking_id}/reply", summary="Send a host reply into a stay-thread (Phase 1052)")
async def reply_to_guest(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Sends a host reply into the given stay-thread.

    Stored in guest_chat_messages as:
        sender_type   = 'host'
        sender_id     = caller's user_id  (NOT tenant_id — per Phase 1052 identity rule)
        message       = body['message']
        booking_id    = path param
        property_id   = resolved from existing thread messages
        assigned_om_id = preserved from existing thread messages (Phase 1048 scaffold)
        tenant_id     = caller's tenant_id (for multi-tenant isolation)

    Scope guard: caller must be the assigned_om_id on existing thread messages, or role=admin.

    Returns the new message row immediately so the UI can append it optimistically.

    Guest-side portal visibility: NOT exposed yet. Phase 1053 controls that gate.
    """
    caller_user_id = str(identity.get("user_id", "")).strip()
    caller_tenant_id = str(identity.get("tenant_id", "")).strip()
    caller_role = str(identity.get("role", "")).strip()

    if not caller_user_id:
        return JSONResponse(status_code=401, content={"error": "CALLER_NOT_IDENTIFIED"})

    message_text = (body.get("message") or "").strip()
    if not message_text:
        return JSONResponse(status_code=400, content={"error": "EMPTY_MESSAGE"})

    if len(message_text) > 4000:
        return JSONResponse(status_code=400, content={"error": "MESSAGE_TOO_LONG"})

    try:
        db = client if client is not None else _get_db()

        # --- 1. Fetch existing thread to resolve property_id + assigned_om_id ---
        existing_res = (
            db.table("guest_chat_messages")
            .select("id,property_id,assigned_om_id,tenant_id")
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        existing = existing_res.data or []

        if not existing:
            return JSONResponse(status_code=404, content={"error": "THREAD_NOT_FOUND"})

        # Scope guard: caller must own this thread or be admin
        owned = any(r.get("assigned_om_id") == caller_user_id for r in existing)
        if not owned and caller_role not in ("admin",):
            return JSONResponse(status_code=403, content={"error": "NOT_ASSIGNED"})

        # Resolve property_id and assigned_om_id from existing thread
        thread_row = existing[0]
        property_id = thread_row.get("property_id") or ""
        assigned_om_id = thread_row.get("assigned_om_id") or caller_user_id
        # Use tenant from existing thread (consistent isolation scope)
        thread_tenant = thread_row.get("tenant_id") or caller_tenant_id

        # --- 2. Insert the host reply ---
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        new_row = {
            "booking_id":    booking_id,
            "property_id":   property_id,
            "tenant_id":     thread_tenant,
            "sender_type":   "host",
            "sender_id":     caller_user_id,   # user_id — NOT tenant_id (Phase 1052 identity rule)
            "message":       message_text,
            "assigned_om_id": assigned_om_id,  # preserve scaffold from thread
            "read_at":       now_iso,           # host's own message is implicitly read
            "created_at":    now_iso,
        }

        insert_res = (
            db.table("guest_chat_messages")
            .insert(new_row)
            .execute()
        )
        inserted = (insert_res.data or [{}])[0]

        logger.info(
            "reply_to_guest: booking=%s sender_user_id=%s msg_len=%d",
            booking_id, caller_user_id, len(message_text),
        )

        return JSONResponse(status_code=201, content={
            "message": {
                "id":          inserted.get("id"),
                "booking_id":  booking_id,
                "sender_type": "host",
                "sender_id":   caller_user_id,
                "message":     message_text,
                "read_at":     now_iso,
                "created_at":  now_iso,
            }
        })

    except Exception as exc:
        logger.exception("reply_to_guest error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})
