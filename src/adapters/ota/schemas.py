from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


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
    """

    tenant_id: str
    type: str
    occurred_at: datetime
    payload: Dict[str, Any]
    idempotency_key: Optional[str] = None
