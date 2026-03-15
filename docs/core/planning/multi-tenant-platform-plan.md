# iHouse Core — Multi-Tenant Platform Plan

> [!NOTE]
> This is a **planning document only** — no code changes yet.
> Created: 2026-03-15 (Phase 775).
> Pre-requisite: Single-tenant staging activation (Phases 776–795) must be complete first.

---

## 1. Current State — Single-Tenant Reality

The system today runs as a single-tenant application with multi-tenant scaffolding:

| Area | Current State | Gap |
|------|---------------|-----|
| JWT model | `sub` claim = tenant_id | Should be: `sub` = user_id, `tenant_id` = custom claim |
| bookings table | No `tenant_id` column | Must be added for true isolation |
| booking_state | No `tenant_id` column | Same — derived projection |
| Role enforcement | `role_authority.py` exists but no middleware | No route-level enforcement |
| Tenant bridge | `DEFAULT_TENANT_ID` hardcoded | Must resolve dynamically from user→org mapping |
| Platform admin | Does not exist | No cross-tenant oversight capability |
| Tenant provisioning | Does not exist | No API to create new tenants |

These gaps are **safe in single-tenant mode** but must be resolved before onboarding a second tenant.

---

## 2. Target Architecture

### 2.1 Identity Model

```
Supabase Auth User (UUID)
  └── belongs to → Organization (tenant)
        └── has role → admin | manager | worker | owner

Platform Admin (super-admin)
  └── special Organization: "platform"
  └── can access all tenants for support/oversight
  └── cannot modify tenant data without audit trail
```

**JWT Claims (target):**
```json
{
  "sub": "user-uuid-from-supabase-auth",
  "tenant_id": "org_abc123",
  "role": "admin",
  "aud": "ihouse-core",
  "exp": 1234567890
}
```

Key change: `sub` becomes the **user identity**, `tenant_id` becomes a **custom claim** injected at login time from the `tenant_permissions` table.

### 2.2 Database Isolation

Every tenant-scoped table must have:
1. A `tenant_id` column (non-nullable, indexed)
2. RLS policy: `tenant_id = current_setting('request.jwt.claims')::json->>'tenant_id'`

Tables requiring `tenant_id` addition:
- `bookings` (currently missing)
- `booking_state` (currently missing)
- `booking_financial_facts` (verify)
- All task, notification, and operational tables (most already have it)

### 2.3 Query Pattern

All Supabase queries must pass through the RLS boundary. The API layer sets the JWT claim, and RLS filters automatically.

```
Request → JWT middleware → extract tenant_id
  → set request.jwt.claims on Supabase connection
  → RLS filters all queries automatically
```

No application-level `.filter(tenant_id=...)` — RLS is the **single enforcement point**.

---

## 3. Platform Layer

### 3.1 Platform Admin (Super-Admin)

| Capability | Description |
|------------|-------------|
| View all tenants | List tenants, see status, subscription, usage |
| Create tenant | Provision new organization + first admin |
| Suspend / reactivate tenant | Disable access without data loss |
| Cross-tenant search | Debug support: find bookings/events across tenants |
| Impersonate (read-only) | View a tenant's data as if logged in, audit-logged |
| System health | Cross-tenant metrics, error rates, resource usage |

**Platform admin is NOT a regular tenant.** Platform admins belong to a special `platform` organization and use a distinct JWT role: `platform_admin`.

### 3.2 Platform Admin Routes

```
GET    /platform/tenants                  — list all tenants
POST   /platform/tenants                  — create new tenant
GET    /platform/tenants/{id}             — tenant detail + usage
PATCH  /platform/tenants/{id}             — update tenant settings
POST   /platform/tenants/{id}/suspend     — suspend tenant
POST   /platform/tenants/{id}/reactivate  — reactivate tenant
GET    /platform/tenants/{id}/users       — tenant's users
POST   /platform/tenants/{id}/first-admin — bootstrap first admin for tenant
GET    /platform/health                   — cross-tenant system health
GET    /platform/audit-log                — platform-level audit trail
```

