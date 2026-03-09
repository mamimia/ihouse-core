# iHouse Core — Handoff to New Chat
# Phase 88 → Phase 89

**Written by:** Claude (Antigravity)
**Date:** 2026-03-09
**Context at handoff:** ~78–80%
**Reason for handoff:** Context window approaching limit — early handoff per BOOT.md protocol.

---

## 1. Current State — One Line

**Phase 88 (Traveloka Adapter) is closed. 1029 tests pass. Next phase is Phase 89 — TBD.**

---

## 2. What You Must Read First (in order)

Per BOOT.md protocol — read in this exact order:

1. `docs/core/BOOT.md` — authority rules, what you can edit, what is immutable
2. `docs/core/vision.md` — Layer A, immutable
3. `docs/core/system-identity.md` — Layer A, immutable
4. `docs/core/canonical-event-architecture.md` — Layer A, immutable
5. `docs/core/governance.md` — Layer B
6. `docs/core/current-snapshot.md` — **START HERE for state** — Layer C
7. `docs/core/work-context.md` — Layer C
8. `docs/core/live-system.md` — Layer C
9. `docs/core/phase-timeline.md` (last 2 sections only — Phase 87 + 88)
10. `docs/core/construction-log.md` (last 2 sections only — Phase 87 + 88)
11. `docs/core/roadmap.md` (only if planning next phase)

---

## 3. Closed Phases — This Chat Session

| Phase | Title | Tests Added | Total After |
|-------|-------|-------------|-------------|
| 86 | Conflict Detection Layer | +58 | 920 |
| 87 | Tenant Isolation Hardening | +54 | 974 |
| 88 | Traveloka Adapter (SE Asia Tier 1.5) | +55 | 1029 |

---

## 4. Test Suite Status

```
1029 passed, 2 skipped
```
- 2 pre-existing SQLite skips — unrelated to iHouse logic. NOT blocking.
- Run: `PYTHONPATH=src .venv/bin/pytest tests/ --ignore=tests/invariants -p no:warnings`

---

## 5. OTA Adapter Registry — Phase 88 Final State

All 8 providers fully registered in `src/adapters/ota/registry.py`:

| Provider | File | Prefix Strip | Currency Field |
|----------|------|-------------|----------------|
| bookingcom | bookingcom.py | BK- | currency |
| expedia | expedia.py | — | currency |
| airbnb | airbnb.py | — | currency |
| agoda | agoda.py | AG- / AGD- | currency |
| tripcom | tripcom.py | TC- | currency |
| vrbo | vrbo.py | — | currency |
| gvr | gvr.py | — | currency |
| **traveloka** | **traveloka.py** | **TV-** | **currency_code** ← NOTE |

> ⚠️ Traveloka uses `currency_code` not `currency`. This is handled in `schema_normalizer._currency()` and `_extract_traveloka()`.

---

## 6. Key Modules Added (Phases 86–88)

### Phase 86 — Conflict Detection Layer
- **`src/adapters/ota/conflict_detector.py`** — read-only scan of `booking_state`
  - `detect_conflicts(db, tenant_id) → ConflictReport`
  - `ConflictKind`: DATE_OVERLAP, MISSING_PROPERTY, MISSING_DATES, DUPLICATE_REF
  - `ConflictSeverity`: ERROR, WARNING
- **Tests**: `tests/test_conflict_detector_contract.py` — 58 tests

### Phase 87 — Tenant Isolation Hardening
- **`src/adapters/ota/tenant_isolation_enforcer.py`** — system-level policy layer
  - `TABLE_REGISTRY`: 5 tables classified as TENANT_SCOPED or GLOBAL
  - `check_cross_tenant_leak(tenant_a, tenant_b, rows) → CrossTenantLeakResult`
  - `audit_system_isolation() → SystemIsolationReport` (all_compliant=True ✅)
  - Complements Phase 81 `tenant_isolation_checker.py` (query-level)
- **Tests**: `tests/test_tenant_isolation_enforcer_contract.py` — 54 tests

### Phase 88 — Traveloka Adapter
- **`src/adapters/ota/traveloka.py`** — `TravelokaAdapter`
  - `booking_code` → reservation_id (TV- stripped)
  - `property_code` → property_id
  - `check_in_date` / `check_out_date` (NOT check_in / check_out)
  - `currency_code` (NOT currency) → handled by schema_normalizer special case
  - `booking_total` / `traveloka_fee` / `net_payout`
  - ESTIMATED net derivation: `net = booking_total - traveloka_fee` when `net_payout` absent
  - Amendment block under `modification.{check_in_date, check_out_date, num_guests, modification_reason}`
- **6 files modified**: schema_normalizer, financial_extractor, amendment_extractor, booking_identity, registry + traveloka.py (NEW)
- **Tests**: `tests/test_traveloka_adapter_contract.py` — 53 tests

