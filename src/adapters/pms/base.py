"""
Phase 804 — PMS Adapter Interface
==================================

Abstract base class for PMS/Channel Manager adapters.
Every PMS provider implements this interface — one adapter per provider.

Convention:
  adapters/pms/guesty.py
  adapters/pms/hostaway.py
  (future providers follow same pattern)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PMSProperty:
    """A property discovered from a PMS."""
    external_id: str           # PMS's ID for this property
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    max_guests: Optional[int] = None
    property_type: Optional[str] = None
    photos: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PMSBooking:
    """A booking fetched from a PMS — pre-normalization."""
    external_id: str           # PMS's reservation ID
    property_external_id: str  # PMS's property ID
    status: str                # raw status from PMS
    check_in: str              # ISO date
    check_out: str             # ISO date
    guest_name: Optional[str] = None
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    guest_count: Optional[int] = None
    total_price: Optional[float] = None
    currency: Optional[str] = None
    channel: Optional[str] = None     # originating OTA (airbnb, booking.com, etc)
    commission: Optional[float] = None
    net_to_property: Optional[float] = None
    special_requests: Optional[str] = None
    internal_notes: Optional[str] = None
    cancellation_policy: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PMSAuthResult:
    """Result of PMS authentication."""
    success: bool
    access_token: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    error: Optional[str] = None


@dataclass
class PMSSyncResult:
    """Result of a booking sync cycle."""
    bookings_fetched: int = 0
    bookings_new: int = 0
    bookings_updated: int = 0
    bookings_canceled: int = 0
    errors: int = 0
    error_details: List[str] = field(default_factory=list)


class PMSAdapter(ABC):
    """
    Abstract PMS adapter. Each provider implements this interface.

    Lifecycle:
      1. authenticate() — get/refresh access token
      2. discover_properties() — list properties from PMS
      3. fetch_bookings() — pull reservations (optionally since a timestamp)
    """

    provider: str  # 'guesty' | 'hostaway'

    @abstractmethod
    def authenticate(self, credentials: Dict[str, str]) -> PMSAuthResult:
        """
        Authenticate with the PMS using stored credentials.
        Returns access_token on success, error on failure.
        """
        ...

    @abstractmethod
    def refresh_token(self, credentials: Dict[str, str], current_token: str) -> PMSAuthResult:
        """
        Refresh an expired or near-expiry token.
        Some providers (Hostaway) have long-lived tokens — this may be a no-op.
        """
        ...

    @abstractmethod
    def discover_properties(self, access_token: str) -> List[PMSProperty]:
        """
        Fetch all properties from the PMS account.
        Returns list of PMSProperty with external IDs and metadata.
        """
        ...

    @abstractmethod
    def fetch_bookings(
        self,
        access_token: str,
        since: Optional[str] = None,
        property_external_id: Optional[str] = None,
    ) -> List[PMSBooking]:
        """
        Fetch reservations from the PMS.

        Args:
            access_token: valid auth token
            since: ISO timestamp — only fetch bookings updated after this time
            property_external_id: optional filter for a specific property

        Returns:
            List of raw PMSBooking objects (pre-normalization).
        """
        ...

    @abstractmethod
    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Quick validation that credentials are well-formed (not expired, right format).
        Does NOT make API call — just structural check.
        """
        ...
