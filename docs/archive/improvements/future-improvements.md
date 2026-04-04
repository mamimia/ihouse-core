# iHouse Core – Future Improvements

## Purpose

This document is the canonical backlog for forward-looking improvements,
deferred hardening items, and non-immediate architecture work.

It is not a phase timeline.

It is not a construction log.

It exists to keep future work centralized in one place while preserving
append-only historical records in `docs/core/phase-timeline.md`.


## Rules

- new future improvements must be recorded here
- phase-timeline remains historical and append-only
- historical references in older timeline entries are not rewritten
- duplicate backlog items should be merged here into one canonical entry
- each item should include where it was first noticed


## Entry Format

### Title
- status: open | deferred | blocked | resolved
- discovered_in: Phase XX, Phase YY
- source_context: short note
- priority: low | medium | high
- notes: concise implementation context


## Active Backlog

### Financial Model Foundation — Canonical Revenue Layer
- status: resolved
- discovered_in: Phase 62 planning discussion
- resolved_in: Phase 65 (in-memory extraction), Phase 66 (Supabase persistence)
- source_context: product direction — finance-aware platform
- priority: high
- notes: Phase 65 introduced BookingFinancialFacts (frozen dataclass, 5-provider extraction). Phase 66 created the booking_financial_facts Supabase table (append-only, RLS) and financial_writer.py to persist facts after BOOKING_CREATED APPLIED (best-effort, non-blocking). Invariant locked: booking_state must NEVER contain financial data.


### Event Time vs System Time Separation
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: distributed OTA ingestion timing semantics
- priority: medium
- notes: separate `occurred_at` from `recorded_at` so delayed or out-of-order external events remain auditable without weakening ordering guarantees. Use `recorded_at` for canonical ordering and preserve `occurred_at` for business history.

### Dead Letter Queue for External Event Failures
- status: resolved
- discovered_in: Phase 20 era backlog
- resolved_in: Phase 38
- source_context: external event failure retention
- priority: medium
- notes: [Claude] Phase 38 implemented ota_dead_letter table (append-only, RLS) and dead_letter.py (best-effort, non-blocking). Rejected OTA events are now preserved. E2E verified.

### External Event Ordering Protection
- status: resolved
- discovered_in: Phase 21, Phase 27
- verified_in: Phase 37
- resolved_in: Phase 44 (ota_ordering_buffer table + buffer_event/get_buffered_events/mark_replayed), Phase 45 (ordering_trigger.py, auto-replay on BOOKING_CREATED)
- source_context: OTA events may arrive out of order
- priority: high
- notes: [Claude] Phase 37 verified current behavior: BOOKING_CANCELED before BOOKING_CREATED raises BOOKING_NOT_FOUND — deterministic rejection, not data loss. Phase 44 introduced ota_ordering_buffer table (Supabase) and ordering_buffer.py (buffer_event, get_buffered_events, mark_replayed). Phase 45 closed the loop: ordering_trigger.py fires automatically on BOOKING_CREATED APPLIED, replays any waiting buffer rows via replay_dlq_row, marks them replayed. E2E verified: CANCELED → buffer → CREATED → auto-trigger → 0 waiting.

### Business Idempotency Beyond Envelope Idempotency
- status: resolved
- discovered_in: Phase 21, Phase 27
- resolved_in: Phase 36
- source_context: duplicate business events with different envelope identifiers
- priority: high
- notes: [Claude] Phase 36 verified that apply_envelope already provides two layers of business-level dedup: (1) by booking_id, (2) by composite (tenant_id, source, reservation_ref, property_id). E2E test confirmed that a duplicate BOOKING_CREATED with a different request_id returns ALREADY_EXISTS without writing a new booking_state row. No additional business-idempotency registry is required at this stage.

### Business Identity Enforcement
- status: resolved
- discovered_in: Phase 21
- resolved_in: Phase 36
- source_context: deterministic booking identity hardening
- priority: high
- notes: [Claude] Phase 36 verified and formally documented canonical booking_id rule: booking_id = "{source}_{reservation_ref}". This rule is applied consistently in booking_created and booking_canceled skills, and apply_envelope reads booking_id from the emitted event payload. The combination of deterministic booking_id construction and apply_envelope dedup eliminates the risk of duplicate booking_state writes for the same OTA identity.

### OTA Schema / Semantic Normalization
- status: deferred
- discovered_in: Phase 21
- source_context: provider field semantics differ
- priority: medium
- notes: introduce stronger channel-specific normalization rules for timezone, currency, guest counts, and similar provider-specific payload semantics while preserving the shared canonical pipeline.

### OTA Integration Hardening
- status: deferred
- discovered_in: Phase 21
- source_context: external ingress protection
- priority: medium
- notes: backlog bucket for rate limiting, webhook replay protection, audit logging, and channel-specific authentication policies around OTA ingress.

### Idempotency Monitoring
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: operational visibility
- priority: medium
- notes: add metrics and monitoring for duplicate envelope detection, retry storms, and integration-side anomalies.

### Multi Projection Support
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: read-model expansion
- priority: low
- notes: future projections may include availability, revenue, and analytics read models beyond `booking_state`.

### Replay Snapshot Optimization
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: long-term replay performance
- priority: low
- notes: when the event log grows large, introduce replay snapshots to reduce rebuild cost without weakening canonical event authority.