### 3.3 Platform Middleware

A new middleware layer:

```python
def require_platform_admin(tenant_id, role):
    """Only platform_admin role in 'platform' org can access /platform/* routes."""
    if tenant_id != "platform" or role != "platform_admin":
        raise HTTPException(403, "Platform admin access required")
```

---

## 4. Tenant Lifecycle

### 4.1 Tenant Creation Flow

```
Platform Admin calls POST /platform/tenants
  ├── Input: { name, plan, region, admin_email }
  ├── Creates organization record in `organizations` table
  ├── Generates tenant_id: "org_{slug}_{random}"
  ├── Creates Supabase Auth user for first admin
  ├── Creates tenant_permissions row (role=admin)
  ├── Sends welcome email with login link
  └── Returns: { tenant_id, admin_user_id, status: "active" }
```

### 4.2 First Admin Bootstrap Per Tenant

When a new tenant is created, the platform admin provides the first admin's email:

1. Supabase Auth user is created (email + temp password or magic link)
2. `tenant_permissions` row: `{ user_id, tenant_id, role: "admin" }`
3. Welcome email sent with login instructions
4. First admin can then:
   - Create properties via onboarding wizard
   - Invite additional users (managers, workers, owners)
   - Configure notification channels

### 4.3 Tenant States

```
                    ┌──────────────┐
                    │   created    │
                    └──────┬───────┘
                           │ first admin accepts
                    ┌──────▼───────┐
                    │    active    │◄─────────┐
                    └──────┬───────┘          │
                           │ suspend          │ reactivate
                    ┌──────▼───────┐          │
                    │  suspended   │──────────┘
                    └──────────────┘
```

No tenant deletion. Suspended tenants retain data but cannot log in.

---

## 5. Support & Oversight Model

### 5.1 Read-Only Impersonation

Platform admins can view a tenant's data for support purposes:

```
GET /platform/tenants/{id}/impersonate
  → Returns a time-limited read-only JWT with:
    { sub: platform_admin_user_id, tenant_id: target_tenant, role: "viewer", impersonating: true }
  → All queries are read-only (RLS allows SELECT but not INSERT/UPDATE/DELETE for "viewer" role)
  → Every impersonation generates an audit log entry
```

### 5.2 Audit Trail

All platform actions are logged:

| Event | Logged Fields |
|-------|---------------|
| Tenant created | platform_admin_id, tenant_id, admin_email |
| Tenant suspended | platform_admin_id, tenant_id, reason |
| Impersonation started | platform_admin_id, tenant_id, duration |
| Cross-tenant query | platform_admin_id, query_type, target_tenant |

---

## 6. Cross-Tenant Architecture Boundaries

### 6.1 What Is Shared

| Resource | Shared? | Notes |
|----------|---------|-------|
| Supabase project | Yes | Single Supabase instance, RLS isolates |
| OTA adapters | Yes | Same adapter code, tenant_id in channel_map |
| Notification infrastructure | Yes | Same dispatcher, per-worker channels |
| AI copilot endpoints | Yes | Same LLM, tenant-scoped context only |
| Storage buckets | Yes (with RLS) | Paths prefixed by tenant_id |

### 6.2 What Is Isolated

| Resource | Isolation Method |
|----------|-----------------|
| Database rows | RLS on `tenant_id` |
| Booking data | `tenant_id` column + RLS |
| Financial data | `tenant_id` column + RLS |
| Task data | Already has `tenant_id` |
| Properties | Already has `tenant_id` |
| Users | `tenant_permissions` maps user→tenant |
| API rate limits | Per-tenant sliding window (already exists) |
| Storage files | Bucket paths: `{tenant_id}/{type}/{file}` |

### 6.3 Hard Rules

1. **No cross-tenant data leakage** — RLS is the single enforcement point, not application code
2. **No shared state between tenants** — each tenant's booking_state is fully independent
3. **No tenant can see another tenant's data** — even through aggregate endpoints
4. **Platform admin access is audit-logged** — every cross-tenant action is recorded
5. **Tenant_id is immutable** — once assigned, never changes

