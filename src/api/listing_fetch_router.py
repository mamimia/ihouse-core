"""
Phase 844 v3 — Listing URL Fetch / Import

Endpoint:
    POST /properties/{id}/fetch-listing
    Body: { listing_url: str }

Attempts to extract structured data from the listing URL using:
  1. Open Graph meta tags
  2. JSON-LD schema.org structured data
  3. Basic HTML title/meta description

Explicitly returns what was and was not extracted.
Does NOT claim full import if not proven.

Note: Airbnb, Booking.com, and most OTAs block server-side scraping.
Only publicly accessible pages with Open Graph / JSON-LD will yield data.
"""
from __future__ import annotations

import json
import logging
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/properties", tags=["properties"])

_TIMEOUT = 10.0
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; iHouseBot/1.0; +https://domaniqo.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Known platforms that block server-side scraping
_BLOCKED_PLATFORMS = ["airbnb.com", "booking.com", "vrbo.com", "homeaway.com", "expedia.com"]


def _detect_blocked_platform(url: str) -> Optional[str]:
    host = urlparse(url).hostname or ""
    for platform in _BLOCKED_PLATFORMS:
        if platform in host:
            return platform
    return None


class _MetaParser(HTMLParser):
    """Lightweight HTML parser for OG tags, JSON-LD, embedded JSON, and basic meta."""

    def __init__(self):
        super().__init__()
        self.og: Dict[str, str] = {}
        self.og_images: List[str] = []  # collect ALL og:image values
        self.meta: Dict[str, str] = {}
        self.jsonld: List[Dict] = []
        self.title: str = ""
        self._in_title = False
        self._in_script_jsonld = False
        self._in_script = False
        self._script_buf = ""
        self._scripts: List[str] = []  # all script contents for embedded data mining

    def handle_starttag(self, tag: str, attrs):
        a = dict(attrs)
        if tag == "meta":
            prop = a.get("property") or a.get("name") or ""
            content = a.get("content") or ""
            if prop == "og:image" or prop == "og:image:url":
                if content and content not in self.og_images:
                    self.og_images.append(content)
            if prop.startswith("og:"):
                self.og[prop[3:]] = content
            elif prop:
                self.meta[prop] = content
        elif tag == "title":
            self._in_title = True
        elif tag == "script":
            if a.get("type") == "application/ld+json":
                self._in_script_jsonld = True
                self._script_buf = ""
            else:
                self._in_script = True
                self._script_buf = ""

    def handle_endtag(self, tag: str):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._in_script_jsonld:
                self._in_script_jsonld = False
                try:
                    data = json.loads(self._script_buf)
                    if isinstance(data, list):
                        self.jsonld.extend(data)
                    elif isinstance(data, dict):
                        self.jsonld.append(data)
                except Exception:
                    pass
            elif self._in_script:
                self._in_script = False
                # Keep scripts that might contain listing data
                if len(self._script_buf) > 100:
                    self._scripts.append(self._script_buf)

    def handle_data(self, data: str):
        if self._in_title:
            self.title += data
        elif self._in_script_jsonld or self._in_script:
            self._script_buf += data


def _parse_airbnb_og_title(title: str) -> Dict[str, Any]:
    """
    Parse Airbnb-style OG titles like:
        'Home in Ko Pha-Ngan · ★5.0 · 2 bedrooms · 2.5 baths'
        'Entire villa in Koh Samui · ★4.9 · 3 bedrooms · 4 beds · 2 baths'
    Returns extracted fields: city, bedrooms, beds, bathrooms, max_guests.
    """
    result: Dict[str, Any] = {}
    parts = [p.strip() for p in title.split("·")]

    for part in parts:
        lower = part.lower()

        # "Home in Ko Pha-Ngan" / "Entire villa in Koh Samui"
        m_location = re.match(r"(?:entire\s+\w+\s+in|home\s+in|room\s+in|place\s+in)\s+(.+)", lower)
        if m_location:
            result["city"] = part[m_location.start(1):m_location.end(1)].strip()
            continue

        # "2 bedrooms" / "1 bedroom"
        m_bed = re.search(r"(\d+)\s+bedroom", lower)
        if m_bed:
            result["bedrooms"] = int(m_bed.group(1))
            continue

        # "4 beds" / "1 bed"
        m_beds = re.search(r"(\d+)\s+bed(?!room)", lower)
        if m_beds:
            result["beds"] = int(m_beds.group(1))
            continue

        # "2.5 baths" / "2 baths" / "1 bath"
        m_bath = re.search(r"([\d.]+)\s+bath", lower)
        if m_bath:
            result["bathrooms"] = float(m_bath.group(1))
            continue

        # "6 guests" / "8 guests"
        m_guests = re.search(r"(\d+)\s+guest", lower)
        if m_guests:
            result["max_guests"] = int(m_guests.group(1))
            continue

    return result


