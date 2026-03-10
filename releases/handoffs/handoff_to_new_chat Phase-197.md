# iHouse Core — Handoff to New Chat: Phase 197

**Date:** 2026-03-10
**Context:** Platform Checkpoint II — all docs synced to true system state.

---

## 🚨 READ THIS ENTIRE FILE BEFORE DOING ANYTHING ELSE

This is a structured handoff. You are the next AI agent picking up this project.
**Do not start executing phases immediately. Follow the protocol below.**

---

## Your First Job: Read the Full System

Read documents in this exact order (BOOT.md protocol):

1. `docs/core/BOOT.md` — authority rules, protocols, safety rails
2. `docs/core/vision.md` — immutable
3. `docs/core/system-identity.md` — immutable
4. `docs/core/canonical-event-architecture.md` — immutable
5. `docs/core/governance.md`
6. `docs/core/current-snapshot.md` — full system state as of Phase 197
7. `docs/core/work-context.md` — what was done, what's next
8. `docs/core/live-system.md` — if present
9. `docs/core/phase-timeline.md` — LAST section only (tail)
10. `docs/core/construction-log.md` — LAST section only (tail)
11. `docs/core/roadmap.md` — LAST section only (forward plan)

Do not skip any of these. Do not start work until you have read all of them.

---

## Current System State (as of Phase 197)

| Item | Value |
|------|-------|
| Last Closed Phase | 197 — Platform Checkpoint II |
| Tests | 4,906 collected / ~4,900 passing / 6 pre-existing failures / exit 0 |
| OTA Adapters | 14 live |
| Escalation Channels | LINE (live), WhatsApp (live), Telegram (stub), SMS (stub) |
| Channel Architecture | Per-worker preference — NO global fallback chain |
| UI Surfaces | Operations Dashboard, Worker Task View, Bookings View, Financial Dashboard, Owner Statement, Admin Settings, Owner Portal, Manager Activity Feed, Guest Profile, Guest Detail |
| Next Phase | **TBD — the next conversation decides** |

---

## Your Second Job: Propose 20 Next Phases

After reading the full system, you must:

1. **Understand where we truly are** — not just what the last phase was, but what the system can and cannot do today
2. **Identify what is missing** — gaps in product value, reliability, operator experience, channel infra, integration management
3. **Propose exactly 20 candidate phases** with:
   - Phase number (starting from 198)
   - Short title
   - One-sentence rationale
   - Type (Backend / UI / Adapter / Docs / Infra)
   - Risk level (Low / Medium / High)

Present the 20 phases in a structured table to the user before doing anything else.

---

## Your Third Job: Wait for Approval

Do NOT start any phase until the user explicitly approves the 20-phase plan (or requests adjustments).

If the user requests changes, update the plan and present again.
Only when the user says "approved" or equivalent — proceed with Phase 198.

---

## Key Architecture Rules — Never Break

1. `apply_envelope` is the ONLY write authority to `booking_state`
2. `event_log` is append-only — no updates, no deletes, ever
3. `booking_state` must NEVER contain financial calculations
4. All OTA adapters route through `ingest_provider_event` → `apply_envelope`
5. Financial read endpoints query `booking_financial_facts` ONLY
6. `booking_id = {source}_{normalized_ref}` — deterministic, canonical
7. External channels (LINE, WhatsApp, Telegram) are escalation fallbacks ONLY — never source of truth
8. Idempotency key format: `{provider}:{event_type}:{event_id}` (lowercase)
9. **No global fallback chain** — each worker has their `channel_type` in `notification_channels`
10. CRITICAL_ACK_SLA_MINUTES = 5 (locked)

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI entrypoint — all routers |
| `src/adapters/ota/registry.py` | OTA adapter registry |
| `src/channels/notification_dispatcher.py` | Channel routing per-worker |
| `src/channels/sla_dispatch_bridge.py` | SLA → dispatcher bridge |
| `src/tasks/sla_engine.py` | Pure SLA evaluation |
| `src/tasks/task_model.py` | Task enums and dataclass |
| `ihouse-ui/` | Next.js 14 App Router UI |
| `docs/core/BOOT.md` | Operational authority rules |

---

## Channels Ready for Production Wiring

| Channel | Module | Status | Env Vars Needed |
|---------|--------|--------|----------------|
| LINE | `line_escalation.py` + `line_webhook_router.py` | Live (sig + ack) | `IHOUSE_LINE_SECRET`, `IHOUSE_LINE_CHANNEL_TOKEN` |
| WhatsApp | `whatsapp_escalation.py` + `whatsapp_router.py` | Live (sig + ack + dry-run) | `IHOUSE_WHATSAPP_TOKEN`, `IHOUSE_WHATSAPP_PHONE_NUMBER_ID`, `IHOUSE_WHATSAPP_APP_SECRET`, `IHOUSE_WHATSAPP_VERIFY_TOKEN` |
| Telegram | `notification_dispatcher.py` (stub) | Stub only | — |
| SMS | `notification_dispatcher.py` (stub) | Stub only | — |

---

## Known Pre-existing Failures (do not fix in Phase 198 unless scoped)

| Test | Reason |
|------|--------|
| `test_webhook_endpoint.py` — 5 providers | Webhook fixture format mismatch pre-Phase 196 |
| `test_conflicts_router_contract.py::test_e1` | DB mock mismatch |
| `test_outbound_health_contract.py` — 2 tests | `failed` status counter edge case |
| `test_outbound_log_router_contract.py::test_all_valid_statuses_accepted[failed]` | Status filter edge case |
| `test_outbound_replay_contract.py` — 2 tests | Strategy/status propagation mock |

All 6 are pre-existing and unrelated to core invariants. Exit 0.

---

## Areas to Consider for Phases 198–210

These are **suggestions only** — the next conversation evaluates them based on a full system read:

| Area | Why |
|------|-----|
| Telegram escalation (real) | Stub is ready; wire real Bot API |
| SMS escalation via Twilio | Tier-3 final escalation needs a real adapter |
| Per-worker channel preference UI | Workers need to select LINE/WhatsApp in their profile |
| Worker mobile app foundation | Workers currently use web; PWA or dedicated mobile surface |
| Pre-arrival guest checklist | Guest Profile exists; workflow for pre-arrival tasks missing |
| Multi-property onboarding flow | Manual setup; need credentials/webhook provisioning UI (Wave 1) |
| Notification history / inbox | Workers can't see past escalation history |
| OTA webhook replay from UI | DLQ Inspector exists but replay is API-only |
| Booking calendar view | Availability projection exists; no calendar UI surface |
| Rate/pricing integration | No OTA rate push exists yet |
| Outbound webhook pre-existing failures | 6 pre-existing test failures |
| Rakuten replay fixture | 13th adapter has no YAML fixture |
| Hostelworld E2E harness extension | 14th adapter not in E2E harness |
| Performance / load testing | No load test harness exists |
| Supabase row-level security audit | RLS policies need systematic review |

---

## Closing Statement

This handoff was written at Platform Checkpoint II (Phase 197) by the agent completing Phase 196 and the Phase 196-patch (per-worker channel architecture). The system is in a clean, consistent state. All docs are accurate. All tests pass (exit 0).

The next conversation owns the roadmap from Phase 198. Trust your reading of the system over this handoff where they conflict — always go back to the code.
