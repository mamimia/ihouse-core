#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any, Dict


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def main() -> int:
    try:
        payload: Dict[str, Any] = json.load(sys.stdin)
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_NOT_JSON"}))
        return 2

    provider = _as_str(payload.get("provider")).strip()
    external_booking_id = _as_str(payload.get("external_booking_id")).strip()
    property_id = _as_str(payload.get("property_id")).strip()
    provider_payload = payload.get("provider_payload")

    if not provider or not external_booking_id or not property_id or not isinstance(provider_payload, dict):
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    status = _as_str(provider_payload.get("status")).strip().lower()
    if status == "cancelled":
        action = "cancel"
        normalized_status = "cancelled"
    else:
        action = "upsert"
        normalized_status = status or "confirmed"

    # Minimal normalized fields expected from provider_payload
    # These are strings so upstream providers can send any shape, we normalize here.
    start_date = _as_str(provider_payload.get("start_date")).strip()
    end_date = _as_str(provider_payload.get("end_date")).strip()
    guest_name = _as_str(provider_payload.get("guest_name")).strip() or None

    if action == "upsert" and (not start_date or not end_date):
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID", "missing": ["payload.start_date", "payload.end_date"]}))
        return 2

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

    result = {
        "decision": {"action": action},
        "booking_record": booking_record,
    }

    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