def _extract_property_name(og_desc: str) -> str:
    """
    Extract the actual property name from an OG description.
    Airbnb format: 'Emuna Villa | Stylish 2BR Tropical Hideaway'
    We take the first segment before | or – or - (if the rest looks like a tagline).
    """
    # Split on common delimiters
    for sep in [" | ", " – ", " — ", " - "]:
        if sep in og_desc:
            first = og_desc.split(sep)[0].strip()
            # Only use if it looks like a name (not too long, not a sentence)
            if len(first) < 80 and not first.endswith("."):
                return first
    # If no delimiter, use the whole thing if it's short enough
    if len(og_desc) < 60:
        return og_desc.strip()
    return ""


def _is_airbnb_style_title(title: str) -> bool:
    """Check if OG title looks like Airbnb's generic format."""
    lower = title.lower()
    return ("·" in title and ("bedroom" in lower or "bath" in lower)) or \
           re.match(r"(?:entire|home|room|place)\s+(?:\w+\s+)?in\s+", lower) is not None


def _extract_from_parsed(parser: _MetaParser, url: str) -> Dict[str, Any]:
    """Build extracted fields from parser results — smart about Airbnb-style OG."""
    extracted: Dict[str, Any] = {}
    og_title = (parser.og.get("title") or "").strip()
    og_desc = (parser.og.get("description") or parser.meta.get("description") or "").strip()
    html_title = (parser.title or "").strip()

    # ── Smart Airbnb-style parsing ───────────────────────────────────────
    if _is_airbnb_style_title(og_title):
        # OG title has metadata (bedrooms, baths, city) — NOT the property name
        parsed = _parse_airbnb_og_title(og_title)
        if parsed.get("city"):
            extracted["city"] = parsed["city"]
        if parsed.get("bedrooms"):
            extracted["bedrooms"] = parsed["bedrooms"]
        if parsed.get("beds"):
            extracted["beds"] = parsed["beds"]
        if parsed.get("bathrooms"):
            extracted["bathrooms"] = parsed["bathrooms"]
        if parsed.get("max_guests"):
            extracted["max_guests"] = parsed["max_guests"]

        # OG description has the ACTUAL property name
        if og_desc:
            prop_name = _extract_property_name(og_desc)
            if prop_name:
                extracted["name"] = prop_name
            # Use full OG description as the description
            extracted["description"] = og_desc
    else:
        # Non-Airbnb: use OG title as name, OG description as description
        if og_title:
            extracted["name"] = og_title
        elif html_title:
            extracted["name"] = html_title
        if og_desc:
            extracted["description"] = og_desc

    # ── Photos from ALL OG images ────────────────────────────────────────
    photos: List[str] = list(parser.og_images)  # already deduplicated
    extracted["photos"] = photos

    # ── JSON-LD structured data (more reliable when available) ───────────
    for ld in parser.jsonld:
        t = ld.get("@type", "")
        if not isinstance(t, str):
            continue
        t_lower = t.lower()

        if "lodging" in t_lower or "accommodation" in t_lower or "property" in t_lower or "vacation" in t_lower:
            if not extracted.get("name") and ld.get("name"):
                extracted["name"] = str(ld["name"]).strip()
            if not extracted.get("description") and ld.get("description"):
                extracted["description"] = str(ld["description"]).strip()

            # Address
            address = ld.get("address") or {}
            if isinstance(address, dict):
                city = address.get("addressLocality") or address.get("addressRegion") or ""
                country = address.get("addressCountry") or ""
                street = address.get("streetAddress") or ""
                if city:
                    extracted["city"] = city
                if country:
                    extracted["country"] = country
                if street:
                    extracted["address"] = street

            # Coordinates from geo
            geo = ld.get("geo") or {}
            if isinstance(geo, dict) and geo.get("latitude"):
                extracted["latitude"] = geo["latitude"]
                extracted["longitude"] = geo.get("longitude")

            # Capacity
            if not extracted.get("max_guests") and ld.get("occupancy"):
                occ = ld["occupancy"]
                if isinstance(occ, dict) and occ.get("maxValue"):
                    extracted["max_guests"] = int(occ["maxValue"])

            # Number of rooms
            if not extracted.get("bedrooms") and ld.get("numberOfRooms"):
                extracted["bedrooms"] = int(ld["numberOfRooms"])

            # Photos from JSON-LD
            ld_photos = ld.get("photo") or ld.get("image") or []
            if isinstance(ld_photos, str):
                ld_photos = [ld_photos]
            if isinstance(ld_photos, list):
                for p in ld_photos:
                    img_url = p.get("contentUrl") if isinstance(p, dict) else str(p) if isinstance(p, str) else None
                    if img_url and img_url.startswith("http") and img_url not in photos:
                        photos.append(img_url)

            # Amenities
            amenity = ld.get("amenityFeature") or []
            if isinstance(amenity, list):
                amenities = []
                for item in amenity:
                    if isinstance(item, dict) and item.get("name"):
                        amenities.append(item["name"])
                    elif isinstance(item, str):
                        amenities.append(item)
                if amenities:
                    extracted["amenities"] = amenities

    # ── Mine embedded JSON from script tags ──────────────────────────────
    # Airbnb, VRBO, and others embed listing data in inline scripts
    _mine_embedded_data(parser._scripts, extracted, photos)

    # Update photos in extracted
    extracted["photos"] = photos
    return extracted


