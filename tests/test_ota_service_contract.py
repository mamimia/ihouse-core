from __future__ import annotations

from typing import Any, Dict

import adapters.ota.service as service_module


def test_ingest_provider_event_is_thin_wrapper(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    expected_envelope = object()

    def fake_process_ota_event(*, provider: str, payload: Dict[str, Any], tenant_id: str) -> object:
        calls.append(
            {
                "provider": provider,
                "payload": payload,
                "tenant_id": tenant_id,
            }
        )
        return expected_envelope

    monkeypatch.setattr(service_module, "process_ota_event", fake_process_ota_event)

    payload = {"event_id": "evt_001", "event_type": "created"}

    result = service_module.ingest_provider_event(
        provider="bookingcom",
        payload=payload,
        tenant_id="tenant_001",
    )

    assert result is expected_envelope
    assert calls == [
        {
            "provider": "bookingcom",
            "payload": payload,
            "tenant_id": "tenant_001",
        }
    ]