### External Event Signature Validation
- status: resolved
- discovered_in: Phase 20 era backlog
- resolved_in: Phase 57 (signature_verifier.py, HMAC-SHA256, 5 providers)
- source_context: webhook authenticity
- priority: medium
- notes: [Claude] Phase 57 introduced signature_verifier.py with HMAC-SHA256 validation for all 5 OTA providers. Each provider has a dedicated header (X-Booking-Signature, X-Expedia-Signature, X-Airbnb-Signature, X-Agoda-Signature, X-TripCom-Signature) and env var (IHOUSE_WEBHOOK_SECRET_{PROVIDER}). Dev-mode skip when secret not set. 403 SIGNATURE_VERIFICATION_FAILED returned on mismatch.

### OTA Sync Recovery Layer
- status: blocked
- discovered_in: Phase 27
- source_context: synchronization-style OTA notifications
- priority: medium
- notes: some OTA ecosystems emit synchronization signals rather than deterministic lifecycle facts. A future recovery layer may fetch snapshots and derive deterministic outcomes, but it must never mutate canonical state directly and must still feed only deterministic facts into the canonical apply gate.

### Amendment Handling
- status: blocked
- discovered_in: Phase 27 and later OTA evolution notes
- source_context: deterministic support for reservation modifications
- priority: medium
- notes: the current rule remains `MODIFY -> deterministic reject-by-default`. Future amendment support is allowed only after deterministic classification, reservation identity stability, safe ordering guarantees, and state-safe application rules exist.


### DLQ Controlled Replay
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 39
- source_context: DLQ rows are preserved but currently unactionable
- priority: high
- notes: [Claude] Phase 39 implemented replay_dlq_row: reads ota_dead_letter, resolves skill, calls apply_envelope with new idempotency key, persists replayed_at/replay_result/replay_trace_id back to row. Never bypasses apply_envelope. Idempotent — re-running APPLIED row is a no-op.

### DLQ Observability and Alerting
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 40 (ota_dlq_summary view, dlq_inspector.py), Phase 41 (dlq_alerting.py, DLQ_ALERT_THRESHOLD)
- source_context: operational visibility on rejected OTA events
- priority: medium
- notes: [Claude] Phase 40 added ota_dlq_summary view (group by event_type/rejection_code, pending/replayed counts) and dlq_inspector.py (get_pending_count, get_replayed_count, get_rejection_breakdown). Phase 41 added dlq_alerting.py: check_dlq_threshold emits WARNING to stderr when pending >= threshold. Configurable via DLQ_ALERT_THRESHOLD env var (default 10).

### Idempotent DLQ Replay Tracking
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 39
- source_context: safe replay from DLQ
- priority: medium
- notes: [Claude] Phase 39 added replayed_at (timestamptz), replay_result (text), replay_trace_id (text) columns to ota_dead_letter (migration: 20260308174500_phase39_dlq_replay_columns.sql). Replay outcome is written back after every replay attempt.

### booking_id Stability Across Provider Schema Changes
- status: resolved
- discovered_in: Phase 36
- resolved_in: Phase 68
- source_context: booking_id is derived from provider-supplied fields
- priority: medium
- notes: [Claude] Phase 68 introduced booking_identity.py with normalize_reservation_ref(provider, raw_ref) — strips whitespace, lowercases, and applies per-provider prefix stripping (bookingcom: BK-, agoda: AGD-/AG-, tripcom: TC-). All 5 adapters now call normalize_reservation_ref() in normalize() before constructing reservation_id. The locked formula booking_id = {source}_{reservation_ref} (Phase 36) is unchanged. 30 contract tests cover all providers, determinism, and edge cases.

### BOOKING_AMENDED Support
- status: resolved
- discovered_in: Phase 42
- resolved_in: Phase 49 (AmendmentFields schema, amendment_extractor.py), Phase 50 (apply_envelope DB branch, BOOKING_AMENDED enum value), Phase 51-57 (Python pipeline routing), Phase 69 (booking_amended skill, registry wiring, service.py hook)
- source_context: Phase 42 investigated all preconditions; Phase 43 verified status column
- priority: medium
- notes: [Claude] All 10 prerequisites satisfied. Phase 69 wired the full Python pipeline: booking_amended skill (transforms OTA adapter envelope → BOOKING_AMENDED emitted event), registered in kind_registry.core.json and skill_exec_registry.core.json. service.py updated with best-effort BOOKING_AMENDED financial facts write. Adapters already emit booking_id + amendment fields in to_canonical_envelope. Full end-to-end: OTA webhook → pipeline → BOOKING_AMENDED envelope → booking_amended skill → apply_envelope updates booking_state (check_in, check_out via COALESCE). 20 contract tests added (451 total).

## Resolved / No Longer Open

### OTA External Surface Hardening
- status: resolved
- discovered_in: Phase 27
- source_context: explicit OTA lifecycle surface
- priority: none
- notes: this was resolved later when the system adopted explicit canonical lifecycle events instead of treating `BOOKING_SYNC_INGEST` as the canonical external business surface. Keep this entry only as migration history, not as active backlog.


## Migration Note

Historical future-looking notes still exist inside older append-only
timeline entries.

Those historical references remain valid as history.

From this point forward, new future improvements must be recorded in
this file instead of being added as new backlog content inside
`docs/core/phase-timeline.md`.

