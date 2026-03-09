# Handoff to New Chat — Phase 81

## Context Status

**Chat context approaching capacity. Stopping per BOOT.md protocol.**

---

## Last Closed Phase

**Phase 81 — Tenant Isolation Audit** | test run: `687 passed, 2 skipped`

- Audited `admin_router.py`, `bookings_router.py`, `financial_router.py`
- All `booking_state` and `booking_financial_facts` queries correctly scoped by `tenant_id`
- `ota_dead_letter` global by design — no `tenant_id` column, documented
- Fixed `financial_router.py`: 404/500 now use `make_error_response` (Phase 75 standard)
- Created `tenant_isolation_checker.py` — `TenantIsolationReport`, `audit_tenant_isolation()`, `check_query_has_tenant_filter()`
- 24 contract tests (Groups A–D in `tests/test_tenant_isolation_checker_contract.py`)

---

## Current State

| Field | Value |
|---|---|
| Last closed phase | Phase 81 — Tenant Isolation Audit |
| Test count | 687 passed, 2 skipped |
| Active branch | `checkpoint/supabase-single-write-20260305-1747` |

---

## Next Objective

**Phase 82 — Admin Query API** (per `docs/core/roadmap.md`)

> `src/api/admin_router.py` endpoints:
> - `GET /admin/metrics`
> - `GET /admin/dlq`
> - `GET /admin/health/providers`
> - `GET /admin/bookings/{id}/timeline`
> First queryable surface for operators.

---

## Key Files to Read at Boot

Per BOOT.md protocol, read in this order:
1. `docs/core/vision.md`, `docs/core/system-identity.md`, `docs/core/canonical-event-architecture.md`
2. `docs/core/governance.md`
3. `docs/core/current-snapshot.md`
4. `docs/core/work-context.md`
5. `docs/core/phase-timeline.md` (last section only — Phase 81)
6. `docs/core/construction-log.md` (last section only)

---

## Phase 79–81 Summary (Done in This Chat)

| Phase | Title | Tests Added |
|---|---|---|
| 79 | Idempotency Monitoring | 35 |
| 80 | Structured Logging Layer | 30 |
| 81 | Tenant Isolation Audit | 24 |

Total: **89 new tests** added in this chat session.

---

## Locked Invariants (Never Change)

- `apply_envelope` is the ONLY write authority to `booking_state` and `event_log`
- `booking_state` never contains financial data
- All canonical keys in `schema_normalizer.py` are additive — raw fields never removed
- `financial_extractor.py` owns Decimal precision — `schema_normalizer.py` does NOT convert types
- All canonical price/date fields in `schema_normalizer.py` are raw `str`

---

## Files Added in This Chat

```
src/adapters/ota/tenant_isolation_checker.py       (Phase 81 — new)
tests/test_tenant_isolation_checker_contract.py    (Phase 81 — new)
docs/archive/phases/phase-81-spec.md
releases/handoffs/handoff_to_new_chat Phase-81.md
```

## Files Modified in This Chat

```
src/api/financial_router.py                        (Phase 81 — 404/500 standardised)
tests/test_financial_router_contract.py            (Phase 81 — T2/T7 updated)
docs/core/current-snapshot.md
docs/core/work-context.md
docs/core/phase-timeline.md
docs/core/construction-log.md
```

---

## Notes for Next Agent

- Pyre2 lint errors (import of `pytest`, `adapters.*`, `+=` on locals) are **false positives** — ignored by maintainers since Phase 77
- 2 pre-existing failing tests in `tests/invariants/` require `IHOUSE_ALLOW_SQLITE=1` — not regressions
- Run tests with: `PYTHONPATH=src .venv/bin/pytest tests/ --ignore=tests/invariants -p no:warnings -q`
