# Phases 952–955 — Property Charge Rules & Owner Deposit Suggestion

## Overview

Two separable but related systems:

1. **Property Charge Rules** (Phases 952–953) — admin-controlled per-property configuration
   for deposit and electricity charges. The live operational source of truth used by
   check-in workers during deposit collection.

2. **Owner Deposit Suggestion** (Phases 954–955) — owner-initiated suggestion flow for
   deposit amounts, with admin review/approve/reject. Owners cannot directly set the
   active deposit rule; they submit suggestions that admin evaluates and approves.

---

## Phase Assignment

| Phase | Scope |
|---|---|
| **952** | `property_charge_rules` table + admin CRUD endpoints |
| **953** | Worker pre-fill endpoint — read charge config during check-in wizard |
| **954** | `deposit_suggestions` table + owner submit + owner read endpoints |
| **955** | Admin suggestion review endpoints (approve / reject) + `main.py` registration |

---

## 1. Data Model

### Table: `property_charge_rules`

Admin-controlled. One row per property per tenant. Upsert model — no history
table at Phase 952. Updated_by is always the real user_id from JWT.

```sql
CREATE TABLE property_charge_rules (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            TEXT        NOT NULL,
    property_id          TEXT        NOT NULL,

    -- Deposit config
    deposit_enabled      BOOLEAN     NOT NULL DEFAULT false,
    deposit_amount       NUMERIC(10,2),       -- NULL = unset; ignored when deposit_enabled=false
    deposit_currency     TEXT        NOT NULL DEFAULT 'THB',
    deposit_notes        TEXT,                -- admin annotation (e.g. "seasonal rate")

    -- Electricity config
    electricity_enabled  BOOLEAN     NOT NULL DEFAULT false,
    electricity_rate_kwh NUMERIC(8,4),        -- cost per kWh; NULL when electricity_enabled=false
    electricity_currency TEXT        NOT NULL DEFAULT 'THB',
    electricity_notes    TEXT,

    -- Audit
    updated_by           TEXT,                -- real user_id of last admin who wrote this
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, property_id)
);
```

Design decisions:
- `deposit_amount = NULL` with `deposit_enabled = true` is valid ("collect deposit, TBD amount").
- `updated_by` is always extracted from JWT — no hardcoded placeholder (consistent with Issues 13, 18).
- Electricity rate stored here; actual kWh billing against bookings is a future workstream.

---

### Table: `deposit_suggestions`

Append-only. Each owner submission creates a new row. Full suggestion history
is preserved per property without any mutation of existing rows.

```sql
CREATE TABLE deposit_suggestions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           TEXT        NOT NULL,
    property_id         TEXT        NOT NULL,
    owner_id            TEXT        NOT NULL,   -- user_id from JWT

    -- Suggestion
    suggested_amount    NUMERIC(10,2) NOT NULL,
    suggested_currency  TEXT        NOT NULL DEFAULT 'THB',
    owner_note          TEXT,                   -- optional message to admin

    -- Review state machine
    status              TEXT        NOT NULL DEFAULT 'pending',
    -- Values:   pending | approved | rejected
    -- Terminal: approved, rejected

    reviewed_by         TEXT,                   -- admin user_id; NULL until reviewed
    reviewed_at         TIMESTAMPTZ,
    admin_note          TEXT,                   -- owner-visible feedback

    -- Applied value (may differ from suggested_amount if admin adjusted on approve)
    applied_amount      NUMERIC(10,2),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_deposit_suggestions_property
    ON deposit_suggestions (tenant_id, property_id);
CREATE INDEX idx_deposit_suggestions_status
    ON deposit_suggestions (tenant_id, status);
CREATE INDEX idx_deposit_suggestions_owner
    ON deposit_suggestions (tenant_id, owner_id);
```

---

## 2. Status Machine — `deposit_suggestions.status`

```
                      ┌─────────┐
    owner submits     │         │
   ─────────────────► │ pending │
                      │         │
                      └────┬────┘
                           │
               ┌───────────┴───────────┐
          admin approves           admin rejects
               │                       │
               ▼                       ▼
         ┌──────────┐            ┌──────────┐
         │ approved │            │ rejected │
         │(terminal)│            │(terminal)│
         └──────────┘            └──────────┘
               │
               │  atomic side effect
               ▼
     property_charge_rules upserted:
       deposit_enabled = true
       deposit_amount  = applied_amount
       updated_by      = admin user_id
```

**Invariants:**
- Only `admin` can approve or reject (not manager — approval mutates the live charge rule).
- Approval atomically upserts `property_charge_rules` in the same request.
- Rejection makes no change to `property_charge_rules`.
- Multiple concurrent `pending` rows per property are allowed — admin acts on each by ID.
- No owner cancel action — once submitted it enters the admin queue.
- `admin_note` is required on reject (owner sees it in the portal as feedback).

---

## 3. API Endpoints

### Phase 952 — Admin: Property Charge Rules CRUD

```
GET  /admin/properties/{property_id}/charge-rules
     Returns current deposit + electricity config for the property.
     404 if no rule row exists yet.
     Auth: admin, manager.

PUT  /admin/properties/{property_id}/charge-rules
     Upsert the full rule for this property.
     Body: {
       deposit_enabled*        bool
       deposit_amount          number | null
       deposit_currency        string  (default: THB)
       deposit_notes           string | null
       electricity_enabled*    bool
       electricity_rate_kwh    number | null
       electricity_currency    string  (default: THB)
       electricity_notes       string | null
     }
     (* required)
     Writes:  updated_by = caller user_id
     Audit:   charge_rules_updated
     Auth:    admin, manager.

GET  /admin/properties/charge-rules
     List all properties' charge rules for the tenant.
     Auth: admin, manager.
```