## Follow-up from Phase 33 — OTA runtime to canonical apply alignment

[Claude] Resolved in Phase 34 (discovery) and Phase 35 (implementation).

Phase 34 proved the routing and emitted-event alignment gap. Phase 35 implemented the minimal fix. Phase 36 confirmed that business identity is deterministic and business dedup is enforced by apply_envelope.

This follow-up is fully resolved.


---

## Forward Product and Architecture Bundle
*Added: Phase 77 closure. Source: user forward-planning note.*

> These are NOT an immediate backlog. They are serious product-direction items to keep in mind while planning future phases, so decisions do not accidentally close these doors.

The core intent: keep the canonical architecture clean and strong while gradually adding thin layers that make the product operationally complete, trustworthy, and useful to real property managers and owners.

Guiding questions for future phases:
- Does this improve operator visibility?
- Does it improve trust in the data?
- Does it help real property managers act faster?
- Does it preserve the canonical architecture?

### Visibility and Trust group

#### Reservation Timeline / Audit Trail
- status: open
- priority: high (builds on existing event_log — zero DB cost)
- notes: Per-booking timeline showing the full event story: created, amended, canceled, occurred_at, recorded_at, buffered, replayed, DLQ, financial updates, state transitions. Does not change the canonical core — only surfaces what already exists in event_log in a human-readable form.

#### Integration Health Dashboard
- status: open
- priority: high
- notes: Operational dashboard beyond the /health endpoint. Per-provider: last successful ingest, occurred_at vs recorded_at lag, buffer counts, DLQ counts, reject counts, stale provider alerts. Uses data the system already collects.

#### Conflict Detection and Mapping Coverage
- status: open
- priority: medium
- notes: Visibility layer for overlaps on same property, missing property mapping, incomplete canonical coverage, potential overbooking risk, provider mapping gaps. Strengthens trust without requiring a full outbound channel manager.

### Reliability and Recovery group

#### OTA Reconciliation / Recovery Layer
- status: open
- priority: medium
- notes: Periodic comparison between iHouse Core state and external OTA state. Detects: booking missing internally, status mismatch, date mismatch, financial facts missing, provider drift. Implemented as a detection and correction-support layer — never bypasses apply_envelope.

### Financial Clarity group

#### Payment Lifecycle / Revenue State Projection
- status: open
- priority: medium
- notes: Dedicated financial status layer with payment states: guest_paid, ota_collecting, payout_pending, payout_released, reconciliation_pending, owner_net_pending. Builds on BookingFinancialFacts (Phase 65/66) without polluting booking_state.

#### Owner Statements and Owner-Facing Views
- status: open
- priority: medium
- notes: Lightweight owner-facing layer: monthly statement, property revenue summary, owner net view, payout summary, scoped role visibility. Turns internal financial data into a usable business surface for property managers and owners.

### Operational Usefulness group

#### Guest Pre-Arrival / Check-In Intake
- status: deferred
- priority: low-medium
- deferred_reason: iCal-first constraint — no reliable guest email, phone, or trusted pre-arrival contact path in the majority of real bookings
- full_spec: `docs/future/guest-pre-arrival-form.md`
- notes: Lightweight intake flow per reservation before arrival: guest contact, arrival time, ID upload, agreement confirmation, special notes, pre-arrival readiness status. Viable only when OTA API access, OTA messaging integration, or richer guest identity exists. Interim path: staff-generated invite after verified contact established. See full spec for dependency map.

#### Task Automation for Operations
- status: open
- priority: low-medium
- notes: Rule-based task layer driven by booking events: new booking → prep task, checkout tomorrow → cleaning task, amendment → reschedule tasks, cancellation → cancel pending tasks. Architecture is already event-driven — natural extension of the existing model.


---

## Forward Adapter Expansion Wave
*Added: Phase 77 closure. Source: user forward-planning note.*

> This is NOT a command to build all adapters immediately. It is a prioritization note so future roadmap decisions follow the right order.

**Principle:** More adapters is not automatically better. A smaller set of strong, well-behaved adapters is better than many shallow integrations. The stronger metric is market coverage and customer confidence per adapter.

**Current core set (done):** Booking.com, Airbnb, Expedia, Agoda, Trip.com.

### Recommended next adapter wave

#### Tier 1 — Vrbo
- status: open
- priority: highest in next wave
- notes: Largest gap in vacation rental credibility. Connects with Booking.com/Airbnb/Expedia as a must-have for management companies focused on villas, holiday homes, vacation rentals. Established connectivity ecosystem.

#### Tier 1 — Google Vacation Rentals
- status: open
- priority: very high
- notes: Not a classic OTA but a critical distribution surface. Many travelers start searches on Google. Official onboarding guidance for vacation rental integrations available. Makes the platform feel modern and complete.

#### Tier 1.5 — Traveloka
- status: open
- priority: high (regional)
- notes: Dominant platform in Southeast Asia — strategically relevant given Thailand and regional property-management context. Improves market fit for Southeast Asian operators.

#### Tier 2 — MakeMyTrip
- status: open
- priority: medium
- notes: Major player in India. Expands iHouse Core into the Indian travel market and adds commercial depth beyond the global channel set.

#### Tier 2 — Despegar
- status: open
- priority: medium
- notes: Strongest travel brand in Latin America. Gives the system broader global coverage beyond English-speaking and Asian channels.

