from __future__ import annotations

from typing import Any, Dict

from core.skill_contract import EmittedEvent, SkillOutput


def run(payload: Dict[str, Any]) -> SkillOutput:
    """
    Transforms the OTA canonical envelope payload into the canonical emitted
    BOOKING_CREATED business event shape required by apply_envelope.

    Expected incoming payload fields (from OTA adapter):
        provider         -> maps to source
        reservation_id   -> maps to reservation_ref
        property_id      -> maps to property_id
        tenant_id        -> maps to tenant_id
        provider_payload -> contains check_in / check_out

    Outgoing emitted event payload fields required by apply_envelope:
        booking_id       (constructed: "{source}_{reservation_ref}")
        tenant_id
        source
        reservation_ref
        property_id
        check_in         (optional)
        check_out        (optional)
    """
    source = payload.get("provider", "")
    reservation_ref = payload.get("reservation_id", "")
    property_id = payload.get("property_id", "")
    tenant_id = payload.get("tenant_id", "")
    provider_payload = payload.get("provider_payload") or {}

    booking_id = f"{source}_{reservation_ref}" if source and reservation_ref else reservation_ref

    emitted_payload: Dict[str, Any] = {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "source": source,
        "reservation_ref": reservation_ref,
        "property_id": property_id,
    }

    check_in = provider_payload.get("check_in") or provider_payload.get("start_date")
    check_out = provider_payload.get("check_out") or provider_payload.get("end_date")
    if check_in:
        emitted_payload["check_in"] = check_in
    if check_out:
        emitted_payload["check_out"] = check_out

    return SkillOutput(
        apply_result="APPLIED",
        reason="OTA_BOOKING_CREATED",
        state_upserts=[],
        events_to_emit=[
            EmittedEvent(type="BOOKING_CREATED", payload=emitted_payload)
        ],
        domain_effects={},
    )
