from __future__ import annotations

from typing import Any, Dict

from core.skill_contract import EmittedEvent, SkillOutput


def run(payload: Dict[str, Any]) -> SkillOutput:
    """
    Transforms the OTA canonical envelope payload into the canonical emitted
    BOOKING_AMENDED business event shape required by apply_envelope.

    Expected incoming payload fields (from OTA adapter, built in to_canonical_envelope):
        provider            -> maps to source (not used directly in emitted — booking_id already built)
        reservation_id      -> maps to reservation_ref (used only if booking_id missing)
        property_id         -> ignored at amendment stage (booking exists)
        booking_id          -> the canonical booking_id (provider_reservationref)
        new_check_in        -> optional — new check-in date (str | None)
        new_check_out       -> optional — new check-out date (str | None)
        new_guest_count     -> optional — new guest count (int | None)
        amendment_reason    -> optional — human-readable reason (str | None)
        provider_payload    -> raw OTA payload (not forwarded)

    Outgoing emitted event payload fields required by apply_envelope BOOKING_AMENDED branch:
        booking_id          (required — used for SELECT FOR UPDATE row lock)
        new_check_in        (optional — COALESCE in SQL preserves existing if absent)
        new_check_out       (optional — COALESCE in SQL preserves existing if absent)

    Invariants:
    - booking_id is always taken from the pre-built field in the adapter payload
    - never reads booking_state
    - never bypasses apply_envelope
    - COALESCE in apply_envelope handles None fields — we pass only what was explicitly amended
    """
    booking_id: str = payload.get("booking_id", "")
    new_check_in = payload.get("new_check_in")
    new_check_out = payload.get("new_check_out")
    new_guest_count = payload.get("new_guest_count")
    amendment_reason = payload.get("amendment_reason")

    # Fallback: reconstruct booking_id if adapter didn't set it (safety net only)
    if not booking_id:
        source = payload.get("provider", "")
        reservation_ref = payload.get("reservation_id", "")
        booking_id = f"{source}_{reservation_ref}" if source and reservation_ref else reservation_ref

    emitted_payload: Dict[str, Any] = {"booking_id": booking_id}

    # Include only explicitly-amended fields so apply_envelope COALESCE preserves existing values
    if new_check_in is not None:
        emitted_payload["new_check_in"] = new_check_in
    if new_check_out is not None:
        emitted_payload["new_check_out"] = new_check_out
    if new_guest_count is not None:
        emitted_payload["new_guest_count"] = new_guest_count
    if amendment_reason is not None:
        emitted_payload["amendment_reason"] = amendment_reason

    return SkillOutput(
        apply_result="APPLIED",
        reason="OTA_BOOKING_AMENDED",
        state_upserts=[],
        events_to_emit=[
            EmittedEvent(type="BOOKING_AMENDED", payload=emitted_payload)
        ],
        domain_effects={},
    )