#### Tier 3 — Future candidates
- Rakuten Travel, Hotelbeds, Hostelworld, Hopper, additional regional/niche channels based on customer profile.

**Planning rule:** When choosing the next adapter, prefer channels that increase customer confidence fast, improve coverage in a meaningful region, have clear strategic value for management companies, and fit the current architecture without unusual complexity.

---

## Financial UI and Revenue Surfaces Product Direction
*Added: Phase 96 closure. Source: user forward-planning note + architecture analysis.*

> **Status: deferred — serious near-future direction. Not immediate.**
> This section captures the financial UI product vision, why it matters now,
> what real SaaS competitors do well, and the precise architectural entry point.

---

### Why Phase 93 Changed Things

Before Phase 93, iHouse Core was **booking-aware**.
It could record, track, amend, and cancel reservations across 10 OTAs.

After Phase 93, it is becoming **business-aware**.
It now understands not only *that* a booking happened — but *where the money stands*.

The 7-state `PaymentLifecycleStatus` machine can answer:
- Is the guest paying, or is the OTA collecting?
- Has the payout been released, or is it pending?
- Is there a reconciliation gap?
- What does the owner actually net?
- Is this booking's financial picture complete or partial?

That unlocks a product layer that was previously impossible to build correctly.

---

### What Real SaaS Products Do — and What They Get Wrong

Before designing this, it is worth understanding how the strongest tools in this space approach it.

**Guesty** (leading PMS, ~$400M ARR, PE-backed):
- Owner statements as first-class PDF exports
- Per-booking gross/fees/net breakdown
- Multi-property owner view
- Weakness: financial UI is often separated from real-time booking state. Owners see stale aggregations, not live lifecycle state.

**Hostaway** (fast-growing PMS, strong in EU/AU):
- OTA channel-separated financial reporting
- Payout schedule calendar
- Provider revenue comparison built in
- Weakness: overly complex for small operators. Reconciliation is manual.

**Lodgify** (mid-market, strong in villas):
- Clean owner-facing revenue summaries
- Occupancy-correlated revenue charts
- Weakness: no lifecycle-aware status. Payouts are assumed to be on time.

**Stripe** (payments infrastructure — not a PMS but best-in-class financial UX):
- Revenue charts with drill-down to individual transactions
- Balance / payout / reserve distinction shown clearly
- Beautiful exception-first design: show what is normal at a glance, alert on anomalies
- **Key insight: never show everything — show the delta from normal first.**

**Quickbooks / Xero** (accounting tools):
- Reconciliation-first design
- Strong at "what do we still need to match?"
- Weakness: too heavy for property-manager workflows. Overkill.

**Key insight from competitive analysis:**

Most PMS tools treat payout status as a *calendar estimate* — they guess when money should arrive
based on expected payout schedules, not based on actual evidence.
iHouse Core does something meaningfully different: it models lifecycle state explicitly from
available provider signals, so its conclusions are *qualified by evidence* rather than assumed.

This does not mean iHouse Core can always claim certainty. Not every OTA provides equally
complete or equally reliable financial signals. Some providers send explicit payout confirmations;
others only confirm the booking and leave payout inference to the system. The key differentiator
is that iHouse Core is transparent about *what it knows and how it knows it*, rather than
presenting all figures with uniform confidence.

That distinction — being honest about evidence quality — is more trustworthy than false precision.
It is also more defensible when financial figures are exposed to owners.

---

### Epistemic Model — Three Tiers of Financial Knowledge

*Refined: Phase 97 (user note on evidence-quality separation).*

All financial figures surfaced by iHouse Core must be understood within one of three tiers.
This model should be explicit at the API level, visible in the UI, and clearly documented for
owner-facing surfaces where trust is highest.

**Tier A — Provider-Attested Facts**
- Values the OTA webhook explicitly stated in its payload
- Examples: `booking_amount`, `mmt_commission`, `klook_commission`, `net_payout`, `currency`
- Status: `source_confidence = FULL` qualifies here
- How to label in UI: ✅ *Confirmed by {provider}*
- Reliability: as reliable as the provider's webhook. Most providers are consistent here.

**Tier B — System-Derived States**
- Values computed by iHouse Core logic from Tier A inputs
- Examples: `derived_net = booking_amount - commission` when `net_payout` is absent,
  `lifecycle_status` produced by `project_payment_lifecycle()`, idempotency keys
- Status: `source_confidence = ESTIMATED`; lifecycle states with strong evidence
- How to label in UI: 🔵 *Calculated by iHouse Core from provider data*
- Reliability: deterministic and auditable, but one step removed from provider confirmation.
  Should be presented as a system conclusion, not as a provider fact.

**Tier C — Estimated or Incomplete Interpretations**
- Values inferred when provider data is missing, partial, or ambiguous
- Examples: `source_confidence = PARTIAL`, `lifecycle_status = UNKNOWN`,
  lifecycle states inferred from booking type without explicit payout signal
- How to label in UI: ⚠️ *Estimated — provider data incomplete*
- Reliability: the system's best inference. Must be flagged clearly. Never shown as confirmed.

**Application to lifecycle states:**

