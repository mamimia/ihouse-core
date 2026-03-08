from __future__ import annotations

from typing import Any, Dict

import adapters.ota.pipeline as pipeline_module


class _FakeAdapter:
    def __init__(self, calls: list[tuple[str, Any]]) -> None:
        self.calls = calls

    def normalize(self, payload: Dict[str, Any]) -> object:
        self.calls.append(("normalize", dict(payload)))
        return NORMALIZED

    def to_canonical_envelope(self, classified: object) -> object:
        self.calls.append(("to_canonical_envelope", classified))
        return ENVELOPE


NORMALIZED = object()
CLASSIFIED = object()
ENVELOPE = object()


def test_process_ota_event_preserves_ordered_shared_pipeline(monkeypatch) -> None:
    calls: list[tuple[str, Any]] = []
    adapter = _FakeAdapter(calls)

    def fake_get_adapter(provider: str) -> object:
        calls.append(("get_adapter", provider))
        return adapter

    def fake_validate_normalized_event(normalized: object) -> None:
        calls.append(("validate_normalized_event", normalized))

    def fake_classify_normalized_event(normalized: object) -> object:
        calls.append(("classify_normalized_event", normalized))
        return CLASSIFIED

    def fake_validate_classified_event(classified: object) -> None:
        calls.append(("validate_classified_event", classified))

    def fake_validate_canonical_envelope(envelope: object) -> None:
        calls.append(("validate_canonical_envelope", envelope))

    monkeypatch.setattr(pipeline_module, "get_adapter", fake_get_adapter)
    monkeypatch.setattr(pipeline_module, "validate_normalized_event", fake_validate_normalized_event)
    monkeypatch.setattr(pipeline_module, "classify_normalized_event", fake_classify_normalized_event)
    monkeypatch.setattr(pipeline_module, "validate_classified_event", fake_validate_classified_event)
    monkeypatch.setattr(pipeline_module, "validate_canonical_envelope", fake_validate_canonical_envelope)

    payload = {
        "event_id": "evt_001",
        "event_type": "created",
        "reservation_id": "res_001",
        "occurred_at": "2026-03-08T10:00:00Z",
    }

    result = pipeline_module.process_ota_event(
        provider="bookingcom",
        payload=payload,
        tenant_id="tenant_001",
    )


    assert result is ENVELOPE
    assert calls == [
        ("get_adapter", "bookingcom"),
        (
            "normalize",
            {
                "event_id": "evt_001",
                "event_type": "created",
                "reservation_id": "res_001",
                "occurred_at": "2026-03-08T10:00:00Z",
                "tenant_id": "tenant_001",
            },
        ),
        ("validate_normalized_event", NORMALIZED),
        ("classify_normalized_event", NORMALIZED),
        ("validate_classified_event", CLASSIFIED),
        ("to_canonical_envelope", CLASSIFIED),
        ("validate_canonical_envelope", ENVELOPE),
    ]
