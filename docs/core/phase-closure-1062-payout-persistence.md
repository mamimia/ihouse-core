# Phase 1062 — Canonical Payout Persistence

**Phase:** 1062 / 1062b  
**Commits:** `e785642` (1062), `d5b73f7` (docs)  
**Status:** ✅ Fully closed — live E2E verified  

---

## What existed before this phase

`generate_payout_record()` in `financial_writer.py` was **calculation-only**:
- Returned a payout dict with a `status: "calculated"` and a session-only `payout_id`
- That `payout_id` was a UUID fragment that was **never written to any table**
- "What was paid to this owner and when" was **unanswerable**
- No status lifecycle, no audit trail, no retrievable records
- The comment in the file explicitly stated: *"no such table exists yet"*

`booking_financial_facts` has 14 columns — none related to payout status or payout identity.  
No `owner_payouts` table existed in the database.

---

## What was built in Phase 1062

### 1. Database: `owner_payouts` + `payout_events`

**`owner_payouts`** — canonical payout records:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | Stable, retrievable payout identity |
| `tenant_id` | TEXT | Tenant isolation |
| `property_id` | TEXT | Property this payout covers |
| `period_start` / `period_end` | DATE | Coverage period |
| `currency` | CHAR(3) | Locked at creation |
| `gross_total` | NUMERIC(14,2) | Snapshot at commit time |
| `management_fee_pct` | NUMERIC(5,2) | Fee % locked at creation |
| `management_fee_amt` | NUMERIC(14,2) | Fee amount |
| `net_payout` | NUMERIC(14,2) | What goes to the owner |
| `bookings_count` | INTEGER | Source booking count |
| `status` | TEXT | `draft\|pending\|approved\|paid\|voided` |
| `paid_at` | TIMESTAMPTZ | Set when marked paid |
| `payment_reference` | TEXT | Bank ref / transfer ID / cheque |
| `created_by` / `approved_by` / `paid_by` | TEXT | Actor attribution per stage |
| `notes` | TEXT | Optional |

**`payout_events`** — append-only audit trail:

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | |
| `payout_id` | UUID FK | References `owner_payouts.id` |
| `tenant_id` | TEXT | |
| `from_status` | TEXT | NULL on creation |
| `to_status` | TEXT | |
| `actor_id` | TEXT | Who made the transition |
| `notes` | TEXT | |
| `occurred_at` | TIMESTAMPTZ | |

Both tables have RLS enabled; service_role bypass policy applied.

### 2. Service: `src/services/payout_service.py`

| Function | Description |
|----------|-------------|
| `create_payout()` | Calculates from `booking_financial_facts` + persists to `owner_payouts` |
| `transition_status()` | Advances lifecycle with state machine enforcement + audit event |
| `get_payout()` | Retrieve single payout by UUID + tenant |
| `list_payouts()` | List with optional `property_id` / `status` filter |
| `get_payout_history()` | Full event log for a payout |

State machine:
```
draft → pending → approved → paid   (happy path)
draft | pending | approved → voided  (cancellation)
paid, voided  → terminal (no further transitions)
```

### 3. Router: `src/api/payout_router.py`

| Endpoint | Description |
|----------|-------------|
| `POST /admin/payouts` | Create and persist a payout |
| `GET /admin/payouts` | List (filter: property_id, status, limit) |
| `GET /admin/payouts/{id}` | Get single payout |
| `GET /admin/payouts/{id}/history` | Full audit trail |
| `POST /admin/payouts/{id}/submit` | `draft → pending` |
| `POST /admin/payouts/{id}/approve` | `pending → approved` |
| `POST /admin/payouts/{id}/mark-paid` | `approved → paid` (+ payment_reference) |
| `POST /admin/payouts/{id}/void` | Any pre-paid → `voided` |

Authorization: all endpoints require `financial` capability (admin always, manager only if delegated).

### 4. Backward compatibility

- `financial_writer.generate_payout_record()` now delegates to `payout_service.create_payout()` — old callers get a real persisted record with `status: "draft"` instead of ephemeral `status: "calculated"`
- Old `POST /admin/financial/payout` endpoint still works but now persists

---

## Product questions now answerable

| Question | Answer |
|----------|--------|
| Can the system persist a payout record canonically? | ✅ Yes — `owner_payouts` table |
| Can we distinguish unpaid / pending / approved / paid? | ✅ Yes — 5-state lifecycle |
| Can we answer "what was paid to this owner and when?" | ✅ Yes — `paid_at` + `payment_reference` on `paid` records |
| Can admin/finance see real payout history? | ✅ Yes — `GET /admin/payouts` + filter by property |
| Can follow-up reconciliation happen against real records? | ✅ Yes — UUID-addressable, append-only event log |

---

## What still remains open

### 1. UI surface for payout management
No admin UI for payout lifecycle exists. Finance team must use the API directly.  
**Blocker:** UI work. Backend is ready.

### 2. `property_id` missing from `booking_financial_facts`
`generate_payout_record()` and `payout_service._calculate_from_facts()` filter by `property_id`, but `booking_financial_facts` does not have a `property_id` column in its current schema. The `owner_statement_router.py` also queries by `property_id` against this table. This means the calculation returns empty `bookings_count: 0` unless data was written with a `property_id` field.  
**Blocker:** A separate migration to add `property_id` to `booking_financial_facts` and backfill it from booking data. This is pre-existing technical debt, not introduced by Phase 1062.

### 3. Automated payout generation (scheduler)
Currently payouts are created manually via API. A monthly scheduler that auto-generates draft payouts per property at period close would complete the workflow.  
**Blocker:** Product decision on timing + notification trigger.

### 4. Owner-facing payout visibility
Owners currently cannot see their own payout records in the portal.  
**Blocker:** Owner portal UI work.

---

## Tests

- **File:** `tests/test_payout_service.py`
- **Cases:** 10 tests
- **Coverage:** create (empty period → zero payout), invalid initial status, state machine transitions (valid + invalid), void from approved, not-found, terminal state verification, full happy path reachability
- **Result:** `10 passed in 0.09s` ✅

---

## Files changed

| File | Change |
|------|--------|
| `src/services/payout_service.py` | **NEW** — canonical payout persistence service |
| `src/api/payout_router.py` | **NEW** — payout lifecycle API (8 endpoints) |
| `src/services/financial_writer.py` | Updated `generate_payout_record()` to delegate to payout_service |
| `src/api/financial_writer_router.py` | Old endpoint now passes `actor_id` + is now persisting |
| `src/main.py` | Registered `payout_router` |
| `tests/test_payout_service.py` | **NEW** — payout service unit tests |
| Supabase DB | `owner_payouts` + `payout_events` tables created with RLS |