| Lifecycle Status | Typical Tier | Notes |
|-----------------|-------------|-------|
| `GUEST_PAID` | B or A | A if provider confirms payment; B if inferred from booking_confirmed |
| `OTA_COLLECTING` | B | Inferred from OTA-type booking; rarely provider-attested |
| `PAYOUT_PENDING` | B | Lifecycle logic conclusion, not provider confirmation |
| `PAYOUT_RELEASED` | B → A | A only if provider sends explicit payout event; B otherwise |
| `RECONCILIATION_PENDING` | B | System-detected gap; show as ⚠️ |
| `OWNER_NET_PENDING` | C | Downstream of multiple inferences; label clearly |
| `UNKNOWN` | C | Always surfaced as ⚠️ with explanation |

**Rule for UI:**
Tier A figures can be shown without qualification.
Tier B figures must always show the derivation basis (tooltip or badge).
Tier C figures must always show a warning and never appear in totals without explicit user acknowledgement.

**Rule for owner statements:**
Owner statements must show the Tier of each financial figure.
A statement where all figures are Tier A or B is ready to send.
A statement containing Tier C figures must be flagged for review before sending.

---

### Recommended Financial UI Architecture

> **Architectural invariant: `booking_state` must NEVER contain financial data.**
> All financial surfaces read from `booking_financial_facts` and the payment lifecycle projection layer.
> No UI surface bypasses this separation.

The financial UI should be structured as **4 rings**:

```
Ring 1 — Financial API Layer       (read-only aggregation endpoints)
Ring 2 — Financial State Surface   (per-booking lifecycle status + epistemic tier)
Ring 3 — Portfolio Surfaces        (across bookings, properties, providers)
Ring 4 — Owner / External Surfaces (simplified, role-scoped, tier-filtered views)
```

Rings should be built in order. Ring 2 before Ring 3. Ring 3 before Ring 4.

---

### Specific Surfaces — Prioritized

#### 1. Financial Summary Widget (Ring 2 — per booking)
- status: open
- priority: high (builds directly on Phase 93 output)
- suggested_entry_phase: 100–102
- notes: A compact, per-booking financial status card. Shows:
  `lifecycle_status`, `total_price`, `ota_commission`, `net_to_property`, `currency`,
  `source_confidence` (FULL / ESTIMATED / PARTIAL), and a plain-English explanation
  from `explain_payment_lifecycle()`. This is the fastest win and directly
  surfaces Phase 93's value to users. Single-booking scope. Zero new DB work.

#### 2. Financial Aggregation API (Ring 1 — read-only endpoints)
- status: open
- priority: high (everything UI-side depends on this)
- suggested_entry_phase: 100–103
- notes: A set of read-only FastAPI endpoints that aggregate
  `booking_financial_facts` by property, provider, date range, and lifecycle status.
  No mutations. No booking_state involvement. Returns structured summaries:
  - `GET /financial/summary?tenant_id=&period=`  →  gross, commission, net totals
  - `GET /financial/by-provider?...`              →  per-OTA breakdown
  - `GET /financial/by-property?...`              →  per-property breakdown
  - `GET /financial/lifecycle-distribution?...`   →  count by PaymentLifecycleStatus
  This is the backbone layer. All UI surfaces query this.

#### 3. Financial Dashboard (Ring 3 — portfolio-level)
- status: open
- priority: high
- suggested_entry_phase: 103–106
- design_reference: Stripe balance dashboard + Guesty owner view
- notes: High-level operator screen. Key metrics:
  - **Gross Revenue** (confirmed bookings, period selectable)
  - **OTA Commission Total** (how much is being paid across all providers)
  - **Net to Portfolio** (what the operation actually retains)
  - **Payout Pending** (how much is on its way but not yet released)
  - **Payout Released** (confirmed received)
  - **Reconciliation Pending** (items needing attention)
  - **Owner Net Pending** (amount not yet settled to owners)
  - **Lifecycle Distribution** (pie/bar of 7 states across active bookings)
  - **Provider Health** (quick visual: which OTAs have drift/gaps)
  Design principle from Stripe: show the exception first, not the total.
  A green "all clear" is worth less than a red "3 bookings need reconciliation."

#### 4. Revenue by Property (Ring 3)
- status: open
- priority: medium
- suggested_entry_phase: 104–107
- notes: Property-level financial performance screen.
  - Gross revenue per property (period selectable)
  - OTA commission per property
  - Owner net per property
  - Booking count + average booking value
  - Lifecycle distribution per property
  - RevPAR (Revenue Per Available Room/Unit) — industry standard hospitality metric.
    Formula: `RevPAR = total_revenue / available_room_nights`.
    This is the metric that gives operators the clearest picture of property yield.
  - Trend direction (MoM, QoQ) if enough historical data
  No operations PMS should ship without RevPAR. It is the industry benchmark.

#### 5. Owner Statement Generator (Ring 4 — external-facing)
- status: open
- priority: medium-high
- suggested_entry_phase: 106–110
- design_reference: Guesty owner statements + Hostaway payout calendar
- notes: The most important owner-facing surface. Period-based (monthly / custom).
  Shows per owner:
  - Bookings included (list with check-in/out, OTA, gross, commission, net)
  - Total gross revenue (period)
  - Total OTA commissions deducted
  - Total management/operation fees (configurable %)
  - **Owner net for period** — the single most important number
  - Payout status per booking (released / pending / reconciliation_pending)
  - Statement total with running balance
  - PDF export (this is a key owner trust builder)
  Role-scoped: owner accounts see only their own properties.
  **This turns iHouse Core from an internal ops tool into an owner-facing product.**