def _mine_embedded_data(scripts: List[str], extracted: Dict[str, Any], photos: List[str]):
    """
    Search through script tag contents for embedded JSON data.
    Many platforms embed listing details in __NEXT_DATA__, deferred state, or other JSON blobs.
    """
    for script_content in scripts:
        # Look for JSON objects that might contain listing data
        # Pattern 1: __NEXT_DATA__ (Next.js pages like Airbnb)
        # Pattern 2: window.__data or similar
        json_candidates = []

        # Try to find JSON blobs in the script
        for pattern in [
            r'__NEXT_DATA__\s*=\s*(\{.+\})\s*;?\s*$',
            r'window\.__data\s*=\s*(\{.+\})\s*;?\s*$',
            r'data-deferred-state[^>]*>(\{.+\})',
        ]:
            for m in re.finditer(pattern, script_content, re.DOTALL):
                try:
                    json_candidates.append(json.loads(m.group(1)))
                except Exception:
                    pass

        # Also try the whole content if it looks like JSON
        stripped = script_content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                json_candidates.append(json.loads(stripped))
            except Exception:
                pass

        for obj in json_candidates:
            _extract_deep(obj, extracted, photos, depth=0, max_depth=8)


def _extract_deep(obj: Any, extracted: Dict[str, Any], photos: List[str],
                  depth: int, max_depth: int):
    """Recursively search a JSON object for listing-related data."""
    if depth > max_depth or obj is None:
        return

    if isinstance(obj, dict):
        # Look for photo/image URLs
        for key in ("url", "baseUrl", "pictureUrl", "picture_url",
                     "large", "xl_picture_url", "original", "scrim_url"):
            val = obj.get(key)
            if isinstance(val, str) and val.startswith("http") and \
               any(ext in val.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", "im/pictures")) and \
               val not in photos and len(photos) < 30:
                photos.append(val)

        # Look for amenities
        if not extracted.get("amenities"):
            for key in ("amenities", "listingAmenities", "amenity_ids"):
                val = obj.get(key)
                if isinstance(val, list) and val:
                    amenities = []
                    for item in val:
                        if isinstance(item, str):
                            amenities.append(item)
                        elif isinstance(item, dict):
                            name = item.get("name") or item.get("title") or item.get("tag") or ""
                            if name:
                                amenities.append(str(name))
                    if amenities:
                        extracted["amenities"] = amenities[:50]  # cap at 50

        # Look for specific data fields
        if not extracted.get("max_guests"):
            for key in ("personCapacity", "person_capacity", "guestCapacity", "maxGuests"):
                val = obj.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    extracted["max_guests"] = int(val)

        if not extracted.get("bedrooms"):
            for key in ("bedrooms", "bedroomCount", "bedroom_count"):
                val = obj.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    extracted["bedrooms"] = int(val)

        if not extracted.get("beds"):
            for key in ("beds", "bedCount", "bed_count"):
                val = obj.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    extracted["beds"] = int(val)

        if not extracted.get("bathrooms"):
            for key in ("bathrooms", "bathroomCount", "bathroom_count"):
                val = obj.get(key)
                if isinstance(val, (int, float)) and val > 0:
                    extracted["bathrooms"] = float(val)

        # Recurse into values
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _extract_deep(v, extracted, photos, depth + 1, max_depth)

    elif isinstance(obj, list):
        for item in obj[:20]:  # limit list traversal
            _extract_deep(item, extracted, photos, depth + 1, max_depth)


@router.post(
    "/{property_id}/fetch-listing",
    summary="Fetch and extract data from a listing URL (Phase 844)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def fetch_listing(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    listing_url = str(body.get("listing_url") or "").strip()
    if not listing_url or not listing_url.startswith("http"):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "A valid 'listing_url' starting with http(s):// is required."},
        )

    # All possible fields — we'll track what was imported vs not
    all_fields = ["name", "description", "city", "country", "address",
                  "latitude", "longitude", "photos", "amenities",
                  "capacity", "owner_contact"]

    blocked_platform = _detect_blocked_platform(listing_url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(listing_url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as e:
        warn = f"HTTP {e.response.status_code} from server."
        if blocked_platform:
            warn = f"{blocked_platform} blocks server-side access. Restricted."
        return JSONResponse(status_code=200, content={
            "imported": {},
            "could_not_import": all_fields,
            "warning": warn,
            "listing_url": listing_url,
        })
    except Exception as exc:
        return JSONResponse(status_code=200, content={
            "imported": {},
            "could_not_import": all_fields,
            "warning": f"Could not reach URL: {exc}",
            "listing_url": listing_url,
        })

    parser = _MetaParser()
    parser.feed(html)
    extracted = _extract_from_parsed(parser, listing_url)

    imported = {k: v for k, v in extracted.items() if v is not None and v != [] and v != ""}
    could_not_import = [f for f in all_fields if f not in imported]

    warning: Optional[str] = None
    if blocked_platform:
        warning = (
            f"{blocked_platform} limits server-side access. "
            f"Only Open Graph / JSON-LD data was captured — most fields may be missing."
        )
    elif not imported:
        warning = "No structured data (Open Graph / JSON-LD) found on this page."

    return JSONResponse(status_code=200, content={
        "imported": imported,
        "could_not_import": could_not_import,
        "warning": warning,
        "listing_url": listing_url,
    })


# ── Public preview endpoint (no auth, for onboarding wizard) ─────────

preview_router = APIRouter(prefix="/listing", tags=["listing"])


@preview_router.post(
    "/preview-extract",
    summary="Public listing URL preview extraction (no auth required)",
    responses={200: {}, 400: {}},
)
async def preview_extract(body: Dict[str, Any]) -> JSONResponse:
    """
    Same extraction logic as fetch_listing but:
    - No JWT auth required (public onboarding flow)
    - No property_id required (property doesn't exist yet)
    - Rate limited by caller (frontend proxy)
    """
    listing_url = str(body.get("listing_url") or "").strip()
    if not listing_url or not listing_url.startswith("http"):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "A valid 'listing_url' starting with http(s):// is required."},
        )

    all_fields = ["name", "description", "city", "country", "address",
                  "latitude", "longitude", "photos", "amenities",
                  "capacity", "owner_contact"]

    blocked_platform = _detect_blocked_platform(listing_url)

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await client.get(listing_url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPStatusError as e:
        warn = f"HTTP {e.response.status_code} from server."
        if blocked_platform:
            warn = f"{blocked_platform} blocks server-side access. Restricted."
        return JSONResponse(status_code=200, content={
            "imported": {},
            "could_not_import": all_fields,
            "warning": warn,
            "listing_url": listing_url,
        })
    except Exception as exc:
        return JSONResponse(status_code=200, content={
            "imported": {},
            "could_not_import": all_fields,
            "warning": f"Could not reach URL: {exc}",
            "listing_url": listing_url,
        })

    parser = _MetaParser()
    parser.feed(html)
    extracted = _extract_from_parsed(parser, listing_url)

    imported = {k: v for k, v in extracted.items() if v is not None and v != [] and v != ""}
    could_not_import = [f for f in all_fields if f not in imported]

    warning: Optional[str] = None
    if blocked_platform:
        warning = (
            f"{blocked_platform} limits server-side access. "
            f"Only Open Graph / JSON-LD data was captured — most fields may be missing."
        )
    elif not imported:
        warning = "No structured data (Open Graph / JSON-LD) found on this page."

    return JSONResponse(status_code=200, content={
        "imported": imported,
        "could_not_import": could_not_import,
        "warning": warning,
        "listing_url": listing_url,
    })
