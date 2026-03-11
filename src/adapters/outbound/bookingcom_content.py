"""
Phase 250 — Booking.com Content API Adapter (Outbound)

Responsible for building the canonical Booking.com Content API payload
from iHouse Core property metadata, and dispatching the content push
request to Booking.com's Partner API.

Design:
    - Pure payload builder functions (testable without network)
    - One real HTTP call in `push_property_content()` — uses requests or
      the Booking.com Partner API base URL from env
    - Returns a structured PushResult dataclass

Booking.com Content API fields supported (subset of Partner API v2):
    - hotel_id          (from property metadata external_id or bcom_id)
    - name              (property display name)
    - description       (short description, max 2000 chars)
    - address           (full formatted address)
    - city              (city name)
    - country_code      (ISO 3166-1 alpha-2)
    - star_rating       (1-5, integer)
    - amenities         (list of Booking.com amenity IDs — numeric codes)
    - photos            (list of photo URLs)
    - check_in_time     (HH:MM, 24h)
    - check_out_time    (HH:MM, 24h)
    - cancellation_policy_code (e.g. "FLEX", "MODERATE", "STRICT")

Environment variables:
    BCOM_PARTNER_API_BASE   — base URL, default: https://distribution-xml.booking.com/2.10
    BCOM_HOTEL_USERNAME     — Booking.com hotel XML API username
    BCOM_HOTEL_PASSWORD     — Booking.com hotel XML API password

Invariants:
    - Does not write to any iHouse Core DB table
    - Does not read booking_state or financial_facts
    - All validation is done before the HTTP call
    - Returns PushResult — never raises on expected API errors
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BCOM_BASE = "https://distribution-xml.booking.com/2.10"
_MAX_DESCRIPTION_CHARS = 2000
_VALID_CANCELLATION_CODES = {"FLEX", "MODERATE", "STRICT", "NON_REFUNDABLE"}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PushResult:
    """Structured result of a Booking.com content push."""
    property_id: str
    bcom_hotel_id: Optional[str]
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    fields_pushed: List[str] = field(default_factory=list)
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Payload builder (pure — no network)
# ---------------------------------------------------------------------------

def build_content_payload(property_meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the Booking.com content API payload from iHouse property metadata.

    Args:
        property_meta: dict with at minimum:
            - bcom_hotel_id or external_id
            - name
            - description (optional, truncated to 2000 chars)
            - address, city, country_code
            - star_rating (optional)
            - amenities (optional, list of int codes)
            - photos (optional, list of URL strings)
            - check_in_time, check_out_time (optional, "HH:MM")
            - cancellation_policy_code (optional)

    Returns:
        dict — content payload ready for the Booking.com Partner API.

    Raises:
        ValueError if required fields are missing or invalid.
    """
    hotel_id = (
        property_meta.get("bcom_hotel_id")
        or property_meta.get("external_id")
    )
    if not hotel_id:
        raise ValueError("property_meta must include bcom_hotel_id or external_id")

    name = property_meta.get("name")
    if not name:
        raise ValueError("property_meta must include name")

    address = property_meta.get("address")
    city = property_meta.get("city")
    country_code = property_meta.get("country_code")
    if not all([address, city, country_code]):
        raise ValueError("property_meta must include address, city, country_code")

    if country_code and len(country_code) != 2:
        raise ValueError("country_code must be ISO 3166-1 alpha-2 (2 characters)")

    description = property_meta.get("description") or ""
    if len(description) > _MAX_DESCRIPTION_CHARS:
        description = description[:_MAX_DESCRIPTION_CHARS]
        logger.warning(
            "Description truncated to %d chars for hotel_id=%s",
            _MAX_DESCRIPTION_CHARS, hotel_id
        )

    cancellation_code = property_meta.get("cancellation_policy_code", "MODERATE")
    if cancellation_code not in _VALID_CANCELLATION_CODES:
        raise ValueError(
            f"cancellation_policy_code must be one of: "
            f"{', '.join(sorted(_VALID_CANCELLATION_CODES))}"
        )

    payload: Dict[str, Any] = {
        "hotel_id": str(hotel_id),
        "name": name,
        "description": description,
        "address": address,
        "city": city,
        "country_code": country_code.upper(),
        "cancellation_policy_code": cancellation_code,
    }

    # Optional fields — only included if provided
    star_rating = property_meta.get("star_rating")
    if star_rating is not None:
        payload["star_rating"] = int(star_rating)

    amenities = property_meta.get("amenities")
    if amenities:
        payload["amenities"] = [int(a) for a in amenities]

    photos = property_meta.get("photos")
    if photos:
        payload["photos"] = [str(url) for url in photos]

    check_in = property_meta.get("check_in_time")
    check_out = property_meta.get("check_out_time")
    if check_in:
        payload["check_in_time"] = check_in
    if check_out:
        payload["check_out_time"] = check_out

    return payload


