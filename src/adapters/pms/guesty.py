"""
Phase 805-807 — Guesty PMS Adapter
====================================

OAuth2 client_credentials authentication, property discovery, and booking fetch.

API docs: https://open-api.guesty.com/docs
Auth: POST /oauth2/token → access_token (24h TTL, auto-refresh)
Properties: GET /v1/listings
Bookings: GET /v1/reservations
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from adapters.pms.base import (
    PMSAdapter,
    PMSAuthResult,
    PMSBooking,
    PMSProperty,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://open-api.guesty.com"
TOKEN_URL = f"{BASE_URL}/oauth2/token"
LISTINGS_URL = f"{BASE_URL}/v1/listings"
RESERVATIONS_URL = f"{BASE_URL}/v1/reservations"

# Guesty status → Domaniqo canonical status
_STATUS_MAP = {
    "confirmed": "active",
    "checked_in": "active",
    "reserved": "active",
    "inquiry": "active",
    "canceled": "canceled",
    "cancelled": "canceled",
    "declined": "canceled",
    "expired": "canceled",
    "closed": "completed",
    "checked_out": "completed",
}


class GuestyAdapter(PMSAdapter):
    """Guesty PMS adapter — OAuth2 client_credentials."""

    provider = "guesty"

    def validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """Check that credentials contain client_id and client_secret."""
        return bool(
            credentials.get("client_id", "").strip()
            and credentials.get("client_secret", "").strip()
        )

    def authenticate(self, credentials: Dict[str, str]) -> PMSAuthResult:
        """
        OAuth2 client_credentials → access_token.

        POST https://open-api.guesty.com/oauth2/token
        Body: { grant_type: "client_credentials", scope: "open-api", client_secret, client_id }
        """
        if not self.validate_credentials(credentials):
            return PMSAuthResult(success=False, error="Missing client_id or client_secret")

        try:
            resp = requests.post(
                TOKEN_URL,
                json={
                    "grant_type": "client_credentials",
                    "scope": "open-api",
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
                headers={"Content-Type": "application/json"},
                timeout=15,
            )

            if resp.status_code != 200:
                body = resp.text[:500]
                logger.warning("Guesty auth failed: %d — %s", resp.status_code, body)
                return PMSAuthResult(success=False, error=f"HTTP {resp.status_code}: {body}")

            data = resp.json()
            token = data.get("access_token")
            expires_in = data.get("expires_in", 86400)  # default 24h

            if not token:
                return PMSAuthResult(success=False, error="No access_token in response")

            return PMSAuthResult(
                success=True,
                access_token=token,
                expires_in_seconds=expires_in,
            )

        except requests.RequestException as exc:
            logger.exception("Guesty auth error: %s", exc)
            return PMSAuthResult(success=False, error=str(exc))

    def refresh_token(self, credentials: Dict[str, str], current_token: str) -> PMSAuthResult:
        """Guesty uses client_credentials — refresh = re-authenticate."""
        return self.authenticate(credentials)

    def discover_properties(self, access_token: str) -> List[PMSProperty]:
        """
        GET /v1/listings — fetch all properties from Guesty account.
        Handles pagination (default limit=25, max=100).
        """
        properties: List[PMSProperty] = []
        skip = 0
        limit = 100

        while True:
            try:
                resp = requests.get(
                    LISTINGS_URL,
                    params={"skip": skip, "limit": limit, "fields": "title address bedrooms bathrooms accommodates propertyType pictures"},
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30,
                )

                if resp.status_code != 200:
                    logger.warning("Guesty listings failed: %d", resp.status_code)
                    break

                data = resp.json()
                results = data.get("results", [])

                if not results:
                    break

                for listing in results:
                    addr = listing.get("address", {}) or {}
                    photos = []
                    for pic in (listing.get("pictures", []) or []):
                        url = pic.get("original") or pic.get("thumbnail")
                        if url:
                            photos.append(url)

                    properties.append(PMSProperty(
                        external_id=listing.get("_id", ""),
                        name=listing.get("title", "Untitled"),
                        address=addr.get("full", ""),
                        city=addr.get("city", ""),
                        country=addr.get("country", ""),
                        bedrooms=listing.get("bedrooms"),
                        bathrooms=listing.get("bathrooms"),
                        max_guests=listing.get("accommodates"),
                        property_type=listing.get("propertyType"),
                        photos=photos[:5],  # limit to 5
                        raw=listing,
                    ))

                # Pagination
                count = data.get("count", 0)
                skip += limit
                if skip >= count:
                    break

            except requests.RequestException as exc:
                logger.exception("Guesty listings error: %s", exc)
                break

        logger.info("Guesty discover_properties: found %d properties", len(properties))
        return properties

    def fetch_bookings(
        self,
        access_token: str,
        since: Optional[str] = None,
        property_external_id: Optional[str] = None,
    ) -> List[PMSBooking]:
        """
        GET /v1/reservations — fetch bookings.
        Supports pagination and filtering by update time.
        """
        bookings: List[PMSBooking] = []
        skip = 0
        limit = 100

        while True:
            try:
                params: Dict[str, Any] = {"skip": skip, "limit": limit}

                if since:
                    params["filters"] = [{"field": "lastUpdatedAt", "operator": "$gte", "value": since}]

                if property_external_id:
                    params["listingId"] = property_external_id

                resp = requests.get(
                    RESERVATIONS_URL,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30,
                )

                if resp.status_code != 200:
                    logger.warning("Guesty reservations failed: %d", resp.status_code)
                    break

                data = resp.json()
                results = data.get("results", [])

                if not results:
                    break

                for res in results:
                    guest = res.get("guest", {}) or {}
                    money = res.get("money", {}) or {}

                    # Extract channel from source
                    source = res.get("source", "")
                    channel = source if source else res.get("integration", {}).get("platform", "")

                    raw_status = res.get("status", "unknown").lower()
                    canonical_status = _STATUS_MAP.get(raw_status, "active")

                    bookings.append(PMSBooking(
                        external_id=res.get("confirmationCode", res.get("_id", "")),
                        property_external_id=res.get("listingId", ""),
                        status=canonical_status,
                        check_in=res.get("checkIn", "")[:10] if res.get("checkIn") else "",
                        check_out=res.get("checkOut", "")[:10] if res.get("checkOut") else "",
                        guest_name=guest.get("fullName", ""),
                        guest_email=guest.get("email", ""),
                        guest_phone=guest.get("phone", ""),
                        guest_count=res.get("guestsCount"),
                        total_price=money.get("totalPrice"),
                        currency=money.get("currency", "").upper()[:3] if money.get("currency") else None,
                        channel=channel,
                        commission=money.get("channelCommission"),
                        net_to_property=money.get("hostPayout"),
                        special_requests=res.get("customFields", {}).get("specialRequests", ""),
                        internal_notes=res.get("note", ""),
                        cancellation_policy=res.get("cancellationPolicy", ""),
                        raw=res,
                    ))

                # Pagination
                count = data.get("count", 0)
                skip += limit
                if skip >= count:
                    break

            except requests.RequestException as exc:
                logger.exception("Guesty reservations error: %s", exc)
                break

        logger.info("Guesty fetch_bookings: fetched %d bookings", len(bookings))
        return bookings
