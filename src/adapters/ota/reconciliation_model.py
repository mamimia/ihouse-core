"""
OTA Reconciliation Model — Phase 89

Discovery-only module. Defines the data model for representing and classifying
discrepancies between iHouse Core internal state and external OTA state.

Architecture constraints:
- This module is READ-ONLY. It never writes to booking_state or any Supabase table.
- Correction of a finding requires producing a new canonical event through the
  standard pipeline (OTA webhook → apply_envelope). The reconciliation layer
  only surfaces findings; it never bypasses apply_envelope.
- No live OTA API calls are made in this module. external_value fields are
  populated only when an external snapshot is provided by the caller.

Finding pipeline (future Phase 97 implementation):
    read booking_state (read-only)
    → compare with OTA snapshot (when available)
    → produce ReconciliationFinding list
    → wrap in ReconciliationReport
    → surface via admin API endpoint

This phase defines the model. Phase 97 will implement the detection logic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReconciliationFindingKind(str, Enum):
    """
    Classification of discrepancy types detected by the reconciliation layer.

    Each kind maps to a specific category of drift between iHouse Core state
    and what the OTA platform reports.
    """

    BOOKING_MISSING_INTERNALLY = "BOOKING_MISSING_INTERNALLY"
    """
    The OTA platform has a booking that does not exist in booking_state.
    Severity: CRITICAL — the system is missing data that may affect operations.
    """

    BOOKING_STATUS_MISMATCH = "BOOKING_STATUS_MISMATCH"
    """
    booking_state.status differs from what the OTA reports (e.g., active vs canceled).
    Severity: CRITICAL — could indicate a missed cancellation event.
    """

    DATE_MISMATCH = "DATE_MISMATCH"
    """
    check_in or check_out in booking_state differs from OTA-reported dates.
    Severity: CRITICAL — could cause operational errors (wrong prep, wrong cleaning).
    """

    FINANCIAL_FACTS_MISSING = "FINANCIAL_FACTS_MISSING"
    """
    booking_financial_facts has no row for a known booking.
    Severity: WARNING — financial reporting incomplete, but booking itself is intact.
    """

    FINANCIAL_AMOUNT_DRIFT = "FINANCIAL_AMOUNT_DRIFT"
    """
    Financial facts recorded in booking_financial_facts differ from OTA totals.
    Severity: WARNING — may indicate a mid-booking price adjustment not captured.
    """

    PROVIDER_DRIFT = "PROVIDER_DRIFT"
    """
    The provider field in booking_state differs from the envelope source.
    Severity: WARNING — usually indicates a data normalisation issue.
    """

    STALE_BOOKING = "STALE_BOOKING"
    """
    booking_state has not been updated in over 30 days with no terminal event
    (BOOKING_CANCELED). The booking remains in 'active' status but may be
    abandoned or incorrectly tracked.
    Severity: INFO — worth operator review, not a data integrity error.
    """


class ReconciliationSeverity(str, Enum):
    """
    Urgency classification for a reconciliation finding.

    CRITICAL  — Data integrity issue. Requires operator action before next check-in.
    WARNING   — Potential drift. Should be investigated within normal review cadence.
    INFO      — Informational observation. Low urgency, review at convenience.
    """

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


# ---------------------------------------------------------------------------
# Severity assignment — canonical mapping, locked at Phase 89
# ---------------------------------------------------------------------------

#: Canonical severity for each finding kind. Not editable after Phase 89.
FINDING_SEVERITY: dict[ReconciliationFindingKind, ReconciliationSeverity] = {
    ReconciliationFindingKind.BOOKING_MISSING_INTERNALLY: ReconciliationSeverity.CRITICAL,
    ReconciliationFindingKind.BOOKING_STATUS_MISMATCH: ReconciliationSeverity.CRITICAL,
    ReconciliationFindingKind.DATE_MISMATCH: ReconciliationSeverity.CRITICAL,
    ReconciliationFindingKind.FINANCIAL_FACTS_MISSING: ReconciliationSeverity.WARNING,
    ReconciliationFindingKind.FINANCIAL_AMOUNT_DRIFT: ReconciliationSeverity.WARNING,
    ReconciliationFindingKind.PROVIDER_DRIFT: ReconciliationSeverity.WARNING,
    ReconciliationFindingKind.STALE_BOOKING: ReconciliationSeverity.INFO,
}


# ---------------------------------------------------------------------------
# Correction hints — human-readable guidance per finding kind
# ---------------------------------------------------------------------------

#: Canonical correction hint for each finding kind.
CORRECTION_HINTS: dict[ReconciliationFindingKind, str] = {
    ReconciliationFindingKind.BOOKING_MISSING_INTERNALLY: (
        "Re-ingest the missing booking via POST /webhooks/{provider} with the original "
        "OTA payload. Do not write to booking_state directly."
    ),
    ReconciliationFindingKind.BOOKING_STATUS_MISMATCH: (
        "If OTA reports canceled, re-ingest a BOOKING_CANCELED event via "
        "POST /webhooks/{provider}. The apply_envelope branch will update booking_state."
    ),
    ReconciliationFindingKind.DATE_MISMATCH: (
        "Re-ingest a BOOKING_AMENDED event via POST /webhooks/{provider} with the "
        "correct check_in and check_out dates from the OTA payload."
    ),
    ReconciliationFindingKind.FINANCIAL_FACTS_MISSING: (
        "Re-ingest the original BOOKING_CREATED event to trigger financial_writer. "
        "Alternatively, verify financial_writer logs for the original ingest attempt."
    ),
    ReconciliationFindingKind.FINANCIAL_AMOUNT_DRIFT: (
        "Review booking_financial_facts.raw_financial_fields vs current OTA payload. "
        "If a price update occurred, re-ingest a BOOKING_AMENDED event with updated "
        "financial fields if the adapter supports them."
    ),
    ReconciliationFindingKind.PROVIDER_DRIFT: (
        "Inspect booking_state.provider and the original event_log entry. "
        "If normalisation rules changed, re-ingest the original event to correct."
    ),
    ReconciliationFindingKind.STALE_BOOKING: (
        "Verify with the OTA platform whether this booking is still active. "
        "If canceled or completed, ingest the appropriate terminal event."
    ),
}


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


def _make_finding_id(kind: ReconciliationFindingKind, booking_id: str) -> str:
    """
    Generate a deterministic finding_id from kind + booking_id.

    Uses the first 12 hex characters of SHA-256(kind:booking_id).
    Deterministic: same kind + booking_id always produces the same finding_id.
    Not a security hash — only used for deduplication and display.
    """
    raw = f"{kind.value}:{booking_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class ReconciliationFinding:
    """
    A single detected discrepancy between iHouse Core state and OTA state.

    Immutable after creation. The reconciliation layer creates findings;
    it never modifies them.

    Fields:
        finding_id      Deterministic 12-char hex string: sha256(kind:booking_id)[:12]
        kind            The category of discrepancy (ReconciliationFindingKind)
        severity        Urgency of this finding (ReconciliationSeverity)
        booking_id      The canonical booking_id affected: "{source}_{reservation_ref}"
        tenant_id       The tenant that owns this booking
        provider        OTA provider name (bookingcom, airbnb, traveloka, …)
        description     Human-readable description of what was found
        detected_at     ISO 8601 UTC timestamp when this finding was generated
        internal_value  What iHouse Core currently holds (None if not applicable)
        external_value  What the OTA platform reports (None if no live API snapshot)
        correction_hint Canonical human-readable guidance for resolving this finding
    """

    finding_id: str
    kind: ReconciliationFindingKind
    severity: ReconciliationSeverity
    booking_id: str
    tenant_id: str
    provider: str
    description: str
    detected_at: str
    internal_value: Optional[str]
    external_value: Optional[str]
    correction_hint: str

    @classmethod
    def build(
        cls,
        kind: ReconciliationFindingKind,
        booking_id: str,
        tenant_id: str,
        provider: str,
        description: str,
        detected_at: str,
        internal_value: Optional[str] = None,
        external_value: Optional[str] = None,
    ) -> "ReconciliationFinding":
        """
        Factory method. Automatically assigns:
        - finding_id from kind + booking_id
        - severity from FINDING_SEVERITY canonical map
        - correction_hint from CORRECTION_HINTS canonical map
        """
        return cls(
            finding_id=_make_finding_id(kind, booking_id),
            kind=kind,
            severity=FINDING_SEVERITY[kind],
            booking_id=booking_id,
            tenant_id=tenant_id,
            provider=provider,
            description=description,
            detected_at=detected_at,
            internal_value=internal_value,
            external_value=external_value,
            correction_hint=CORRECTION_HINTS[kind],
        )


@dataclass
class ReconciliationReport:
    """
    The full output of a reconciliation run for a single tenant.

    Contains all ReconciliationFinding instances detected, plus aggregate counts
    for operator dashboards and alerting.

    partial=True if any data source query failed during the run. Results
    are still returned — operators should treat a partial report as incomplete
    and rerun when the data source recovers.
    """

    tenant_id: str
    generated_at: str
    findings: List[ReconciliationFinding]
    total_checked: int
    critical_count: int
    warning_count: int
    info_count: int
    partial: bool = False

    @classmethod
    def build(
        cls,
        tenant_id: str,
        generated_at: str,
        findings: List[ReconciliationFinding],
        total_checked: int,
        partial: bool = False,
    ) -> "ReconciliationReport":
        """
        Factory method. Derives critical_count, warning_count, info_count
        from the provided findings list automatically.
        """
        critical = sum(
            1 for f in findings if f.severity == ReconciliationSeverity.CRITICAL
        )
        warning = sum(
            1 for f in findings if f.severity == ReconciliationSeverity.WARNING
        )
        info = sum(
            1 for f in findings if f.severity == ReconciliationSeverity.INFO
        )
        return cls(
            tenant_id=tenant_id,
            generated_at=generated_at,
            findings=findings,
            total_checked=total_checked,
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            partial=partial,
        )

    def has_critical(self) -> bool:
        """Return True if report contains at least one CRITICAL finding."""
        return self.critical_count > 0

    def has_warnings(self) -> bool:
        """Return True if report contains at least one WARNING finding."""
        return self.warning_count > 0

    def is_clean(self) -> bool:
        """Return True if no findings of any kind were detected."""
        return len(self.findings) == 0


@dataclass(frozen=True)
class ReconciliationSummary:
    """
    A lightweight summary of a ReconciliationReport for use in dashboards
    and API responses where the full finding list is not needed.

    Immutable after creation.
    """

    tenant_id: str
    generated_at: str
    has_critical: bool
    has_warnings: bool
    finding_count: int
    critical_count: int
    warning_count: int
    info_count: int
    top_kind: Optional[str]
    """The value of the most frequent ReconciliationFindingKind, or None if no findings."""
    partial: bool

    @classmethod
    def from_report(cls, report: ReconciliationReport) -> "ReconciliationSummary":
        """
        Derive a ReconciliationSummary from a full ReconciliationReport.
        Computes top_kind as the most frequently occurring finding kind.
        If tied, the CRITICAL-severity kind wins; then alphabetical.
        """
        top_kind: Optional[str] = None
        if report.findings:
            from collections import Counter

            counts = Counter(f.kind.value for f in report.findings)
            # Sort by: frequency desc, then CRITICAL first, then alphabetical
            def _sort_key(item: tuple[str, int]) -> tuple[int, int, str]:
                kind_val, count = item
                try:
                    kind = ReconciliationFindingKind(kind_val)
                    sev_order = {
                        ReconciliationSeverity.CRITICAL: 0,
                        ReconciliationSeverity.WARNING: 1,
                        ReconciliationSeverity.INFO: 2,
                    }[FINDING_SEVERITY[kind]]
                except (ValueError, KeyError):
                    sev_order = 99
                return (-count, sev_order, kind_val)

            top_kind = sorted(counts.items(), key=_sort_key)[0][0]

        return cls(
            tenant_id=report.tenant_id,
            generated_at=report.generated_at,
            has_critical=report.has_critical(),
            has_warnings=report.has_warnings(),
            finding_count=len(report.findings),
            critical_count=report.critical_count,
            warning_count=report.warning_count,
            info_count=report.info_count,
            top_kind=top_kind,
            partial=report.partial,
        )
