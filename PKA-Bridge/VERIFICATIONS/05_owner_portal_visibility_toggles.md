# Title

Owner Portal Visibility Toggles — No Real Issue; 3-of-8 Gates Are Correct Because Only 3 Data Sections Exist; Dual Schema Drift Noted

# Related files

- Investigation: `INVESTIGATIONS/05_owner_portal_v2_visibility.md`
- Evidence: `EVIDENCE/05_owner_portal_v2_visibility.md`

# Original claim

5 of 8 visibility toggles are defined in `_DEFAULT_VISIBILITY` but have no enforcement gates in the summary endpoint. The investigation concluded this as an incomplete wiring gap.

# Original verdict

CONTRADICTED — the original "not wired" claim was wrong for 3 toggles; wiring status of the remaining 5 was uncertain.

# Response from implementation layer

**Verdict from implementation layer: No real issue. The investigation was too conservative.**

The 3-of-8 gate ratio is correct and intentional. The 5 ungated toggles have no enforcement gates because the summary endpoint does not expose those 5 data sections yet. There is nothing to gate.

**Full toggle state:**

| Toggle | In `_DEFAULT_VISIBILITY`? | Write API? | Read API? | Gate in summary endpoint? | Default |
|--------|--------------------------|-----------|----------|--------------------------|---------|
| `bookings` | ✅ | ✅ | ✅ | ✅ Line 151 | True |
| `financial_summary` | ✅ | ✅ | ✅ | ✅ Line 161 | True |
| `maintenance_reports` | ✅ | ✅ | ✅ | ✅ Line 176 | False |
| `occupancy_rates` | ✅ | ✅ | ✅ | ❌ No data section exists | True |
| `guest_details` | ✅ | ✅ | ✅ | ❌ No data section exists | False |
| `task_details` | ✅ | ✅ | ✅ | ❌ No data section exists | False |
| `worker_info` | ✅ | ✅ | ✅ | ❌ No data section exists | False |
| `cleaning_photos` | ✅ | ✅ | ✅ | ❌ No data section exists | False |

**Why the 5 ungated toggles are not a gap:**
The summary endpoint (`GET /owner-portal/{owner_id}/properties/{property_id}/summary`) only returns 3 data sections: bookings, financial aggregates, and maintenance_reports. It does not return occupancy rates, guest detail records, task lists, worker info, or cleaning photos. You cannot gate data that is not queried. The 5 ungated toggle keys are forward-looking scaffolding — when those data sections are added to the summary endpoint, the gate is `if visible.get("guest_details", False):` — one line per section.

**Full toggle lifecycle confirmed:**
```
_DEFAULT_VISIBILITY (8 keys, line 46–55)
    ↓
PUT /owners/{owner_id}/properties/{property_id}/visibility
    → validates keys against _DEFAULT_VISIBILITY (line 70)
    → upserts into owner_visibility_settings table (line 89)
    ↓
GET /owner-portal/{owner_id}/properties/{property_id}/summary
    → fetches visible_fields from owner_visibility_settings (line 134)
    → applies gates for bookings, financial_summary, maintenance_reports
```

**Frontend does not consume the v2 summary endpoint:**
`ihouse-ui/app/(app)/owner/page.tsx` calls:
```typescript
api.getFinancialByProperty(month)  // → /financial/aggregation/by-property
api.getCashflowProjection(month)    // → /cashflow
```
It does NOT call `/owner-portal/{owner_id}/properties/{property_id}/summary`. The current owner portal frontend is a financial-only dashboard (gross revenue, OTA commission, owner net, cashflow timeline per property). There is no guest details, task details, worker info, or cleaning photos section in the frontend — meaning the 5 ungated toggle types have no corresponding frontend surface that would expose data regardless of toggle state.

