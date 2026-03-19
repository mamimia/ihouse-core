# Integration Status Matrix

| Integration | Built | Configured | Inbound Proven | Outbound Proven | Production Ready | Notes |
|---|---|---|---|---|---|---|
| LINE | Yes | Yes | Yes | Yes | Partial | E2E proof completed 2026-03-20: real webhook receipt, real userId capture, real worker binding with notification_channels sync, real outbound message delivered. Remaining: dev tunnel (not final prod domain), manual worker binding (no auto-pairing yet). |
| Telegram | Yes | Yes | N/A | Yes | Partial | Telegram dispatch was proven, but production-readiness documentation should remain explicit and current. |
| WhatsApp | Not started / Partial | No | No | No | No | Define provider path and final integration model before calling this connected. |

Notes:
- "Inbound Proven" applies only when the integration depends on inbound callbacks/webhooks/events.
- "Outbound Proven" means a real message/notification was delivered successfully through the real provider.
- "Production Ready" requires all relevant proof, not only code completion.
