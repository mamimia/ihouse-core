# Preview / Act-As Dropdown Matrix — Canonical Reference

> **Status**: Canonical — Governs all Preview As and Act As dropdown implementations  
> **Created**: Phase 875 (2026-03-23)  
> **Parent Note**: `admin-preview-and-act-as.md`

---

## Three Layers — Kept Separate

The system has three distinct layers that must not be conflated:

| Layer | Purpose | Where It Lives |
|-------|---------|----------------|
| **1. Persistence / Assignment** | What is stored in the database for a staff member | `tenant_permissions.role` + `tenant_permissions.worker_roles[]` |
| **2. Invite Presets** | Convenience checkboxes that pre-fill sub-role flags when generating invitation links | `/admin/staff/requests` page UI |
| **3. Preview / Act-As Targets** | Distinct operational surface states that an admin needs to inspect or test | Preview dropdown in admin sidebar |

These serve different functions and have different cardinalities.

---

## Layer 1: Persistence / Assignment Model

### Top-Level Roles (radio select — mutually exclusive)

| Value | Label | Description |
|-------|-------|-------------|
| `admin` | Admin | Full tenant governance |
| `manager` | Operational Manager | Full operational access |
| `worker` | Worker | Staff member — must have ≥1 sub-role flag |
| `owner` | Owner | Property owner (financial/business visibility) |

### Worker Sub-Role Flags (checkboxes — combinable)

When `role = worker`, the `worker_roles[]` array contains one or more of:

| Flag Value | Label | Operational Surface |
|------------|-------|-------------|
| `cleaner` | Cleaner | Housekeeping flows |
| `checkin` | Check-in | Guest arrival flows |
| `checkout` | Check-out | Guest departure flows |
| `maintenance` | Maintenance | Repair/upkeep flows |

**Key rules:**
- A worker MUST have at least one sub-role flag (enforced in UI)
- A worker CAN have multiple flags (e.g., `['checkin', 'checkout']`)
- The combined state is represented by the flag array, not by creating a separate deep system role

### Legacy / System Roles (not in assignment UI)

| Value | Status | Note |
|-------|--------|------|
| `ops` | Exists in `canonical_roles.py` | Not exposed in admin assignment UI. Separate middleware prefix set. Future: may become an explicit assignment option. |
| `identity_only` | System access class | Not a tenant role. Auto-assigned to authenticated users with no tenant binding. |

---

## Layer 2: Invite Generation Presets

The "Generate Public Invite" UI on `/admin/staff/requests` offers convenience presets that pre-fill worker sub-role flags.

| Preset Checkbox | Effect on `worker_roles[]` |
|-----------------|---------------------------|
| Cleaner | `['cleaner']` |
| Checkin | `['checkin']` |
| Checkout | `['checkout']` |
| Check-in & Check-out | `['checkin', 'checkout']` |
| Maintenance | `['maintenance']` |
| Op Manager | Sets `role = manager` (not a worker flag) |

**Key rule:** These are UI convenience shortcuts. They do not create new system roles. "Check-in & Check-out" in the invite UI simply pre-selects both flags.

---

## Layer 3: Preview / Act-As Targets

These represent **distinct operational surface states** that an admin must be able to inspect (Preview As) or test (Act As).

### Revised Canonical Dropdown

| # | Dropdown Label | Token Role | Worker Flags | Target Route | Surface Description |
|---|---------------|------------|-------------|--------------|---------------------|
| 1 | **Ops Manager** | `manager` | — | `/dashboard` | Full operational dashboard: SSE streaming, financial overview, sync health, DLQ, portfolio cards |
| 2 | **Owner** | `owner` | — | `/owner` | Property owner portal: financial cards, cashflow, statements, per-property drill-down |
| 3 | **Cleaner** | `worker` | `['cleaner']` | `/ops/cleaner` | Cleaning flow: checklist, photo upload, issue reporting, supply tracking |
| 4 | **Check-in Staff** | `worker` | `['checkin']` | `/ops/checkin` | Check-in stepper: booking selector, arrival, passport, deposit, QR generation |
| 5 | **Check-out Staff** | `worker` | `['checkout']` | `/ops/checkout` | Check-out stepper: inspection, issue flagging, deposit settlement |
| 6 | **Check-in & Check-out** | `worker` | `['checkin', 'checkout']` | `/worker` | Combined worker dashboard showing both check-in and check-out tasks. Tests the real phone experience of a dual-flagged worker. |
| 7 | **Maintenance** | `worker` | `['maintenance']` | `/maintenance` | Maintenance flow: task list, problem reporting, category/severity, work notes, photo upload |