#### 6. Payout Timeline / Cashflow View (Ring 3)
- status: open
- priority: medium
- suggested_entry_phase: 107–111
- design_reference: Stripe payout calendar + Xero cashflow
- notes: Time-oriented financial view. Not just totals — when does the money move.
  - Expected inflows by week/month (from OTA payout projections)
  - Released payouts (actual cash received, confirmed)
  - Delayed payouts (expected but overdue)
  - Provider-by-provider payout schedule
  - Forward projection: next 30/60/90 days of expected cash
  Key differentiator from competitors: because iHouse Core has lifecycle state,
  this view can show HONEST projections — not assumed ones.
  OTA_COLLECTING bookings are NOT projected as received.
  PAYOUT_RELEASED bookings ARE confirmed.
  No other PMS makes this distinction clearly.

#### 7. Reconciliation Inbox (Ring 3 — operator-facing)
- status: open
- priority: medium
- suggested_entry_phase: 108–112
- design_reference: Stripe disputes + Quickbooks unmatched items
- notes: Exception-first view. Shows only items that need attention.
  - Bookings with RECONCILIATION_PENDING status
  - Bookings with PARTIAL confidence financial facts
  - Bookings with missing `net_to_property` (detected financial drift)
  - Bookings where lifecycle_status is UNKNOWN
  - Provider-flagged mismatches (OTA state vs internal state)
  - Correction suggestions where the system can infer the likely fix
  Design principle: this inbox should be **empty on a good day**.
  If it is empty, the operator knows financials are clean.
  If it has items, they are always actionable.

#### 8. OTA Financial Health Comparison (Ring 3)
- status: open
- priority: low-medium
- suggested_entry_phase: 110–115
- notes: Cross-provider intelligence view.
  - Average commission rate per OTA (over a period)
  - Net-to-gross ratio per OTA
  - Average time-to-payout per OTA (if timestamps captured)
  - Lifecycle distribution per OTA (which OTAs have more RECONCILIATION_PENDING?)
  - Revenue share by OTA
  This helps operators make smarter channel management decisions.
  A channel with 25% commission and slow payouts is less valuable than it appears.

---

### Surfaces NOT to Build (Yet)

The following are deliberate exclusions to avoid premature complexity:

| Surface | Reason Not to Build Yet |
|---------|------------------------|
| Full accounting ledger / double-entry | Not a core PMS need. Use Xero/QBO export if needed. |
| Tax calculation engine | Jurisdiction-specific. Requires legal input. Out of scope. |
| Automated bank reconciliation | Requires bank API integrations. Different product scope. |
| Owner payment disbursement | Requires payment rails (Stripe Connect, etc.). Phase 200+. |
| Forecasting / ML revenue models | No training data yet. Premature. |

The financial layer should stay in its lane: **explain what the money IS doing**, not what it WILL do.
Forecasting can come later when historical fact density justifies it.

---

### Architecture Rules for This Layer

These must be preserved across all financial UI phases:

1. **Read-only surfaces only.** Financial UI reads `booking_financial_facts`. Never writes to booking_state.
2. **No financial logic in the UI layer.** All business logic lives in `payment_lifecycle.py`. UI consumes projections.
3. **Confidence is always visible.** Every financial figure must show its `source_confidence` (FULL / ESTIMATED / PARTIAL). Users must never assume a number is confirmed when it is derived.
4. **Lifecycle state is the source of truth.** No UI surface should compute payout status from raw fields. Always call `project_payment_lifecycle()`.
5. **Currency is always explicit.** Multi-currency is real (SGD, INR, THB, USD, EUR). Never aggregate across currencies without explicit conversion — or show per-currency figures separately.
6. **Owner surfaces are role-scoped.** Owners see their properties only. No cross-property leakage.

---

### Suggested Phase Entry Point

Based on the current roadmap and architecture maturity:

| Ring | Suggested Window | Prerequisite |
|------|-----------------|--------------|
| Ring 1 — Financial API | Phase 100–103 | 10+ providers stable ✅, payment lifecycle stable ✅ |
| Ring 2 — Per-booking widget | Phase 100–102 | Phase 93 output ✅ |
| Ring 3 — Portfolio views | Phase 103–112 | Ring 1 API complete |
| Ring 4 — Owner statements | Phase 106–112 | Ring 3 + role scoping |

**Do not rush Ring 4 before Ring 1 is solid.**
Owner statements need a reliable aggregation backend.
A bad owner statement destroys trust faster than no statement at all.

---

### Immediate Action (Now — Before Implementation)

Before any financial UI phase starts, one pre-step should happen:

**Ensure `booking_financial_facts` has the right indexing and RLS.**
Specifically:
- Index on `(tenant_id, provider, created_at)` for fast aggregation
- Index on `(tenant_id, booking_id)` for per-booking lookup
- RLS policy that scopes all reads to `tenant_id`
- Confirm `source_confidence` column exists (or add it)

This is a cheap Phase 99–100 DDL migration that prevents performance problems later.

---

*End of Financial UI direction. Reviewed and expanded from user note, Phase 96.*

---

## UI Architecture and Role-Based Product Surfaces

