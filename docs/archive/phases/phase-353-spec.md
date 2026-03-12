# Phase 353 — Doc Auto-Generation from Code

**Closed:** 2026-03-12
**Category:** 📄 Documentation / Tooling
**Test file:** `tests/test_doc_autogen_p353.py`
**Script:** `scripts/extract_metrics.py`

## Summary

Automated metrics extraction script + validation test suite that proves
documentation matches code reality. The script auto-reads 6 live metrics;
the tests validate invariants about test count (≥200 files), route count
(≥100), phase progression (≥350), adapter registries, and doc freshness.

## Deliverables

### scripts/extract_metrics.py (NEW)
Auto-extracts 6 live metrics from the codebase:
- `test_file_count`, `src_file_count`, `route_count`
- `outbound_adapter_count`, `phase_spec_count`, `current_phase`

Outputs JSON. Use with `--output docs/core/metrics-report.json`.

## Tests Added: 22

### Group A — Metrics Extractor (6 tests)
- ≥200 test files, ≥200 src files, ≥100 phase specs, phase≥350,
  script exists, all metrics positive

### Group B — Route Inventory Consistency (4 tests)
- ≥100 routes, all have paths, ≤5 duplicates, critical infra routes exist

### Group C — Adapter Registry Consistency (4 tests)
- OTA registry has ≥10 entries, outbound has 7, all names lowercase, interface impl

### Group D — Doc ↔ Code Cross-Validation (4 tests)
- Snapshot refs Phase 350+, test count ≥5000, timeline has 352+, log non-empty

### Group E — Phase Spec Completeness (4 tests)
- All markdown, all >100 bytes, phases 349-352 have specs, specs have Closed: dates

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 7,047 | 7,069 |
| Test files | 236 | 237 |
| New tests | — | 22 |
| New scripts | — | 1 |