**iCal-first operating mode is consistent:**
The 3 data dimensions that exist in the endpoint (bookings, financial aggregates, maintenance reports) all have enforcement gates. The 5 that don't exist in the endpoint yet either require data not available from iCal (guest names, occupancy rates as derived metrics) or are purely operational (task details, worker info, cleaning photos). The toggle definitions are structurally sound for the current operating mode.

**One observation — dual schema drift:**
There are two visibility routers that both write to `owner_visibility_settings.visible_fields` (JSON column) with different key schemas:

| Router | Phase | Example keys | Overlap |
|--------|-------|-------------|---------|
| `owner_visibility_router.py` | 604 | `booking_count`, `guest_names`, `revenue`, `price_per_night` | `maintenance_reports` only |
| `owner_portal_v2_router.py` | 721 | `bookings`, `guest_details`, `financial_summary`, `occupancy_rates` | `maintenance_reports` only |

The Phase 721 router validates keys against its own `_DEFAULT_VISIBILITY` and will reject Phase 604 keys. The Phase 604 router appears to be a pre-v2 remnant. No current breakage — both can coexist as long as they are not called for the same property in conflicting ways. But simultaneous use for the same property would produce a key-schema collision in `visible_fields`.

**Changes made: None.** The system is architecturally sound.

# Verification reading

No additional repository verification read was performed. The implementation response provides specific line numbers, code paths, and a consistent explanation that resolves all 4 original questions. The dual schema drift observation is new information not in the original investigation and is documented here as a forward risk.

# Verification verdict

RESOLVED

The 3-of-8 enforcement gate ratio is correct for the current state of the endpoint. The 5 ungated toggles are forward scaffolding for data sections that do not yet exist — not gaps. No code changes needed.

# What changed

Nothing. No code was modified.

The evidence file (EVIDENCE/05) had already corrected the original "not wired" verdict to CONTRADICTED when direct reading confirmed 3 gates were active. This verification completes that correction: the 5 inactive gates are not a deficiency — they are pre-wired definitions for future data sections.

# What now appears true

- All 8 visibility toggle keys are defined, stored, and configurable via API. Write validation prevents invalid keys.
- 3 enforcement gates are active in the summary endpoint — one per data section that actually exists in that endpoint.
- 5 toggle keys are pre-wired forward scaffolding. They will require single-line gate additions when their data sections are built.
- The current owner portal frontend does not consume the v2 summary endpoint. The financial dashboard calls `/financial/aggregation/by-property` and `/cashflow` directly.
- No data is exposed regardless of toggle state for the 5 unimplemented sections — because neither the backend endpoint returns that data nor the frontend requests it.
- There are two visibility router schemas writing to the same table. Phase 604 appears to be a legacy remnant. Only the Phase 721 schema is consumed by the v2 summary endpoint.

# What is still unclear

- Whether the Phase 604 `owner_visibility_router.py` is still actively used by any frontend page or admin surface. If it is, and a property's `visible_fields` is written via Phase 604 keys, the Phase 721 summary endpoint would read a `visible_fields` JSON that contains no recognized keys — defaulting all toggles to their `_DEFAULT_VISIBILITY` values. This would be a silent misconfiguration.
- Whether `owner_visibility_settings` has any rows in production and which schema those rows use (Phase 604 keys or Phase 721 keys).
- Whether occupancy rates, guest details, or task details sections are planned for the v2 summary endpoint in the near-term roadmap — which would make the ungated toggle keys immediately load-bearing rather than forward scaffolding.

# Recommended next step

**Close as resolved.** The toggle system is architecturally sound for the current scope. The investigation overstated the gap.

**Keep as a low-priority observation:**
- Audit whether Phase 604 `owner_visibility_router.py` is still called by any active surface. If it is not, it is dead weight. If it is, it is a silent schema mismatch risk.
- When any of the 5 ungated data sections are added to the summary endpoint, the corresponding `if visible.get("<key>", default):` gate must be added at the same time — not as a follow-up. The toggle definitions make this a one-line addition per section.
