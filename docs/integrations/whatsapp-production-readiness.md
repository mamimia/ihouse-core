# WhatsApp Production Readiness

## Purpose

This note exists to define the future WhatsApp integration clearly before it becomes half-built or inconsistently documented.

## Current truth

WhatsApp is not yet fully connected.
Treat it as planned or partial unless and until the exact provider path is selected and proven.

## First decision required

Before implementation, decide which WhatsApp path will be used.

Examples:
- WhatsApp Business API provider
- Meta-hosted path
- third-party provider
- another approved messaging gateway

Do not start building UI assumptions before this provider decision is explicit.

## What must be defined before implementation

1. Provider choice
2. Credential model
3. Webhook model if applicable
4. Recipient routing model
5. Message template rules
6. Business verification requirements
7. Production limitations and rate constraints

## Required separation of values

Keep these distinct:
- provider credentials
- webhook verification secret if relevant
- recipient phone/routing value
- message template identifiers if required
- integration enable/disable state

## Production checklist

1. Choose final provider
2. Document exact webhook and credential model
3. Define where recipient routing lives
4. Build integration settings UI
5. Prove outbound delivery to a real target
6. Prove inbound webhook flow if required by provider
7. Document real operational limits and template requirements

## Current status

- Built: no / partial
- Configured: no
- Inbound proven: no
- Outbound proven: no
- Production ready: no

## Important reminder

Do not call WhatsApp “planned support” the same thing as “connected.”
Only call it connected once real provider, credentials, routing, and proof all exist.
