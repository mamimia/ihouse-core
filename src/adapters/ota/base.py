from abc import ABC, abstractmethod
from typing import Dict, Any

from .schemas import NormalizedBookingEvent, CanonicalExternalEnvelopeInput


class OTAAdapter(ABC):
    channel_name: str

    @abstractmethod
    def normalize(
        self,
        raw_payload: Dict[str, Any],
        *,
        tenant_id: str,
        source: str
    ) -> NormalizedBookingEvent:
        """
        Convert raw OTA payload into internal normalized structure.
        """
        raise NotImplementedError

    @abstractmethod
    def to_canonical_envelope(
        self,
        normalized: NormalizedBookingEvent
    ) -> CanonicalExternalEnvelopeInput:
        """
        Convert normalized object into canonical external envelope input.
        """
        raise NotImplementedError
