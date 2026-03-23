# Admin Preview As & Admin Act As — Canonical Architecture Note

> **Status**: Canonical — Must be followed by all future implementations  
> **Created**: Phase 875 (2026-03-23)  
> **Scope**: Defines two distinct admin capabilities, their rules, and their lifecycle

---

## 1. Two Capabilities — Not One

The system defines two separate admin capabilities for inspecting and verifying role-specific surfaces. These must never be conflated.

| | Admin Preview As | Admin Act As |
|---|---|---|
| **Verb** | **See** | **Do** |
| **Purpose** | Visual inspection of a role's UI | Operational testing through a role's flows |
| **Identity** | Admin remains admin | Admin remains admin, operating through a role's permission lens |
| **Mutations** | Impossible — all mutation controls disabled | Permitted — real actions are performed |
| **Data** | Role-scoped read-only projection | Role-scoped operational data |
| **Product lifecycle** | Permanent production feature | Internal testing / QA only — never customer-available |

---

## 2. Admin Preview As (See)

### Definition

The admin views a read-only rendering of how a target role's surface appears. This is a **product feature** that ships to production.

### Rules

1. The admin does NOT leave their admin identity
2. The preview shows **role-appropriate data**, not admin data rendered in a different template
3. A cleaner preview shows what a cleaner would see (their assigned tasks, their properties) — not the full admin task board in a cleaner card layout
4. All mutation controls (buttons, forms, actions) are **hidden or visually disabled** with a "Preview Mode" indicator
5. No impersonation token is issued — no operational context switch occurs
6. The admin's session, cookies, and JWT remain unchanged
7. Minimal audit: log that admin opened a preview (role, timestamp)

### UI Indicator

A non-interactive banner:
```
👁 PREVIEW MODE: Viewing as Cleaner  |  Read-only  |  [Close Preview]
```

### Data Scoping

Preview data must come from an **explicitly read-only, role-scoped preview path** or a **server-enforced preview contract**. A cosmetic client-side query parameter is not sufficient — the server must enforce that the returned data matches what the target role would actually see.

This means Preview requires either:
- A dedicated `GET /preview/{role}/...` server endpoint that applies role-scoped filters, or
- A server-side middleware that intercepts preview-flagged requests and applies the target role's data permissions before returning results

The preview must NOT show admin-privileged data inside the role template.

| Wrong | Correct |
|-------|---------|
| Admin's 200 tasks displayed in cleaner card layout | Only tasks a cleaner would see (assigned, active, relevant property) |
| All 50 properties in owner portal | Only properties assigned to a representative owner |
| Full booking list in check-in stepper | Only today's arrivals for the relevant property |

### Availability

| Environment | Available |
|-------------|:---------:|
| Local dev | ✅ |
| Staging | ✅ |
| Production | ✅ |

---

## 3. Admin Act As (Do)

### Definition

The admin enters a scoped acting session with a target role's effective permissions. The admin performs real mutations through the role's operational flows. This is an **internal testing and QA capability**, not a customer-facing product feature.

### Rules

1. The admin's real identity is **always preserved** — never erased, replaced, or hidden
2. The admin does not "become" the target role — they are an admin performing a scoped acting session
3. Every mutation records dual attribution: `real_admin_user_id` + `effective_role` + `acting_session_id`
4. The acting session has a hard TTL (default: 1 hour, maximum: 4 hours)
5. The session can be ended manually or expires automatically
6. Full audit logging of every action taken while acting
7. The UI must display a persistent, non-dismissible banner indicating the acting state

### Identity Preservation Invariant

> **At no point during an Act As session does the system lose track of the real admin identity.**  
> The admin is always the true actor. The effective role is a permission lens, not an identity replacement.

### Token Model

When an Act As session is created, a scoped JWT is issued:

```
JWT Claims:
  sub:                <admin-uuid>           ← real identity (NEVER changes)
  tenant_id:          <tenant-uuid>
  role:               <target-role>          ← effective permissions
  token_type:         "act_as"               ← canonical signal
  acting_session_id:  <session-uuid>         ← links to session record
  real_admin_id:      <admin-uuid>           ← explicit redundancy for safety
  auth_method:        "act_as"
  exp:                <timestamp + TTL>
```