- status: open
- discovered_in: Phase 112 (recorded 2026-03-09)
- source_context: product direction — role-based operational platform
- priority: high
- notes: Full architecture vision recorded in `docs/core/planning/ui-architecture.md`. Summary below.

### Core Direction

iHouse Core should become a **set of role-based product surfaces** — not one giant dashboard.
Every surface should be built around the **7 AM rule**: someone wakes up, opens the dashboard,
and within two minutes understands the state of the business.

### Role Model

| Role | Authority |
|------|-----------|
| Admin | Full system control — settings, integrations, permissions, audit |
| Manager | Broad operational authority (~80%) — no system-owner powers by default |
| Manager + delegated permissions | Admin-granted trust extensions per manager |
| Worker | Action-first mobile surfaces — per role (Cleaner / Check-in / Maintenance) |
| Owner | Trust-based, financially clear — no operational noise |
| Guest | Pre-arrival and stay support *(long-term)* |

### Product Surfaces

| Surface | Purpose |
|---------|---------|
| Admin Web App | Governance, settings, integrations, audit, financial oversight |
| Manager Web App | Daily operational command center |
| Operations Dashboard | Live: arrivals, departures, cleanings, unacked tasks, today's risks |
| Worker Mobile | Per role — My tasks, ack, start, done, notes, photos |
| Owner Portal | Monthly statement, revenue, payout status, upcoming stays |
| Guest Portal | Pre-arrival info, check-in, house guide *(long-term)* |

### Dashboard Philosophy (Anti-patterns to avoid)

- No dashboard that tries to show everything on page one
- No managers with accidental system-owner powers
- No workers seeing admin complexity
- No owners seeing operational noise
- No charts for chart's sake on the first screen

### Permission-Aware UI

Two managers may not see the same controls. Admin controls delegation.
The UI must consume a permission manifest — not hardcode role assumptions.

### Financial UI Phasing

Financial UI should grow in layers (per Ring model in this doc), only when
supporting APIs and reconciliation confidence are stable.
Do not build before Phase 116 (Financial Aggregation API) is complete and stable.

### Suggested Entry Sequence

1. Build API layer first (Phase 113+ Task Query, Phase 116 Financial Aggregation)
2. Start with **Operations Dashboard** — clearest contract, highest daily value
3. Then **Manager Booking + Task views**
4. Then **Admin settings surfaces**
5. Then **Owner Portal**
6. Worker mobile last (needs stable task + notification stack)

> Full detail: `docs/core/planning/ui-architecture.md`

---

## Contextual Help Layer — UI/UX Product Quality

- status: open
- discovered_in: Phase 120 (user forward-planning note, 2026-03-09)
- source_context: product quality, UI/UX direction
- priority: medium — implement when UI phase opens, not before
- full_spec: `docs/future/contextual-help-layer.md`

### Summary

As iHouse Core grows more complex, the UI will eventually need a structured, layered help system.

**Core principle:** UI stays clean by default. Help appears only where it is genuinely needed.

**Four layers:**
1. Simple tooltip (1 line — labels, terminology, status chips)
2. Rich toggletip / popover (2–4 lines — financial logic, tiers, escalation)
3. Visible helper text (always visible — forms, destructive actions)
4. Global help toggle (user-controlled on/off, persisted per user)

**High-priority areas for help:** payment lifecycle, reconciliation, epistemic tiers A/B/C, RevPAR, owner statement confidence, escalation/SLA, financial status cards, conflict center, delegated permissions.

**Role-aware depth:** Admin → governance explanations. Manager → operational. Worker → short action-oriented. Owner → plain business language. Guest → minimal.

**Copy rule:** Short, specific, action-aware, not academic. Explain *meaning*, not labels.

**Implementation direction:** Define a help pattern library before adding help ad hoc. Treat the system as a real product capability, not random tooltips.

> Full detail: `docs/future/contextual-help-layer.md`

---

## API First Outbound Channel Sync

- status: open
- discovered_in: Phase 131 (user requirement, 2026-03-09)
- source_context: product requirement — close availability on all connected channels immediately after inbound booking accepted
- priority: high
- full_spec: `docs/core/planning/outbound-sync-layer.md`

### Summary

iHouse Core is inbound-complete but outbound-blind.

It knows the booking truth internally. It cannot yet propagate that truth to other
connected channels for the same property. Without outbound sync, overbooking is not
a risk we manage — it is a risk we accept. That is not acceptable for a serious
multi-channel property operations platform.

### Core Requirement

When a booking is accepted from any source:

1. Canonical ingest succeeds — `apply_envelope` returns APPLIED
2. Internal availability becomes occupied in `booking_state`
3. Outbound sync trigger fires (best-effort, non-blocking — identical pattern to `task_writer.py`)
4. Mapped connected channels for the same property receive availability lock updates
5. Success / failure / retry state is tracked in `channel_sync_log`
6. UI surfaces show sync health and exceptions

### Architecture Pattern

Wired into `service.py` after BOOKING_CREATED APPLIED — same hook point as
`task_writer` and `financial_writer`. Non-blocking. Never delays the canonical response.

Three new tables required:

- `property_channel_map` — maps `property_id` to external listing IDs per provider
- `channel_sync_log` — tracks every outbound sync attempt with retry state
- `provider_capability_registry` — declarative write capabilities per provider

### Provider Capability Tiers