---

## 7. Implementation Phases

> Executed AFTER single-tenant staging is validated (Phase 795+).

### Wave 1 — JWT & Identity (3 phases)

| Phase | Title | Description |
|-------|-------|-------------|
| 796 | JWT Model Migration | Change `sub` to user_id, add `tenant_id` as custom claim. Update `auth.py`, `tenant_bridge.py`. Migration for `tenant_permissions` if needed. |
| 797 | Login Flow Update | `/auth/login` resolves user → tenant → role, mints JWT with all 3 fields. Session endpoint returns structured identity. |
| 798 | Auth Middleware Hardening | All routes extract `tenant_id` from JWT claim (not `sub`). Backward-compatible: support old tokens during migration window. |

### Wave 2 — Database Isolation (3 phases)

| Phase | Title | Description |
|-------|-------|-------------|
| 799 | Add tenant_id to bookings | DDL migration: add `tenant_id` to `bookings`, `booking_state`, `booking_financial_facts`. Backfill existing rows with DEFAULT_TENANT_ID. |
| 800 | RLS Policy Update | Update RLS policies to use JWT `tenant_id` claim instead of `sub`. Verify all 48+ tables. |
| 801 | Query Pattern Audit | Audit all Supabase queries to ensure they rely on RLS, not manual filtering. Remove any `.filter(tenant_id=...)` patterns. |

### Wave 3 — Role Enforcement (2 phases)

| Phase | Title | Description |
|-------|-------|-------------|
| 802 | Role Enforcement Middleware | FastAPI middleware that checks JWT `role` against route requirements. Decorator: `@require_role("admin")`. |
| 803 | Route Permission Matrix | Define which roles can access which routes. Apply middleware to all existing routes. |

### Wave 4 — Platform Layer (4 phases)

| Phase | Title | Description |
|-------|-------|-------------|
| 804 | Organizations Table & API | `organizations` table (id, name, slug, plan, status, created_at). POST/GET /platform/tenants. |
| 805 | Tenant Provisioning | POST /platform/tenants creates org + first admin + tenant_permissions. Welcome email. |
| 806 | Platform Admin Role | `platform_admin` JWT role, platform middleware, /platform/* routes. |
| 807 | Tenant Lifecycle | Suspend/reactivate, impersonation (read-only), platform audit log. |

### Wave 5 — Verification & Hardening (3 phases)

| Phase | Title | Description |
|-------|-------|-------------|
| 808 | Multi-Tenant E2E Tests | Create 2 test tenants, verify complete isolation: bookings, tasks, financial, notifications. |
| 809 | Cross-Tenant Security Audit | Attempt data leakage between tenants. Verify RLS blocks all cross-tenant access. Test impersonation audit trail. |
| 810 | Platform Checkpoint XXVI | Full docs sync, multi-tenant verified, handoff document. |

---

## 8. Migration Strategy

### From Single-Tenant to Multi-Tenant

1. **Backward compatible**: Old JWTs (sub=tenant_id) continue working during migration window
2. **Data migration**: Existing rows get `tenant_id = DEFAULT_TENANT_ID` via backfill
3. **No downtime**: New columns are nullable during migration, then made NOT NULL after backfill
4. **Rollback safe**: If anything breaks, revert to `sub`-based auth (old code path remains)

### Tenant_id Format

```
org_{slug}_{4-char-random}
Example: org_seaside_villas_a7b2
```

- `slug` derived from organization name (lowercase, underscored)
- 4-char random suffix prevents collisions
- Immutable once created

---

## 9. Open Questions (To Resolve Before Implementation)

1. **Billing model**: Per-tenant subscription vs. per-booking fee? Affects `organizations` schema.
2. **Data residency**: Will tenants in different regions need separate Supabase projects?
3. **Tenant limits**: Max properties per tenant? Max users? Max bookings/month?
4. **Migration window**: How long do we support old JWT format alongside new?
5. **Platform admin onboarding**: Who are the first platform admins? How many?
