from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

if TYPE_CHECKING:
    from .financial_extractor import BookingFinancialFacts


@dataclass
class NormalizedBookingEvent:
    """
    Provider payload normalized into a stable structure.

    This stage represents transport normalization only.
    It MUST NOT contain canonical business event kinds.
    """

    tenant_id: str
    provider: str
    external_event_id: str
    reservation_id: str
    property_id: str
    occurred_at: datetime
    payload: Dict[str, Any]
    financial_facts: Optional["BookingFinancialFacts"] = None


@dataclass
class ClassifiedBookingEvent:
    """
    Semantic classification result.

    semantic_kind values are defined by semantics.py
    and represent business lifecycle meaning.
    """

    normalized: NormalizedBookingEvent
    semantic_kind: str


@dataclass
class CanonicalEnvelope:
    """
    Canonical envelope that enters the core ingestion system.

    Separation (Phase 76):
      occurred_at  — ISO datetime str from the OTA provider — business event time
      recorded_at  — ISO datetime str set by OUR server when the event is received

    recorded_at is always the server wall-clock at ingest time and is never
    overridable by the OTA provider payload.
    """

    tenant_id: str
    type: str
    occurred_at: Union[datetime, str]
    payload: Dict[str, Any]
    idempotency_key: Optional[str] = None
    recorded_at: Optional[str] = None  # Phase 76: server ingestion timestamp (ISO UTC)


@dataclass(frozen=True)
class AmendmentFields:
    """
    Canonical, provider-agnostic amendment field container.

    Represents WHAT changed in a booking amendment, independent of
    the OTA provider's payload structure.

    All fields are Optional — a provider may send only a partial
    amendment (e.g. only dates, not guest count).

    This is the normalized output of amendment_extractor.py and
    the canonical input to apply_envelope when BOOKING_AMENDED is
    implemented (Phase 50).

    Immutable: created once, never mutated.
    """

    new_check_in: Optional[str]       # ISO date string e.g. "2026-09-01"
    new_check_out: Optional[str]      # ISO date string e.g. "2026-09-05"
    new_guest_count: Optional[int]    # integer guest count or None
    amendment_reason: Optional[str]   # provider-supplied note, or None
