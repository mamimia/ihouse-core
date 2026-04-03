# Questions for Owner

These are questions that cannot be resolved by reading the repository. Each one represents genuine ambiguity that requires owner input to safely resolve before work proceeds.

Non-essential or answerable-by-reading questions are excluded.

---

## Priority 1 — Required Before Any Implementation Work

**Q1. What is the current true operational state?**

The documentation states 959 phases closed and the system at "33–35% product vision completion." But "completion" is relative to the full Domaniqo product vision, not to what's needed for current operations.

*What I need to know:* Is iHouseCore currently being used by real staff, with real guests, at real properties? Or is it still pre-launch? This changes everything about what "partial" means — a partial feature in a live system is different from a partial feature in a staging system.

---

**Q2. Which mobile worker flows are in real use today?**

The check-in flow exists as a 6-step wizard. The cleaner flow exists as a workflow with checklist backend. The check-out flow exists as 4 steps.

*What I need to know:* Are real workers (cleaners, check-in agents) using these flows on their phones today? Or are these prepared but not yet deployed to a real operation? This determines whether a gap is urgent or theoretical.

---

**Q3. What is the `DEV_PASSPORT_BYPASS` status in your actual staging environment?**

The code has `DEV_PASSPORT_BYPASS=true` which disables passport photo capture and storage. This flag being active means passport data from the check-in flow is not being persisted.

*What I need to know:* Is this flag active in your current running staging? And is this intentional while you test other parts of the flow, or was it forgotten?

---

**Q4. Who are the real users of this system right now?**

The role model defines: admin, manager, ops, owner, worker, cleaner, checkin, checkout, maintenance.

*What I need to know:* Which of these roles have real humans using them today, even in staging? Are there actual property owners viewing the owner portal? Are there real cleaners assigned and using the app? Or is all of this currently single-operator/admin-only?

---

## Priority 2 — Required Before Role-Specific Work

**Q5. Is the combined `checkin_checkout` role real or vestigial?**

The code references a `checkin_checkout` combined role at `/ops/checkin-checkout`. This is routed from `worker/page.tsx` but I could not confirm a corresponding canonical role definition.

*What I need to know:* Is `checkin_checkout` an actual intended role that needs to exist in `canonical_roles.py`? Or is it a shortcut for a single worker who does both, handled via `worker_roles[]` array? This affects how we build or extend that flow.

---

**Q6. What is the intended relationship between the `worker` canonical role and the sub-role `worker_roles[]` array?**

The system has `canonical_roles.py` defining `worker`, `cleaner`, `checkin`, `checkout`, `maintenance` as separate top-level roles. But it also has a `worker_roles[]` array inside `tenant_permissions.permissions` for sub-role assignment.

*What I need to know:* Is the intent that a person has a single canonical role (e.g. `cleaner`) OR that they have a canonical role of `worker` with sub-roles like `["cleaner", "checkin"]`? The code supports both patterns, but which is the intended authoritative model going forward?

---

**Q7. What is the actual scope of the "owner" role?**

The owner role sees a financial dashboard at `/owner`. The documentation mentions configurable transparency toggles.

*What I need to know:* Does the owner role represent a property owner who is an external stakeholder (can only see their own properties' financials), or can they ever take operational actions? And are there real property owners using this portal today?

---

## Priority 3 — Product Direction

**Q8. What is the "one property, end-to-end" milestone?**

The documentation references a checkpoint called "One Property, End-to-End" as the current focus before resuming the PMS/channel manager layer.

*What I need to know:* What does completing this milestone look like in your mind? Which specific flows must work, end-to-end, for you to consider it done? This is the most useful thing to know before any implementation begins.

---

**Q9. Is problem reporting (Phase F) a prerequisite for going live, or deferred?**

The gap analysis marks problem reporting as 0% and critical. But it's unclear whether it's blocking anything real or just a feature gap.

*What I need to know:* Do you need workers to be able to report property problems (pool, AC, plumbing) before you can use the system operationally? Or can you operate without it for a defined period?

---

**Q10. What is the relationship between iHouseCore and Domaniqo for external parties?**

The brand boundary is clear internally. But from a product perspective: does Domaniqo have a public-facing identity that guests interact with? Or is Domaniqo the operator brand and guests just see the property name?

*What I need to know:* Do guests see "Domaniqo" anywhere in the guest portal today? Should they? This affects the guest portal design and onboarding copy.

---

## Non-Questions (Resolved by Reading)

The following are NOT questions — they were resolved by direct reading:

- Role hierarchy: Fully documented and code-confirmed.
- OTA adapter coverage: 14 adapters, all verified in registry.
- Event sourcing architecture: Fully proven in code.
- Admin cannot be created via invite: Confirmed in code.
- DEV_MODE is blocked in production: Confirmed in env_validator.
- Staging is live on Vercel + Railway: Confirmed in documentation.
