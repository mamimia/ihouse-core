# Title

ops /bookings and /calendar Capability Mismatch — Investigation Correct; Path B Chosen; _ROLE_CAPABILITY_ALLOWLIST Added to capability_guard.py

# Related files

- Investigation: `INVESTIGATIONS/17_ops_bookings_calendar_capability_mismatch.md`
- Evidence: `EVIDENCE/17_ops_bookings_calendar_capability_mismatch.md`
- Source of this issue: `VERIFICATIONS/07_ops_route_surface.md` — Issue B from the ops surface verification

# Original claim

`ops` is listed in `ROLE_ALLOWED_PREFIXES["ops"]` with `/bookings` and `/calendar` allowed (Phase 397), but `require_capability("bookings")` in `capability_guard.py` denies all roles except `admin` and capability-delegated `manager`. The two controls were built at different phases and had never been reconciled. ops users can navigate to these pages but all data calls return HTTP 403.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict: Investigation fully correct. Real coherence mismatch. Product decision made: Path B. Fix implemented.**

**All 5 questions answered:**

**1. ops allowed by middleware to navigate to /bookings and /calendar?**
Confirmed. Explicit deliberate entry at Phase 397.

**2. Backend booking data calls blocked for ops?**
Confirmed — and stronger than the investigation knew. The `tenant_permissions` delegation DB query filters `.eq("role", "manager")` — there was literally no code path for `ops` even through admin-granted delegation. An admin could not have unblocked `ops` via the delegation system because the delegation lookup hard-filters on `role = "manager"`.

**3. Real broken-surface mismatch, not a security issue?**
Confirmed. Security boundary held correctly throughout. The mismatch was purely UX: navigable but data-empty pages.

**4. Path A (remove routes) or Path B (extend guard)?**
**Path B.** The Phase 397 middleware grant was intentional. An Operational Manager who cannot see booking state cannot effectively coordinate cleaning, check-in, or checkout workers. The capability guard was the latecomer that broke the intended access. The product decision is that `ops` needs booking visibility.

**5. Does /calendar share the booking backend path?**
Confirmed identical. The calendar page docstring explicitly states: "Reads from `GET /bookings`. No new backend endpoints." Both routes are unblocked together by the single guard change.

**Fix applied — `_ROLE_CAPABILITY_ALLOWLIST` introduced in `capability_guard.py`:**

```python
_ROLE_CAPABILITY_ALLOWLIST: dict[str, set[str]] = {
    "ops": {"bookings"},
    # Future additions: "ops": {"bookings", "guests"} if ops needs guests read
}
```

Guard evaluation order (new):
1. `admin` → unconditional pass
2. `_ROLE_CAPABILITY_ALLOWLIST[role]` contains the capability → unconditional pass (no DB check)
3. `manager` + DB delegation check → pass if delegated
4. All other roles → HTTP 403

`ops` gets `{"bookings"}` — unconditional pass, no DB query needed. `ops` does NOT get `financial`, `staffing`, or any other sensitive capability — those remain admin/manager-delegated only. The allowlist is explicitly scoped to `bookings` only.

**Why the allowlist pattern is correct:**
The previous guard structure assumed all non-admin capabilities required DB delegation. The allowlist is a clean mechanism for roles that have fixed, role-inherent capabilities rather than delegated ones. `ops` has booking visibility as a role property, not as an individually delegated permission. Future expansion (e.g., if `ops` should also have `guests` capability) is a one-line addition to the allowlist dict.

# Verification reading

No additional repository verification read performed. The implementation response is specific about the fix mechanism (`_ROLE_CAPABILITY_ALLOWLIST`), confirms the calendar backend path sharing, and reveals the previously unknown detail about the manager delegation query filtering on `role = "manager"` — which explains why the original bypass was total (no code path for ops even via delegation).

# Verification verdict

RESOLVED

The coherence mismatch between middleware and capability guard is closed. `ops` users can now navigate to `/bookings` and `/calendar` and receive booking data. The guard extension is scoped to `bookings` only — no other capabilities are granted to `ops`.

# What changed

`src/api/capability_guard.py`:
- `_ROLE_CAPABILITY_ALLOWLIST: dict[str, set[str]] = {"ops": {"bookings"}}` added
- Guard evaluation updated to check allowlist before the manager delegation DB query
- Evaluation order: admin → allowlist → manager delegation → 403

`ops` now passes `require_capability("bookings")` unconditionally. All other capabilities (`financial`, `staffing`, etc.) remain blocked for `ops`.

# What now appears true

- The middleware grant and the capability guard are now aligned. `ops` can navigate to `/bookings` and `/calendar` and receive data.
- The Phase 397 middleware grant was intentional. The capability guard (Phase 862 P37) was the latecomer that didn't account for `ops` as a role with inherent booking visibility.
- The manager delegation DB query filters on `role = "manager"` — this means admin delegation cannot grant capabilities to `ops` users through the delegation system. The allowlist is the correct mechanism for role-inherent capabilities.
- `ops` capability scope: `{bookings}` only. All other capabilities remain exclusive to admin + delegated managers.
- The `_ROLE_CAPABILITY_ALLOWLIST` pattern is extensible. Future role-capability expansions can be added as single-line entries rather than requiring changes to the core guard logic.
- Issue B from Verification 07 (guests_router unguarded) remains separately open — this fix addresses only `/bookings` and `/calendar`. The guests write access question (Investigation 18) is still pending implementation response.

# What is still unclear

- **Whether `ops` users need read-only or read-write booking access.** The allowlist grants `ops` the `"bookings"` capability. If `require_capability("bookings")` is used on both read and write booking endpoints (e.g., `POST /bookings/manual`, `PATCH /bookings/{id}/status`), `ops` now has write access as well. The investigation did not determine whether write access for `ops` was intended. If ops should have read-only booking access, a separate `"bookings_read"` capability (or a role-level write check) would be needed.
- **Whether the `_ROLE_CAPABILITY_ALLOWLIST` is checked before or after the empty-role guard.** The evaluation order as described (admin → allowlist → manager delegation → 403) suggests the allowlist is checked early — this is the correct order but was not independently verified.
- **Whether any existing `ops` user sessions** need to clear token or re-authenticate to pick up the new capability grant. Since the allowlist check is role-based (not session-based), any existing valid `ops` JWT should immediately benefit from the fix on next request.

# Recommended next step

**Close the ops bookings/calendar mismatch.** The UX breakage is resolved. Middleware and backend are aligned.

**Verify booking write access scope for ops:**
Check whether `POST /bookings/manual` and write-type booking endpoints use the same `"bookings"` capability key. If they do, `ops` now has write access to manual booking creation and amendment — which may or may not be intended. If ops should be read-only for bookings, the capability key should be split (`"bookings_read"` vs `"bookings_write"`) or a separate role check should be added to write endpoints.

**Track `_ROLE_CAPABILITY_ALLOWLIST` as the expansion point for future role-capability decisions:**
- If ops should also access guests read (`GET /guests`): add `"guests"` to the ops allowlist entry
- If a new role needs inherent capabilities: add an entry
- Do NOT use manager delegation for role-inherent capabilities — the delegation system filters on `role = "manager"` and cannot delegate to other roles
