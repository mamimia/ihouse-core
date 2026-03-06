from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class NormalizedBookingEvent:
    canonical_type: str
    tenant_id: str
    source: str
    reservation_ref: str
    property_id: str
    occurred_at: str
    check_in: Optional[str]
    check_out: Optional[str]
    raw_event_name: str
    raw_external_id: Optional[str]
    idempotency_request_id: str
    raw_payload: Dict[str, Any]


@dataclass
class CanonicalExternalEnvelopeInput:
    type: str
    payload: Dict[str, Any]
    occurred_at: str
    idempotency_request_id: str


@dataclass
class IngestionResult:
    status: str
    channel: str
    request_id: str
    reason: Optional[str] = None


@dataclass
class IngestionContext:
    tenant_id: str
    source: str