### Phase 953 — Worker: Charge Config Pre-fill

```
GET  /worker/bookings/{booking_id}/charge-config
     Read-only. Returns active charge rule for the booking's property.
     Response: {
       deposit_enabled       bool
       deposit_amount        number | null
       deposit_currency      string
       electricity_enabled   bool
       electricity_rate_kwh  number | null
     }
     Purpose: pre-fills deposit amount prompt in the check-in wizard.
     If deposit_enabled=false → worker sees "No deposit for this property".
     If deposit_enabled=true + amount set → amount is pre-filled (worker can adjust).
     Auth: checkin, checkout, ops, worker roles.
     No writes — does not change the deposit collection write path.
```

### Phase 954 — Owner: Submit & Read Suggestions

```
POST /owner/properties/{property_id}/deposit-suggestion
     Submit a new suggestion (always creates a new row — append-only).
     Body: {
       suggested_amount*   number
       suggested_currency  string  (default: THB)
       owner_note          string | null
     }
     (* required)
     Audit:    deposit_suggestion_submitted
     Response: { id, status, suggested_amount, created_at }
     Auth:     owner (own properties only).

GET  /owner/properties/{property_id}/deposit-suggestion
     Suggestion history for this property, newest first.
     Returns: [ { id, status, suggested_amount, owner_note,
                  admin_note, reviewed_at, created_at } ]
     Does NOT expose property_charge_rules internals.
     Auth: owner (own properties only).

GET  /owner/properties/{property_id}/deposit-policy
     Minimal policy read.
     Returns: { deposit_enabled, deposit_amount, deposit_currency }
     Does NOT expose: electricity config, settlement records, deduction details.
     Auth: owner (own properties only).
```

### Phase 955 — Admin: Suggestion Review

```
GET  /admin/deposit-suggestions
     List suggestions for the tenant.
     Filters: ?status=pending|approved|rejected  ?property_id=
     Auth: admin, manager (read-only).

GET  /admin/deposit-suggestions/{suggestion_id}
     Single suggestion detail.
     Auth: admin, manager.

POST /admin/deposit-suggestions/{suggestion_id}/approve
     Approve a pending suggestion.
     Body: {
       applied_amount  number | null   (defaults to suggested_amount)
       admin_note      string | null
     }
     Transitions:   pending → approved
     Side effect:   upserts property_charge_rules atomically
                    (deposit_enabled=true, deposit_amount=applied_amount, updated_by=admin)
     Audit:         suggestion_approved + charge_rules_updated
     Auth:          admin only (not manager).

POST /admin/deposit-suggestions/{suggestion_id}/reject
     Reject a pending suggestion.
     Body: {
       admin_note  string   (required — owner sees this as feedback)
     }
     Transitions:   pending → rejected
     Side effect:   none (property_charge_rules unchanged)
     Audit:         suggestion_rejected
     Auth:          admin only.
```

---

## 4. Role Access Matrix

| Endpoint | admin | manager | ops | owner | worker/cleaner |
|---|---|---|---|---|---|
| GET charge-rules (admin list/detail) | ✅ | ✅ | read via allowlist | ❌ | ❌ |
| PUT charge-rules | ✅ | ✅ | ❌ | ❌ | ❌ |
| GET charge-config (worker pre-fill) | ❌ | ❌ | ✅ | ❌ | ✅ checkin/out |
| POST deposit-suggestion | ❌ | ❌ | ❌ | ✅ own | ❌ |
| GET deposit-suggestion (history) | ❌ | ❌ | ❌ | ✅ own | ❌ |
| GET deposit-policy | ❌ | ❌ | ❌ | ✅ own | ❌ |
| GET deposit-suggestions (admin review) | ✅ | ✅ | ❌ | ❌ | ❌ |
| POST .../approve | ✅ | ❌ | ❌ | ❌ | ❌ |
| POST .../reject | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## 5. Audit Events

All mutations write to `admin_audit_log` with real `actor_id` from JWT:

| Event | Trigger | Actor |
|---|---|---|
| `charge_rules_updated` | PUT charge-rules | admin/manager user_id |
| `deposit_suggestion_submitted` | POST deposit-suggestion | owner user_id |
| `suggestion_approved` | POST .../approve | admin user_id |
| `charge_rules_updated` | same approve (atomic) | admin user_id |
| `suggestion_rejected` | POST .../reject | admin user_id |

---

## 6. New Files

| File | Phase | Purpose |
|---|---|---|
| `src/api/property_charge_rules_router.py` | 952 | Admin deposit + electricity CRUD |
| Worker endpoint added to `worker_router.py` | 953 | `/worker/bookings/{id}/charge-config` |
| `src/api/deposit_suggestion_router.py` | 954–955 | Owner submit + admin review |
| `src/main.py` — two new `include_router` lines | 955 | Register both new routers |

---

## 7. Out of Scope for This Workstream

- Booking revenue modeling or nightly pricing estimation
- Electricity billing against guest stays (rate stored here; billing is a future workstream)
- Deposit settlement details visible to owner (policy only, not deduction/forfeit records)
- Owner notification on suggestion review (owner polls via portal)
- Charge rule version history / audit log of amount changes over time
