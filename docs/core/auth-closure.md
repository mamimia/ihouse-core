# Login / Identity / Access — Full Closure

> **Phases:** 863–873
> **Date:** 2026-03-22
> **Status:** Fully closed ✅

---

## Scope

| Scope | Status |
|---|---|
| Backend architecture, role enforcement, identity linking, invite provisioning, privilege consistency | ✅ Closed (Phase 868) |
| Full user-facing auth/account experience (13 flows) | ✅ Closed (Phase 869 audit + Phase 873 fixes) |

---

## Phase registry

| Phase | Title | Status |
|---|---|---|
| 863 | Check-in/check-out permission tightening | ✅ |
| 864 | Guest portal restructure (Current Stay model) | ✅ |
| 865 | Identity linking e2e proof | ✅ code-complete, config-enabled, pending live verification |
| 866 | Invite flow frontend verification | ✅ (31 tests) |
| 867 | Staff onboarding path verification | ✅ (39 tests) |
| 867-fix | Privilege consistency fix | ✅ (3 targeted tests) |
| 868 | Structural closure | ✅ |
| 869 | Full user-facing auth/account audit | ✅ (13-flow audit) |
| 871 | Standalone sign-up (`/register`) | ✅ |
| 872 | Auth routing + signed-in shell (`/welcome` resolver, signed-in Get Started) | ✅ |
| 873 | Auth surface polish (password policy, profile UX, no-access CTA) | ✅ |

---

## Canonical policies

### 1. Least-privilege invalid-role fallback

If a role value in `tenant_permissions` is not a member of `CANONICAL_ROLES`, the system defaults to `worker`.

Enforced in:
- `POST /invite/accept/{token}` — `invite_router.py`
- `POST /auth/login` — `auth_login_router.py`
- `POST /auth/google-callback` — `auth_login_router.py`

### 2. Admin cannot be provisioned via invite

The invite accept endpoint validates role against `INVITABLE_ROLES` (`CANONICAL_ROLES` minus `admin`).

### 3. Canonical role registry

All valid roles are defined in `services/canonical_roles.py`:

| Set | Contents |
|---|---|
| `CANONICAL_ROLES` | admin, manager, ops, owner, worker, cleaner, checkin, checkout, maintenance |
| `INVITABLE_ROLES` | CANONICAL_ROLES − {admin} |
| `FULL_ACCESS_ROLES` | admin, manager |
| `STAFF_ROLES` | worker, cleaner, checkin, checkout, maintenance, ops |
| `IDENTITY_ONLY` | identity_only (not a tenant role — identity-level access class) |

### 4. Identity continuity

A single Supabase Auth UUID anchors all identity providers (email, Google, future).
`lookup_user_tenant(db, uuid)` returns the same tenant/role regardless of auth method.
`provision_user_tenant` uses upsert on `(tenant_id, user_id)` — no duplicates.

### 5. Password policy (Phase 873)

Canonical rules defined in `hooks/usePasswordRules.ts`:
- 8+ characters, 1 uppercase, 1 number, 1 special character

Enforced on all surfaces: `/register`, `/login/reset`, `/update-password`, `/invite/[token]`, `/profile`.

---

## Test coverage

| Test file | Tests |
|---|---|
| `test_identity_linking_proof.py` | 8 |
| `test_invite_flow.py` | 6 |
| `test_invite_flow_e2e.py` | 31 |
| `test_staff_onboarding_path.py` | 39 |
| `test_privilege_consistency_fix.py` | 3 |
| `test_checkin_role_guard.py` | 31 |
| `test_auth_router_contract.py` | 21 |
| `test_e2e_flows.py` | 6 |
| **Total** | **145 pass, 0 fail** |

---

## Phase 869 audit — 13-flow closure matrix

| # | Flow | Status |
|---|---|---|
| 1 | Sign Up | ✅ Closed (Phase 873 fix — inline OTP verification) |
| 2 | Sign In | ✅ Closed (Phase 873 fix — removed property CTA, styled Sign up link) |
| 3 | Remember-Me / session persistence | ✅ Closed (caveat: checkbox cosmetic) |
| 4 | Forgot Password | ✅ Closed |
| 5 | Password Reset | ✅ Closed (Phase 873 — rules unified) |
| 6 | Invite Accept UX | ✅ Closed (Phase 873 — rules + PasswordInput) |
| 7 | Logout | ✅ Closed |
| 8 | Identity Linking / Unlinking | ✅ Closed (Phase 873 — inline form) |
| 9 | Callback / Redirect | ✅ Closed |
| 10 | No-Access Handling | ✅ Closed (Phase 873 — CTA → /welcome) |
| 11 | Profile / Account Basics | ✅ Closed (Phase 873 — API base fix) |
| 12 | OTP / Verification | ✅ Closed (Phase 873 fix — functional verifyOtp step in /register) |
| 13 | Get Started Auth Interaction | ✅ Closed |

---

## Pending live / manual verification

- Identity linking (Google ↔ email) — code-complete, pending live OAuth verification
- Invite email click-through — pending human inbox verification
- Guest-origin auth context preservation — structurally ready, functionally unbuilt (deferred)