| Tier | Providers | Write Path |
|------|-----------|-----------|
| **Tier A** | Booking.com, Expedia, Vrbo, Agoda, Airbnb | API-first (partner enrollment required) |
| **Tier B** | Google Vacation Rentals, Hotelbeds, MakeMyTrip | Partner/feed-gated |
| **Tier C** | Trip.com, Traveloka, Despegar | Verify write path before classifying |
| **Tier D** | Klook | Not a villa inventory target — disabled |
| **Fallback** | Any channel without write API | iCal (degraded mode, clearly surfaced in product) |

### iCal Policy (Locked)

iCal is **degraded mode only**. It is never the primary strategy.

If a channel is iCal-only, the product must surface this as lower-confidence sync.
Operators must be able to see which channels are protected by real-time API lock
and which are operating in fallback mode.

### Canonical Safety Rules

1. Outbound sync is always best-effort and non-blocking.
2. Outbound sync never writes to `booking_state` or `event_log`.
3. `apply_envelope` remains the only write authority for canonical booking state.
4. Every outbound attempt is auditable — no silent failures.
5. The source channel is never sent an outbound lock (it already knows).

### Phase Entry Points

| Stage | Phase Window | What |
|-------|-------------|------|
| Foundation | 135–137 | `property_channel_map`, `provider_capability_registry`, `channel_sync_log`, trigger hook |
| First writes | 139–143 | Booking.com, Expedia, Vrbo, Agoda, Airbnb writers |
| Fallback layer | 144 | iCal fallback writer |
| Health + retry | 145–148 | Retry engine, sync health dashboard, reconciliation tie-in |
| Broader coverage | 151–154 | Tier B + Tier C provider verification and writers |

> Full detail: `docs/core/planning/outbound-sync-layer.md`

---

## Product UI Layer — Backend/UI Rhythm

- status: open
- discovered_in: Phase 149 closure (2026-03-10)
- source_context: structural roadmap review — all-API imbalance identified
- priority: high
- full_spec: `docs/core/planning/phases-150-175.md`

### Summary

At Phase 149, the system has 3836 passing tests and covers full inbound + outbound sync,
financial APIs, task system, reconciliation, and owner statements.
All of it is invisible without Postman.

**Decision:** Introduce a Backend/UI/Backend/UI rhythm starting Phase 150.

### UI Stack

- Framework: Next.js 14 App Router
- Styling: Tailwind CSS
- Auth: existing Phase 61 JWT — no new auth layer
- Data: FastAPI only — never direct Supabase from UI

### Planned Surfaces (Phases 152–170)

| Phase | Surface | Audience |
|-------|---------|----------|
| 152 | Next.js scaffold + design system | — |
| 153 | Operations Dashboard | Admin, Manager |
| 157 | Worker Task Mobile View | Cleaner, Check-in, Maintenance |
| 158 | Manager Booking View | Manager |
| 163 | Financial Dashboard | Admin, Manager |
| 164 | Owner Statement View | Manager, Owner |
| 169 | Admin Settings UI | Admin |
| 170 | Owner Portal | Owner |

### Invariant

The UI never reads Supabase directly. All data flows through FastAPI.
Role scoping is enforced at the API layer, not the UI layer.

---

## Guest-Initiated Pre-Arrival Form

- status: deferred
- discovered_in: Item 9, active-fix stream (2026-04-04)
- source_context: guest experience / pre-arrival product planning
- priority: low-medium — not a current bug or missing build
- full_spec: `docs/future/guest-pre-arrival-form.md`

### Why it is deferred

The system is currently **iCal-first** in most real bookings. iCal provides booking timing,
property identity, and a partial booking reference — but it does not reliably provide
guest email, guest phone, or any trusted pre-arrival contact path.

Without guest identity confidence:
- we cannot know we have the right guest before issuing a link
- we have no reliable delivery path for the link
- any response cannot be confidently associated with the correct stay

This is not a gap in the implementation. It is a fundamental constraint of the iCal data model.

### Why it is still strategically important

- Pre-arrival data reduces check-in friction and operations load
- Enriches the guest dossier: arrival time, contact, guest count, preferences, documents
- Converts fragmented LINE/WhatsApp exchanges into structured, recorded intake
- Premium hospitality signal at the right moment before arrival

### What would make it viable

| Dependency | Why it unlocks this |
|---|---|
| OTA API access (Airbnb, Booking.com) | Verified guest email available at booking confirmation |
| OTA messaging integration | Existing message thread is a verified delivery path |
| Direct booking channel with identity | Verified email at booking creation |
| Manual invite after staff contact established | Staff can generate link once they have verified guest contact |

### Intended future model

When built:
- Structured field form (arrival time, guest count, document confirmation, preferences)
  — not free text, not a chat
- Strong stay-scoped token (same GUEST_PORTAL / GUEST_CHECKOUT model)
- Output flows into guest dossier and stay thread, visible to OM
- Idempotent — re-opening shows summary if already submitted
- Graceful expiry handling

### Possible interim path (not active)

A manual staff-generated invite flow — OM triggers "Send pre-arrival form" after
a verified contact path already exists (e.g. WhatsApp / LINE), delivers link manually,
guest fills in structured form, data flows into dossier. Does not solve the zero-contact
problem but converts manual exchanges into recorded structured intake.

**Not to be started unless explicitly requested.**

> Full detail: `docs/future/guest-pre-arrival-form.md`
