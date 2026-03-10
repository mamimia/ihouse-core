# Phase 196 — WhatsApp Escalation Channel

**Closed:** 2026-03-10  
**Type:** Escalation Channel  
**Risk:** Low  

## Goal

Add WhatsApp as a second escalation channel alongside LINE. Dominant messaging platform in Thailand/SEA property manager market. Follows exact same architecture — pure module, no source-of-truth role, in-app acknowledgement always first.

## Escalation Sequence

```
In-app notification → ACK SLA breached → LINE escalation
                                         ↕ LINE fails OR whatsapp_enabled
                                         WhatsApp escalation (2nd channel)
```

## Changes

### `src/channels/whatsapp_escalation.py` [NEW]
Pure module mirroring `line_escalation.py`:
- `WhatsAppEscalationRequest` frozen dataclass
- `WhatsAppDispatchResult` frozen dataclass (`sent`, `task_id`, `error`, `dry_run`)
- `should_escalate(result)` — ACK_SLA_BREACH only, COMPLETION_SLA_BREACH not triggered
- `build_whatsapp_message(task_row)` → `WhatsAppEscalationRequest`
- `format_whatsapp_text(task_row)` — WhatsApp-native `*bold*` formatting, no HTML
- `is_priority_eligible(task_row)` — HIGH/CRITICAL eligible only
- `verify_whatsapp_signature(payload_bytes, sig_header)` — HMAC-SHA256 via `IHOUSE_WHATSAPP_APP_SECRET`
- `dispatch_dry_run(request)` — returns `sent=False, dry_run=True` when token absent

### `src/api/whatsapp_router.py` [NEW]
- `GET /whatsapp/webhook` — Meta webhook challenge verification (`hub.verify_token` vs `IHOUSE_WHATSAPP_VERIFY_TOKEN`)
- `POST /whatsapp/webhook` — Inbound ack, HMAC-SHA256 sig check, ACK task_id extraction, PENDING→ACKNOWLEDGED transition (best-effort), 200 always after sig check

### `src/main.py` [MODIFY]
Registered: `from api.whatsapp_router import router as whatsapp_router`

### `src/channels/sla_dispatch_bridge.py` [MODIFY]
- `BridgeResult` extended with `whatsapp_attempted: bool`, `whatsapp_result: Optional[WhatsAppDispatchResult]`
- `_attempt_whatsapp_second_channel(action, primary_results, whatsapp_enabled)` — triggers when LINE fails (`sent=False`) or `whatsapp_enabled=True`, fail-isolated

## Env Vars (new)

| Var | Purpose |
|-----|---------|
| `IHOUSE_WHATSAPP_TOKEN` | Meta Cloud API bearer token |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business phone number ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | HMAC-SHA256 sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | Meta challenge verification token |

All absent → dry-run mode, never crash.

## Tests

**`tests/test_whatsapp_escalation_contract.py`** — 57 tests, Groups A–H:
- A (6): `should_escalate()` — ACK/COMPLETION/empty/multi
- B (9): `build_whatsapp_message()` — field mapping, frozen immutability
- C (9): `format_whatsapp_text()` — content, WhatsApp bold, no HTML
- D (7): `is_priority_eligible()` — HIGH/CRITICAL/LOW/MEDIUM
- E (6): dry-run mode — sent=False, dry_run=True, no exception
- F (6): HMAC signature verification — valid/invalid/missing/tampered
- G (8): Router endpoints — challenge GET, sig POST, 200/403
- H (6): `sla_dispatch_bridge` — second-channel trigger logic, BridgeResult fields

## Verification

```
57 passed in 0.54s   (whatsapp suite)
exit code 0          (full suite — pre-existing webhook failures unchanged)
```