### What Was Removed

| Old Option | Reason Removed |
|-----------|---------------|
| **Worker (General)** | Not a meaningful surface state. A worker always has specific sub-role flags. The generic `/worker` route is the landing for any worker, but it renders differently based on their flags. The combined Check-in & Check-out target already covers the `/worker` dashboard use case. |

### What Was Added

| New Option | Reason Added |
|-----------|-------------|
| **Check-out Staff** | Was missing from the dropdown entirely. `checkout` is a distinct operational flow. |
| **Check-in & Check-out** | Represents the combined dual-flag worker experience. Required to inspect and test how the phone UI behaves when one person handles both arrival and departure. |

### What Was Fixed

| Issue | Old Value | Correct Value |
|-------|-----------|---------------|
| Check-in Staff value | `checkin_staff` | `checkin` (matches canonical role and `worker_roles` flag) |
| Ops Manager label | `Manager` | `Ops Manager` (matches admin assignment UI label) |

---

## How Each Target Maps Under Preview vs Act As

| Target | Preview As (See) | Act As (Do) |
|--------|:---:|:---:|
| Ops Manager | Read-only `/dashboard` with manager-scoped data | Full operational access, can manage bookings/tasks |
| Owner | Read-only `/owner` with representative owner data | Can view statements, drill into financials |
| Cleaner | Read-only `/ops/cleaner` with assigned cleaning tasks | Can acknowledge, complete, flag issues |
| Check-in Staff | Read-only `/ops/checkin` stepper | Can process arrivals, collect deposits, generate QR |
| Check-out Staff | Read-only `/ops/checkout` stepper | Can process departures, settle deposits |
| Check-in & Check-out | Read-only `/worker` combined task view | Can perform both check-in and check-out flows |
| Maintenance | Read-only `/maintenance` task list | Can acknowledge, report, submit work notes |

---

## Implementation Notes

### For Preview As (read-only)
- The dropdown value determines which role-scoped read-only preview to render
- For worker targets, the preview must simulate the correct `worker_roles[]` combination
- No actual JWT is issued — the admin views a server-enforced role-scoped projection

### For Act As (staging-only)
- The dropdown value determines the acting session parameters
- For worker targets, the `acting_sessions` record must include the `worker_roles` flags in `acting_as_context`
- The scoped JWT includes both `role: "worker"` and `worker_roles: ["checkin", "checkout"]` in claims

### Token Claims for Combined Worker Targets

```
JWT (Act As: Check-in & Check-out):
  sub:              <admin-uuid>
  role:             "worker"
  worker_roles:     ["checkin", "checkout"]
  token_type:       "act_as"
  acting_session_id: <session-uuid>
  real_admin_id:    <admin-uuid>
```

---

## Cross-Reference: Dropdown vs Assignment vs Invite

| Surface Target | Persistence Role | Worker Flags | Invite Preset |
|---------------|-----------------|-------------|---------------|
| Ops Manager | `manager` | — | "Op Manager" checkbox |
| Owner | `owner` | — | (role dropdown) |
| Cleaner | `worker` | `['cleaner']` | "Cleaner" checkbox |
| Check-in Staff | `worker` | `['checkin']` | "Checkin" checkbox |
| Check-out Staff | `worker` | `['checkout']` | "Checkout" checkbox |
| Check-in & Check-out | `worker` | `['checkin', 'checkout']` | "Check-in & Check-out" checkbox |
| Maintenance | `worker` | `['maintenance']` | "Maintenance" checkbox |
