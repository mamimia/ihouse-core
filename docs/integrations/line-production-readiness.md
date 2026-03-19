# LINE Production Readiness

## Purpose

This note explains what is already prepared for LINE, what is still missing, and what must be completed before LINE is considered fully connected in production.

## Current truth

LINE is only partially complete.

What is already possible:
- create and configure the LINE Official Account
- enable Messaging API
- obtain Channel ID
- obtain Channel Secret
- obtain Channel Access Token
- prepare webhook route in the backend
- prepare outbound messaging logic
- prepare worker routing logic

What is not fully complete yet:
- permanent public HTTPS webhook setup
- permanent inbound webhook proof from LINE
- final end-to-end delivery proof to a real worker in production conditions

## Why this is blocked in local development

LINE requires a public HTTPS webhook URL.

A local development URL such as:
- localhost
- 127.0.0.1
- 192.168.x.x
- plain http

is not enough for real webhook delivery.

This means:
- local development can prepare the integration
- but real webhook proof requires a public HTTPS endpoint

## Temporary development workaround

A temporary HTTPS tunnel may be used for testing, such as:
- ngrok
- Cloudflare Tunnel

This is acceptable for testing only.
It is not the final production setup.

## Setup guide

### 1. Create or open the LINE Official Account
Go to LINE Official Account Manager.
Create the account if needed, or open the existing account you want to connect.

### 2. Enable Messaging API
In LINE Official Account Manager:
Settings -> Messaging API -> Enable Messaging API

If LINE asks you to choose a provider:
select the existing provider for the business.
Do not create a duplicate provider unless intentionally required.

### 3. Open LINE Developers Console
Go to:
Provider -> Channel -> Messaging API

### 4. Collect the required values
Collect:
- Channel ID
- Channel Secret
- Channel Access Token (long-lived)

Where to find them:
- Channel ID: Basic settings / Messaging API area
- Channel Secret: Basic settings / Messaging API area
- Channel Access Token: Messaging API -> Channel access token (long-lived) -> Issue

### 5. Set the webhook URL
Webhook path:
`/line/webhook`

The full URL must be public HTTPS, for example:
`https://your-public-api-domain.com/line/webhook`

Paste it into LINE Messaging API settings and enable webhook use.

### 6. Store values in Domaniqo correctly
Keep these values separated:

#### Channel Secret
Purpose:
verify inbound webhook signatures

Storage:
backend secret storage only

#### Channel Access Token
Purpose:
send outbound LINE messages

Storage:
integration settings / secure secret storage

#### Worker LINE user ID
Purpose:
route LINE messages to the intended worker

Storage:
worker profile / notification routing model

### 7. Configure worker routing
Each worker who should receive LINE notifications must have a valid LINE recipient identifier linked in the platform.

### 8. Test the connection
After configuration:
- verify webhook is enabled
- verify webhook URL is publicly reachable
- verify one real inbound webhook reaches the backend
- verify one real outbound message reaches a real worker

## Implementation truth to remember

- Channel Secret is not the same as Channel Access Token
- Public HTTPS is mandatory for real LINE webhook delivery
- Do not call LINE connected until both inbound and outbound proof exist
- If the Channel Secret was ever exposed during setup, rotate it and update backend secret storage

## Current recommended completion checklist

1. Final public HTTPS API domain available
2. Final webhook URL pasted into LINE
3. Webhook enabled
4. Channel Secret stored in backend secrets
5. Channel Access Token stored in integration settings
6. Worker routing verified end-to-end
7. Real inbound webhook proven
8. Real outbound delivery to a real worker proven

## Proof summary (2026-03-20)

The following were action-proven in a live test session:

1. **Inbound webhook action-proven** — LINE POST to `/line/webhook` received via ngrok tunnel, HTTP 200 returned
2. **source.userId captured** — `Ue6ef0a469d844632061fc0a3f04c7e2e` extracted from native LINE Messaging API event
3. **Worker binding action-proven** — userId bound to worker เเพรวา ตาลพันธ์ via PATCH `/permissions/{user_id}`
4. **notification_channels sync action-proven** — `_sync_channels()` automatically created `channel_type=line` row with correct `channel_id` matching the captured userId
5. **Outbound LINE message action-proven** — real push message delivered to the worker via LINE Messaging API (HTTP 200, sentMessages ID confirmed)

A real worker received a real LINE message sent by the Domaniqo system.

## Current limitations

These remain after proof:

- **Manual worker LINE user binding** — worker LINE userId is currently captured from webhook logs and manually entered into the staff profile. No automated pairing flow exists yet.
- **Dev tunnel, not final production domain** — webhook proof used a temporary ngrok tunnel. The final production webhook URL must be a permanent public HTTPS domain.
- **Token storage not encrypted at application level** — the LINE channel access token is stored in `tenant_integrations.credentials` (JSONB) and relies on Supabase RLS for access control, not application-layer encryption.
- **Channel Secret rotation pending** — the original Channel Secret was exposed during setup and should be rotated.

## Current status

- Built: yes
- Configured: yes
- Inbound proven: yes (action-proven 2026-03-20)
- Outbound proven: yes (action-proven 2026-03-20)
- Production ready: partial — proven for current tested flow, pending permanent domain and secret rotation
