# Integrations

This folder is the operational source of truth for external integrations.

Each integration document should answer:
- what already exists
- what is already proven
- what is still missing
- what must be completed before production readiness

Use this folder to avoid guesswork, repeated setup confusion, and hidden configuration drift.

## Files

- `integration-status-matrix.md`
- `line-production-readiness.md`
- `telegram-production-readiness.md`
- `whatsapp-production-readiness.md`

## Rules

Do not call an integration fully connected unless:
- configuration is complete
- inbound flow is proven if relevant
- outbound flow is proven if relevant
- real end-to-end delivery is verified where applicable

Keep these documents updated whenever:
- credentials change
- webhook paths change
- routing logic changes
- production blockers are discovered or resolved
