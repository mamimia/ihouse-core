from __future__ import annotations

from typing import Any, Dict, List

from core.skill_contract import SkillOutput, StateUpsert, EmittedEvent


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _reject(reason: str, missing: List[str] | None = None) -> SkillOutput:
    effects: Dict[str, Any] = {"error": reason}
    if missing:
        effects["missing"] = list(missing)
    return SkillOutput(
        apply_result="REJECTED",
        reason=reason,
        state_upserts=[],
        events_to_emit=[],
        domain_effects=effects,
    )


def run(payload: Dict[str, Any]) -> SkillOutput:
    provider = _as_str(payload.get("provider")).strip()
    external_booking_id = _as_str(payload.get("external_booking_id")).strip()
    property_id = _as_str(payload.get("property_id")).strip()
    provider_payload = payload.get("provider_payload")

    if not provider or not external_booking_id or not property_id or not isinstance(provider_payload, dict):
        return _reject("INPUT_INVALID")

    status = _as_str(provider_payload.get("status")).strip().lower()
    if status == "cancelled":
        action = "cancel"
        normalized_status = "cancelled"
    else:
        action = "upsert"
        normalized_status = status or "confirmed"

    start_date = _as_str(provider_payload.get("start_date")).strip()
    end_date = _as_str(provider_payload.get("end_date")).strip()
    guest_name = _as_str(provider_payload.get("guest_name")).strip()

    if action == "upsert" and (not start_date or not end_date):
        return _reject("INPUT_INVALID", missing=["payload.start_date", "payload.end_date"])

    booking_id = f"b_{provider}_{external_booking_id}"
    external_ref = f"{provider}:{external_booking_id}"

    booking_record = {
        "booking_id": booking_id,
        "property_id": property_id,
        "external_ref": external_ref,
        "start_date": start_date,
        "end_date": end_date,
        "status": normalized_status,
        "guest_name": guest_name,
    }

    upserts = [
        StateUpsert(
            key=booking_id,
            value=booking_record,
            expected_last_envelope_id=None,
        )
    ]

    events: List[EmittedEvent] = [
        EmittedEvent(
            type="booking_sync_ingested",
            payload={
                "booking_id": booking_id,
                "property_id": property_id,
                "external_ref": external_ref,
                "action": action,
                "status": normalized_status,
            },
        )
    ]

    return SkillOutput(
        apply_result="APPLIED",
        reason=None,
        state_upserts=upserts,
        events_to_emit=events,
        domain_effects={"decision": {"action": action}, "booking_record": booking_record},
    )
