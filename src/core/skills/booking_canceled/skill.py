from __future__ import annotations

from typing import Any, Dict

from core.skill_contract import EmittedEvent, SkillOutput


def run(payload: Dict[str, Any]) -> SkillOutput:
    """
    Transforms the OTA canonical envelope payload into the canonical emitted
    BOOKING_CANCELED business event shape required by apply_envelope.

    Expected incoming payload fields (from OTA adapter):
        provider        -> maps to source
        reservation_id  -> maps to reservation_ref (used to resolve booking_id)
        tenant_id       -> optional

    Outgoing emitted event payload fields required by apply_envelope:
        booking_id  (constructed: "{source}_{reservation_ref}")
    """
    source = payload.get("provider", "")
    reservation_ref = payload.get("reservation_id", "")

    booking_id = f"{source}_{reservation_ref}" if source and reservation_ref else reservation_ref

    return SkillOutput(
        apply_result="APPLIED",
        reason="OTA_BOOKING_CANCELED",
        state_upserts=[],
        events_to_emit=[
            EmittedEvent(type="BOOKING_CANCELED", payload={"booking_id": booking_id})
        ],
        domain_effects={},
    )