def list_pushed_fields(payload: Dict[str, Any]) -> List[str]:
    """Return the list of content field keys in the payload."""
    return sorted(payload.keys())


# ---------------------------------------------------------------------------
# Network push (real HTTP — not tested without mocking)
# ---------------------------------------------------------------------------

def push_property_content(
    property_meta: Dict[str, Any],
    *,
    dry_run: bool = False,
    _http_client: Optional[Any] = None,
) -> PushResult:
    """
    Push property content to Booking.com Partner API.

    Args:
        property_meta: dict — see build_content_payload() for required fields
        dry_run: if True, builds and validates payload but does NOT send HTTP
        _http_client: optional requests-compatible client for testing

    Returns:
        PushResult
    """
    property_id = property_meta.get("property_id", "unknown")
    bcom_hotel_id = (
        property_meta.get("bcom_hotel_id")
        or property_meta.get("external_id")
    )

    try:
        payload = build_content_payload(property_meta)
        fields = list_pushed_fields(payload)
    except ValueError as exc:
        return PushResult(
            property_id=property_id,
            bcom_hotel_id=str(bcom_hotel_id) if bcom_hotel_id else None,
            success=False,
            error=str(exc),
            dry_run=dry_run,
        )

    if dry_run:
        logger.info(
            "DRY RUN — Booking.com content push for property=%s hotel_id=%s fields=%s",
            property_id, bcom_hotel_id, fields
        )
        return PushResult(
            property_id=property_id,
            bcom_hotel_id=str(bcom_hotel_id),
            success=True,
            status_code=None,
            fields_pushed=fields,
            dry_run=True,
        )

    # Live push
    base_url = os.environ.get("BCOM_PARTNER_API_BASE", _DEFAULT_BCOM_BASE)
    endpoint = f"{base_url}/hotels/{bcom_hotel_id}/content"
    username = os.environ.get("BCOM_HOTEL_USERNAME", "")
    password = os.environ.get("BCOM_HOTEL_PASSWORD", "")

    try:
        if _http_client is not None:
            resp = _http_client.put(endpoint, json=payload, auth=(username, password))
        else:  # pragma: no cover
            import requests
            resp = requests.put(
                endpoint,
                json=payload,
                auth=(username, password),
                timeout=15,
            )

        success = 200 <= resp.status_code < 300
        error = None if success else f"HTTP {resp.status_code}: {resp.text[:200]}"

        return PushResult(
            property_id=property_id,
            bcom_hotel_id=str(bcom_hotel_id),
            success=success,
            status_code=resp.status_code,
            error=error,
            fields_pushed=fields if success else [],
            dry_run=False,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Booking.com content push failed for property=%s: %s", property_id, exc
        )
        return PushResult(
            property_id=property_id,
            bcom_hotel_id=str(bcom_hotel_id) if bcom_hotel_id else None,
            success=False,
            error=str(exc),
            dry_run=False,
        )
