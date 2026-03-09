# Phase 89 — OTA Reconciliation Discovery

**Status:** Closed
**Prerequisite:** Phase 88 (Traveloka Adapter)
**Date Closed:** 2026-03-09

## Goal

Discovery-only phase. Define the reconciliation model for iHouse Core: what discrepancies between
internal state and external OTA state can be detected without a live OTA API connection,
how to classify and flag each category of drift, and what the correction-support layer
would look like without ever bypassing `apply_envelope`.

This phase produces:
1. `src/adapters/ota/reconciliation_model.py` — frozen dataclasses + enums for reconciliation findings
2. `tests/test_reconciliation_model_contract.py` — 32 contract tests covering all finding types

No live OTA API calls. No writes to booking_state. No bypassing of apply_envelope.
Reconciliation is detection + correction-support only.

## Invariant (if applicable)

Pre-existing invariants preserved:
- `apply_envelope` remains the only write authority
- `booking_state` is never mutated by the reconciliation layer
- Reconciliation findings are read-only outputs — they describe drift, never correct it directly

New invariant locked by this phase:
- The reconciliation layer is **read-only** — it may read `booking_state` and `booking_financial_facts`,
  but must never write to either. Correction requires a new canonical event through the normal pipeline.

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/reconciliation_model.py` | NEW — ReconciliationFindingKind enum, ReconciliationSeverity enum, ReconciliationFinding frozen dataclass, ReconciliationReport dataclass, ReconciliationSummary dataclass |
| `tests/test_reconciliation_model_contract.py` | NEW — 32 contract tests (Groups A–F) |

### ReconciliationFindingKind (7 categories)

| Kind | Description |
|------|-------------|
| `BOOKING_MISSING_INTERNALLY` | OTA has a booking we don't have in booking_state |
| `BOOKING_STATUS_MISMATCH` | booking_state status differs from OTA-reported status |
| `DATE_MISMATCH` | check_in/check_out in booking_state differ from OTA snapshot |
| `FINANCIAL_FACTS_MISSING` | booking_financial_facts row absent for a known booking |
| `FINANCIAL_AMOUNT_DRIFT` | financial facts recorded differ from OTA-reported totals |
| `PROVIDER_DRIFT` | provider field in booking_state differs from envelope source |
| `STALE_BOOKING` | booking_state not updated in >30 days with no terminal event |

### ReconciliationSeverity

| Severity | Meaning |
|----------|---------|
| `CRITICAL` | Data integrity issue — requires urgent operator review |
| `WARNING` | Potential drift — worth investigation, not blocking |
| `INFO` | Informational observation — low urgency |

### ReconciliationReport structure

```python
@dataclass(frozen=True)
class ReconciliationFinding:
    finding_id: str          # deterministic: sha256(kind+booking_id)[:12]
    kind: ReconciliationFindingKind
    severity: ReconciliationSeverity
    booking_id: str
    tenant_id: str
    provider: str
    description: str
    detected_at: str         # ISO 8601 UTC
    internal_value: Optional[str]   # what iHouse Core has
    external_value: Optional[str]   # what OTA reports (None if no live API)
    correction_hint: str     # human-readable suggested next step

@dataclass
class ReconciliationReport:
    tenant_id: str
    generated_at: str
    findings: List[ReconciliationFinding]
    total_checked: int
    critical_count: int
    warning_count: int
    info_count: int
    partial: bool            # True if any data source failed

@dataclass(frozen=True)
class ReconciliationSummary:
    has_critical: bool
    has_warnings: bool
    finding_count: int
    top_kind: Optional[str]  # most frequent finding kind
```

## Result

**1061 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations. No booking_state writes.
No live OTA API calls. Pure Python model + contract tests.