---

## 7. Key Invariants — Never Break These

These are locked. Do not touch.

| Invariant | Source |
|-----------|--------|
| `apply_envelope` is the only write authority | Phase 35 |
| `event_log` is append-only | Phase 21 |
| `booking_id = "{source}_{reservation_ref}"` | Phase 36 |
| `reservation_ref` normalized by `normalize_reservation_ref()` before use | Phase 68 |
| `tenant_id` from JWT `sub` claim ONLY — never from payload body | Phase 61 |
| `booking_state` must NEVER contain financial data | Phase 62 |
| All OTA adapters: normalize → classify → to_canonical_envelope | Phase 35 |

---

## 8. Architecture — Critical Files

```
src/
  main.py                          FastAPI entrypoint (OpenAPI, middleware)
  api/
    webhooks.py                    POST /webhooks/{provider}
    auth.py                        JWT verification
    rate_limiter.py                Per-tenant rate limiting
    health.py                      GET /health
    financial_router.py            GET /financial/{booking_id}
    admin_router.py                GET /admin/* (metrics, DLQ, timeline)
    bookings_router.py             GET /bookings/{booking_id}
  adapters/ota/
    registry.py                    8 providers registered
    base.py                        OTAAdapter ABC
    booking_identity.py            normalize_reservation_ref + _PROVIDER_RULES
    schema_normalizer.py           8 canonical field helpers (all 8 providers)
    financial_extractor.py         _EXTRACTORS dict + _extract_* per provider
    amendment_extractor.py         normalize_amendment dispatcher
    date_normalizer.py             normalize_date (ISO 8601)
    idempotency.py                 generate_idempotency_key
    tenant_isolation_checker.py    Phase 81: query-level audit
    tenant_isolation_enforcer.py   Phase 87: system-level policy audit
    conflict_detector.py           Phase 86: read-only conflict scan
    structured_logger.py           Phase 80: StructuredLogger, JSON emit

scripts/
  supabase_schema_13c.sql          Canonical DB schema

docs/core/
  BOOT.md                          ← READ THIS FIRST
  current-snapshot.md              ← State of record
  work-context.md                  ← Key invariants + env vars
  live-system.md                   ← Architecture snapshot
  phase-timeline.md                ← Append-only history
  construction-log.md              ← Append-only build log
  roadmap.md                       ← Forward direction
```

---

## 9. Document Authority — What You Can Edit

| Layer | Document | Rule |
|-------|----------|------|
| A — Immutable | vision.md, system-identity.md, canonical-event-architecture.md | NEVER edit |
| B — Governance | governance.md | Only when explicitly requested |
| C — Current State | current-snapshot.md, work-context.md, live-system.md, roadmap.md | Editable, tightly scoped |
| D — History | phase-timeline.md, construction-log.md | **APPEND ONLY** — never rewrite |

---

## 10. Next Phase — Phase 89

**Next phase is TBD** — not yet defined.

Candidates from `docs/core/roadmap.md` + `docs/core/improvements/future-improvements.md`:

1. **MakeMyTrip Adapter** — Completes the SE Asia + South Asia adapter wave
2. **Despegar Adapter** — Latin America Tier 1
3. **Financial Reconciliation Layer** — compare `booking_financial_facts` vs `booking_state`
4. **Rate Card / Pricing Layer** — owner-facing price management surfaces
5. **Worker Communication Planning** — locked forward note in future-improvements.md

> Ask the user which direction to take before starting Phase 89.

---

## 11. Protocol Reminders

Per BOOT.md — the next chat must follow these without exception:

- **Push to GitHub** after every meaningful change
- **Every phase must have a spec file**: `docs/archive/phases/phase-N-spec.md`
- **ZIP at phase closure**: `releases/phase-zips/iHouse-Core-Docs-Phase-N.zip` (entire `docs/core/` tree)
- **Phase timeline + construction-log**: APPEND ONLY — never rewrite
- **If a tool fails twice**: stop, list alternatives, pick the next best one
- **Read full file before editing**: never overwrite blindly

---

## 12. Quick Start for New Chat

```
1. Read BOOT.md → current-snapshot.md → work-context.md
2. State: "Phase 88 closed. Last closed: Traveloka Adapter. 1029 tests. Next: Phase 89 TBD."
3. Ask the user: "Which direction for Phase 89?"
4. Run baseline: PYTHONPATH=src .venv/bin/pytest tests/ --ignore=tests/invariants -p no:warnings -q
5. Confirm: 1029 passed, 2 skipped
6. Begin Phase 89
```

---

*Handoff written per BOOT.md § "Context limit — handoff protocol"*
*Context at handoff: ~78–80%*
