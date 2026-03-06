from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import (
    NormalizedBookingEvent,
    ClassifiedBookingEvent,
    CanonicalEnvelope,
)


class OTAAdapter(ABC):
    """
    Base interface for OTA adapters.

    Each provider adapter must implement:

        normalize()
        to_canonical_envelope()

    The shared pipeline performs validation and semantic classification.
    """

    provider: str

    @abstractmethod
    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Convert provider payload into normalized structure.
        """
        raise NotImplementedError

    @abstractmethod
    def to_canonical_envelope(
        self,
        classified: ClassifiedBookingEvent,
    ) -> CanonicalEnvelope:
        """
        Build canonical envelope based on semantic classification.
        """
        raise NotImplementedError
