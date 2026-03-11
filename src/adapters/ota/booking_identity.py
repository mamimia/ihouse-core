from __future__ import annotations

"""
booking_identity.py — Phase 68: booking_id Stability

Provides deterministic normalization of reservation_ref values
before they are used to construct booking_id.

Rule: booking_id = "{source}_{reservation_ref}"  (locked Phase 36)
This module ensures reservation_ref is stable across provider
schema variations (capitalisation, whitespace, prefix changes).

Constraints:
- No booking_state reads
- No database I/O
- Deterministic: same input always produces same output
- Unknown providers pass through with base normalization only
"""


# Per-provider normalization rules.
# Each entry is a list of callables applied left-to-right.
# The base rule (strip + lowercase) is always applied first.

def _strip_bookingcom_prefix(ref: str) -> str:
    """Booking.com sometimes prefixes refs with 'BK-' or 'bk-'."""
    lower = ref.lower()
    if lower.startswith("bk-"):
        return ref[3:]
    return ref


def _strip_agoda_prefix(ref: str) -> str:
    """Agoda occasionally prefixes with 'AG-' or 'AGD-'."""
    lower = ref.lower()
    if lower.startswith("agd-"):
        return ref[4:]
    if lower.startswith("ag-"):
        return ref[3:]
    return ref


def _strip_tripcom_prefix(ref: str) -> str:
    """Trip.com uses numeric order_id but occasionally adds 'TC-' prefix.
    Ctrip (Phase 238) uses 'CTRIP-' prefix for Chinese market bookings."""
    lower = ref.lower()
    if lower.startswith("ctrip-"):
        return ref[6:]
    if lower.startswith("tc-"):
        return ref[3:]
    return ref


def _strip_traveloka_prefix(ref: str) -> str:
    """Traveloka booking codes may be prefixed with 'TV-'. Strip it for a stable ref."""
    lower = ref.lower()
    if lower.startswith("tv-"):
        return ref[3:]
    return ref


def _strip_makemytrip_prefix(ref: str) -> str:
    """MakeMyTrip booking IDs may be prefixed with 'MMT-'. Strip it for a stable ref."""
    lower = ref.lower()
    if lower.startswith("mmt-"):
        return ref[4:]
    return ref


def _strip_klook_prefix(ref: str) -> str:
    """Klook booking refs may be prefixed with 'KL-'. Strip it for a stable ref."""
    lower = ref.lower()
    if lower.startswith("kl-"):
        return ref[3:]
    return ref


def _strip_despegar_prefix(ref: str) -> str:
    """Strip DSP- prefix from Despegar reservation codes.

    Examples:
      'DSP-AR-9988001' -> 'ar-9988001'
      'dsp-mx-7654321' -> 'mx-7654321'
    """
    lowered = ref.lower()
    if lowered.startswith("dsp-"):
        return lowered[4:]
    return lowered


def _strip_rakuten_prefix(ref: str) -> str:
    """Strip RAK- prefix from Rakuten Travel booking references.

    Phase 187 — Rakuten Travel (Japan) uses RAK- prefix.

    Examples:
      'RAK-JP-20250815-001' -> 'jp-20250815-001'
      'rak-sg-99001234'     -> 'sg-99001234'
    """
    lowered = ref.lower()
    if lowered.startswith("rak-"):
        return lowered[4:]
    return lowered


def _strip_hotelbeds_prefix(ref: str) -> str:
    """Hotelbeds voucher refs may be prefixed with 'HB-'. Strip it for a stable ref."""
    lower = ref.lower()
    if lower.startswith("hb-"):
        return ref[3:]
    return ref


def _strip_hostelworld_prefix(ref: str) -> str:
    """Strip HW- prefix from Hostelworld booking reservation IDs.

    Phase 195 — Hostelworld uses HW- prefix.

    Examples:
      'HW-2025-0081234' -> '2025-0081234'
      'hw-eu-99001234'  -> 'eu-99001234'
    """
    lowered = ref.lower()
    if lowered.startswith("hw-"):
        return lowered[3:]
    return lowered

# Registry: provider → list of extra normalization steps after base
_PROVIDER_RULES: dict[str, list] = {
    "bookingcom": [_strip_bookingcom_prefix],
    "expedia":    [],   # no extra rules — numeric IDs, stable
    "airbnb":     [],   # no extra rules — numeric IDs, stable
    "agoda":      [_strip_agoda_prefix],
    "tripcom":    [_strip_tripcom_prefix],
    "vrbo":       [],   # numeric IDs, stable — no prefix stripping needed
    "gvr":        [],   # GVR booking IDs are stable alphanumeric — no prefix stripping
    "traveloka":  [_strip_traveloka_prefix],  # Traveloka booking codes prefixed with TV-
    "makemytrip": [_strip_makemytrip_prefix],  # MMT booking IDs prefixed with MMT-
    "klook":      [_strip_klook_prefix],       # Klook booking refs prefixed with KL-
    "despegar":   [_strip_despegar_prefix],    # Despegar reservation codes prefixed with DSP-
    "hotelbeds":  [_strip_hotelbeds_prefix],    # Hotelbeds voucher refs prefixed with HB-
    "rakuten":      [_strip_rakuten_prefix],      # Phase 187: Rakuten Travel booking refs prefixed with RAK-
    "hostelworld":  [_strip_hostelworld_prefix],  # Phase 195: Hostelworld booking refs prefixed with HW-
}


def normalize_reservation_ref(provider: str, raw_ref: str) -> str:
    """
    Return a stable, canonical form of a reservation reference.

    Steps applied in order:
      1. Strip leading/trailing whitespace
      2. Lowercase
      3. Provider-specific prefix stripping (if any)

    This function is deterministic and pure — same input always
    returns the same output. It never reads external state.

    Args:
        provider:  OTA provider slug (e.g. "bookingcom", "airbnb")
        raw_ref:   Raw reservation reference string from provider payload

    Returns:
        Normalized reservation ref string, safe to use in booking_id.

    Example:
        normalize_reservation_ref("bookingcom", "  BK-RES12345  ")
        → "res12345"
    """
    if not raw_ref:
        return raw_ref

    # Step 1 + 2: base normalization
    ref = raw_ref.strip().lower()

    # Step 3: provider-specific rules
    extra_rules = _PROVIDER_RULES.get(provider, [])
    for rule_fn in extra_rules:
        ref = rule_fn(ref)

    return ref


def build_booking_id(source: str, reservation_ref: str) -> str:
    """
    Build the canonical booking_id from source and reservation_ref.

    Applies normalize_reservation_ref before constructing the ID.
    Locked invariant (Phase 36): booking_id = "{source}_{reservation_ref}"

    Args:
        source:          OTA provider slug  (e.g. "bookingcom")
        reservation_ref: Raw reservation reference from provider payload

    Returns:
        Canonical booking_id string (e.g. "bookingcom_res12345")
    """
    normalized_ref = normalize_reservation_ref(source, reservation_ref)
    return f"{source}_{normalized_ref}"
