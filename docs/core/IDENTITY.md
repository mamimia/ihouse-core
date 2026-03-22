# IDENTITY — Canonical Authorization Model
> Phase 862 — System truth for identity, access, and authorization

---

## 5-Layer Access Pipeline

```
Identity → Auth Methods → Membership/Context → Role + Permissions → UI Surface
```

| Layer | What It Answers | Storage |
|-------|----------------|---------|
| 1. Identity | Who is this person? | `auth.users` (Supabase Auth UUID) |
| 2. Auth Methods | How did they prove it? | Supabase Auth (email+pw, Google, magic link) |
| 3. Membership | Which tenant(s) do they belong to? | `tenant_permissions` (user_id + tenant_id) |
| 4. Role + Permissions | What can they do inside that tenant? | `tenant_permissions.role` + `.permissions` JSONB |
| 5. UI Surface | What do they see? | Frontend middleware + route guards |

## Non-Negotiable Rules

1. **Login method is NOT the authorization model** — auth proves identity only
2. **No whitelist-based access** — no email lists, no hardcoded UUIDs
3. **No default tenant provisioning** — identity exists before membership
4. **Role fallback is None** — unknown users get rejected, not promoted
5. **Dev endpoints are gated** — `POST /auth/token` requires `IHOUSE_DEV_MODE=true`

## Canonical Roles

Defined in `services/canonical_roles.py` — single source of truth.

| Role | Access Level | Description |
|------|-------------|-------------|
| `admin` | Full | Tenant governance, all surfaces |
| `manager` | Full | Operational management |
| `ops` | Operational | Operational team member |
| `owner` | Business | Property owner visibility |
| `worker` | Task | General staff |
| `cleaner` | Task | Housekeeping staff |
| `checkin` | Task | Check-in staff |
| `checkout` | Task | Check-out staff |
| `maintenance` | Task | Maintenance staff |

## User Types & Lifecycle

### 1. Public Identity (Open Registration)
- **Entry**: Sign up via email+password or Google
- **State**: Supabase Auth UUID exists, no `tenant_permissions` row
- **Surface**: Minimal personal area (welcome, profile)
- **Transition**: Admin invite or property submission approval grants membership

### 2. Submitter (Future — Not Yet Implemented)
- **Entry**: Public user completes "Get Started" wizard
- **State**: `intake_requests` row + identity, no tenant membership yet
- **Surface**: My Properties (view/edit submitted properties)
- **Transition**: Admin approval → Owner

### 3. Staff (Invited Workers)
- **Entry**: Admin sends invite → user accepts with password
- **State**: `tenant_permissions` row with staff role
- **Surface**: Role-specific operational pages
- **Entry Pipelines**: Pipeline A (invite_router) or Pipeline B (staff_onboarding_router)

### 4. Operational Manager (Future)
- **Entry**: Admin assigns `ops` or elevated manager role
- **State**: `tenant_permissions` with role + delegated permissions JSONB
- **Surface**: Extended operational dashboard

### 5. Owner
- **Entry**: Submitter's property approved, or admin creates
- **State**: `tenant_permissions` with `owner` role
- **Surface**: Owner portal — financial reports, property status

### 6. Admin
- **Entry**: Bootstrap or explicit admin grant
- **State**: `tenant_permissions` with `admin` role
- **Surface**: Full access to all surfaces

### 7. Super Admin (Future — Cross-Tenant)
- **Entry**: Platform-level grant
- **State**: Multiple `tenant_permissions` rows or platform-level table
- **Surface**: Cross-tenant administration

### 8. Guest/Renter (Future)
- **Entry**: Booking creates temporary context
- **State**: Stay-scoped access (dates + property)
- **Surface**: Property instructions, schedules, communication

## Security Corrections Applied (Phase 862)

| Phase | Fix | Status |
|-------|-----|--------|
| P1 | Removed signup auto-provisioning | ✅ Done |
| P2 | JWT guard on password-update | ✅ Done |
| P3 | Role fallback → None (reject) | ✅ Done |
| P4 | Middleware: empty role → /no-access | ✅ Done |
| P5 | Removed DEFAULT_TENANT_ID/ROLE | ✅ Done |
| P6 | Removed dual bootstrap identity row | ✅ Done |
| P7 | Unified canonical roles module | ✅ Done |
| P8 | Dev token gated by IHOUSE_DEV_MODE | ✅ Done |
| P11 | Admin role enforcement on password-update | ✅ Done |
| P12 | Dev login endpoints gated by IHOUSE_DEV_MODE | ✅ Done |
| P13 | Removed bootstrap hardcoded DEFAULT_TENANT_ID | ✅ Done |
| P14 | Intake requests linked to Supabase Auth identity | ✅ Done |
| P15 | GET /auth/identity canonical surface | ✅ Done |
| P16 | GET /properties/mine + POST /properties/{id}/submit | ✅ Done |
| P17 | Submitter→Owner state machine | ✅ Done |
| P18 | GET/PATCH /auth/profile | ✅ Done |
| P19 | Frontend /profile page + middleware route | ✅ Done |

## Key Files

| File | Purpose |
|------|---------|
| `services/canonical_roles.py` | Single source of truth for roles |
| `services/role_authority.py` | Role lookup + resolution |
| `services/tenant_bridge.py` | User↔Tenant provisioning (requires explicit params) |
| `services/submitter_states.py` | Submitter→Owner state machine |
| `api/auth.py` | JWT verification + identity resolution |
| `api/auth_login_router.py` | Production login (email+pw, Google) |
| `api/auth_router.py` | Dev token, signup, identity, profile endpoints |
| `api/submitter_router.py` | /properties/mine + submit endpoints |
| `api/intake_router.py` | Public intake requests (with optional identity linkage) |
| `api/bootstrap_router.py` | Admin bootstrap (tenant_id now explicit in request) |
| `ihouse-ui/middleware.ts` | Frontend route guard |
| `ihouse-ui/app/(public)/profile/page.tsx` | Shared profile page |