The `token_type: "act_as"` claim is the canonical signal. Any API handler or middleware can detect it and annotate mutations accordingly.

### Session Record: `acting_sessions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | uuid | Primary key |
| `real_admin_user_id` | uuid | The actual human admin. NOT NULL. |
| `real_admin_email` | text | Denormalized for audit readability |
| `acting_as_role` | text | The effective role (`cleaner`, `checkin`, etc.) |
| `acting_as_context` | jsonb | Optional scope narrowing (property ID, worker context) |
| `tenant_id` | uuid | Tenant scope |
| `created_at` | timestamptz | Session start |
| `expires_at` | timestamptz | Hard expiry |
| `ended_at` | timestamptz | Null until session ends |
| `end_reason` | text | `manual_exit` / `expired` / `admin_revoked` |

### Mutation Attribution

Every mutating API call made during Act As must record:

| Field | Value | Purpose |
|-------|-------|---------|
| `performed_by` | `<admin-uuid>` | The real human who did this |
| `effective_role` | `<target-role>` | The permission context applied |
| `acting_session_id` | `<session-uuid>` | Links to session record |
| `auth_method` | `act_as` | Distinguishes from normal operations |

### UI Indicator

A persistent, non-dismissible, high-contrast banner:
```
🔴 ACTING AS: Cleaner  |  Admin: admin@domaniqo.com  |  Expires: 47 min  |  [End Session]
```

This banner:
- Cannot be hidden, minimized, or styled away
- Uses high-contrast colors (red/amber) distinct from Preview Mode
- Shows the real admin email for clarity
- Includes a countdown and an explicit exit action

### Availability

Act As may exist **only** in local, staging, and internal QA environments.

| Environment | Available | Gate |
|-------------|:---------:|------|
| Local dev | ✅ | Admin role required |
| Staging / Internal QA | ✅ | Admin role required |
| Production (sold product) | ❌ **Architecturally absent** | Not disabled. Not hidden. Does not exist. |

---

## 4. Production Rule

In the sold production product:

- **Preview As** is a permanent admin feature. It ships. Customers use it.
- **Act As** does not exist as a customer-available surface. It is not hidden behind a flag. It is not soft-disabled. It is architecturally absent from the production build.

Act As is an internal testing and QA capability intended for local and staging environments only. Before the product ships to paying customers, Act As must be removed or hard-gated at the build/deploy level — not at the UI level.

---

## 5. Comparison Summary

| Dimension | Preview As | Act As |
|-----------|-----------|--------|
| What admin can do | View role surface (read-only) | Perform role actions (mutations) |
| Data shown | Role-scoped projection (not admin data) | Role-scoped operational data |
| Admin identity | Unchanged | Preserved — never replaced |
| Token issued | None (uses admin token + preview flag) | Scoped act_as JWT |
| Mutations possible | No | Yes |
| Audit depth | Minimal (view log) | Full (dual-attribution on every action) |
| UI indicator | 👁 "Preview Mode" banner (neutral) | 🔴 "Acting As" banner (high-contrast, non-dismissible) |
| Production | ✅ Ships | ❌ Does not exist |
| Staging | ✅ Available | ✅ Available |

---

## 6. Implementation Order

1. **Canonicalize Preview dropdown**: Lock the correct role labels, canonical role values (`checkin` not `checkin_staff`), and canonical target routes for all 8 preview roles. Remove all current mismatches. This must happen before any data-scoping work.
2. **Preview As (data isolation)**: Build server-enforced read-only preview contract. Add mutation-disabled UI mode with Preview banner.
3. **Act As (build new)**: Backend session/token endpoint, `acting_sessions` table, frontend acting banner, mutation attribution middleware.
4. **Production gate**: Before GA, remove Act As from production build pipeline.

---

## 7. Relevant Implementation Surfaces

- Preview dropdown: `components/PreviewAsSelector.tsx`
- Preview routing: `app/(app)/preview/page.tsx`
- Preview state: `lib/PreviewContext.tsx`
- Role enforcement: `middleware.ts` (`ROLE_ALLOWED_PREFIXES`)
- Canonical roles: `services/canonical_roles.py`
