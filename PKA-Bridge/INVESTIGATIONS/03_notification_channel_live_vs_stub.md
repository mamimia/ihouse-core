# Title

WhatsApp, FCM, Email, and SMS Notifications Are Stubs That Silently Report Success

# Why this matters

The notification dispatch system is a core operational reliability mechanism. SLA escalations, urgent problem alerts, task assignments, and worker communications all flow through it. If four of the six notification channels silently claim to deliver while doing nothing, any worker registered under those channels receives no notifications. This is not a visible error — the system logs a success. No operator, no monitoring dashboard, and no worker will know delivery failed. The operational impact is that workers may miss urgent task assignments or SLA alerts, and the system will show no sign of the failure.

# Original claim

LINE and Telegram are the only clearly live notification channels. Other channels (WhatsApp, FCM, Email, SMS) are partial, stubbed, or not fully proven.

# Final verdict

PROVEN

# Executive summary

Two channels make real HTTP calls: LINE (to `api.line.me`) and Telegram (to `api.telegram.org`). Both fetch live credentials from `tenant_integrations` and check HTTP response codes. The other four channels — WhatsApp, FCM, Email, SMS — are stubs. They contain no HTTP calls. They log a message and return `ChannelAttempt(success=True)`. This means the dispatch system will report successful delivery for any worker registered under WhatsApp, FCM, Email, or SMS, while no message is actually sent. The WhatsApp stub has a comment describing a real Facebook Graph API call — but that call is only in a comment, not in code.

# Exact repository evidence

- `src/channels/notification_dispatcher.py` — all six channel adapter functions
  - Lines 134–190: `_default_line_adapter` — live HTTP call
  - Lines 245–294: `_default_telegram_adapter` — live HTTP call
  - Lines 223–242: `_default_whatsapp_adapter` — stub, returns `success=True`
  - Lines 193–205: `_default_fcm_adapter` — stub, returns `success=True`
  - Lines 208–220: `_default_email_adapter` — stub, returns `success=True`
  - Lines 297–314: `_default_sms_adapter` — stub, returns `success=True`
- `src/channels/notification_dispatcher.py` lines 461–511 — `dispatch_notification()` — core dispatcher
- `src/channels/sla_dispatch_bridge.py` — SLA escalation bridge (calls `dispatch_notification`)
- `src/tasks/sla_trigger.py` — periodic SLA batch sweep (triggers escalations)

# Detailed evidence

**LINE adapter — LIVE:**
```python
def _default_line_adapter(channel_id, message, db=None, tenant_id=""):
    """LINE Messaging API adapter (Phase 845)."""
    import httpx
    # Fetches channel_access_token from tenant_integrations
    res = db.table("tenant_integrations").select("credentials, is_active")
            .eq("tenant_id", tenant_id).eq("provider", "line").execute()
    rows = res.data or []
    if not rows or not rows[0].get("is_active"):
        return ChannelAttempt(..., success=False, error="LINE integration not active")
    channel_access_token = rows[0].get("credentials", {}).get("channel_access_token")
    ...
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {channel_access_token}"}
    resp = httpx.post(url, headers=headers, json=payload, timeout=5.0)
    if resp.status_code == 200:
        return ChannelAttempt(..., success=True)
    else:
        err = f"HTTP {resp.status_code}: {resp.text}"
        return ChannelAttempt(..., success=False, error=err)
```
The LINE adapter:
- Checks whether the tenant has an active LINE integration
- Fetches a real credential (channel_access_token) from the DB
- Makes a real HTTPS POST to the LINE Messaging API
- Inspects the HTTP response code
- Returns failure correctly on non-200 responses

**Telegram adapter — LIVE:**
```python
def _default_telegram_adapter(channel_id, message, db=None, tenant_id=""):
    """Telegram Bot API adapter (Phase 842)."""
    import httpx
    # Fetches bot_token from tenant_integrations
    ...
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = httpx.post(url, json=payload, timeout=5.0)
    if resp.status_code == 200:
        return ChannelAttempt(..., success=True)
    else:
        err = f"HTTP {resp.status_code}: {resp.text}"
        return ChannelAttempt(..., success=False, error=err)
```
Same pattern as LINE. Real credential fetch, real HTTP call, HTTP response inspection.

**WhatsApp adapter — STUB:**
```python
def _default_whatsapp_adapter(channel_id, message, db=None, tenant_id=""):
    """
    WhatsApp Cloud API adapter stub (Phase 196).
    In production: HTTP POST to graph.facebook.com/v19.0/{phone_number_id}/messages
    with Authorization: Bearer {IHOUSE_WHATSAPP_TOKEN}.
    Stub returns success=True; tests inject mocks via `adapters` parameter.
    """
    text = f"{message.title}\n{message.body}"
    logger.info("WhatsApp dispatch to number=%s text_len=%d", channel_id, len(text))
    return ChannelAttempt(channel_type=CHANNEL_WHATSAPP, channel_id=channel_id, success=True)
```
No HTTP call. No credential fetch. No response inspection. Always returns `success=True`. The Facebook Graph API URL is documented in a comment but never called.

**FCM adapter — STUB:**
```python
def _default_fcm_adapter(channel_id, message, db=None, tenant_id=""):
    """FCM stub — reserved for Phase 168+ wiring."""
    logger.info("FCM dispatch to token=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_FCM, channel_id=channel_id, success=True)
```
No implementation. One log line. Always returns `success=True`.

**Email adapter — STUB:**
```python
def _default_email_adapter(channel_id, message, db=None, tenant_id=""):
    """Email stub — reserved for Phase 168+ wiring."""
    logger.info("Email dispatch to=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_EMAIL, channel_id=channel_id, success=True)
```
No implementation. One log line. Always returns `success=True`.

**SMS adapter — STUB:**
```python
def _default_sms_adapter(channel_id, message, db=None, tenant_id=""):
    """SMS adapter stub — tier-2 last-resort escalation (future phase)."""
    logger.info("SMS dispatch to number=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_SMS, channel_id=channel_id, success=True)
```
No implementation. One log line. Always returns `success=True`.

**The dispatch core — how `success=True` from stubs propagates:**
```python
def dispatch_notification(db, tenant_id, user_id, message, adapters=None):
    effective_adapters = adapters if adapters is not None else _DEFAULT_ADAPTERS
    channels = _lookup_channels(db, tenant_id, user_id)
    ...
    for ch_type in _CHANNEL_PRIORITY:
        ch_id = channel_map.get(ch_type)
        if ch_id is None:
            continue
        attempt = adapter(ch_id, message, db, tenant_id)
        attempts.append(attempt)
    sent = any(a.success for a in attempts)
    return DispatchResult(sent=sent, user_id=user_id, channels=attempts)
```
If a worker has `channel_type="whatsapp"` in `notification_channels`, the WhatsApp stub is called. It returns `success=True`. The `sent = any(a.success ...)` check passes. `DispatchResult.sent=True` is returned. The SLA bridge and caller receive a clean "delivered" signal. No error is raised, no warning is logged at the dispatch level, and no retry is triggered.

**Module-level comment contradicts reality:**
```
Per-worker channel preference:
    Worker A → channel_type="line"      → LINE only
    Worker B → channel_type="whatsapp"  → WhatsApp only
    Worker C → channel_type="telegram"  → Telegram only (future)
    Worker D → channel_type="sms"       → SMS only (tier-2 escalation)
```
The module comment at lines 20–25 presents all four channel types as equivalent and viable. "WhatsApp only" implies WhatsApp works. "Telegram only (future)" correctly signals Telegram's deferred state — but Telegram is actually live (Phase 842), making the "(future)" label wrong. The comment does not indicate WhatsApp is a stub.

**Dry-run paths in live adapters — a secondary concern:**
Both the LINE and Telegram adapters have dry-run paths:
```python
if db is None or not tenant_id:
    logger.warning("LINE dispatch dry-run for channel_id=%s (no db)", channel_id)
    return ChannelAttempt(..., success=True)
```
If these adapters are called without a DB client (e.g., from a test or a misconfigured call path), they return `success=True` without making any HTTP call — silently, the same as the stubs. This is a separate reliability concern: LINE and Telegram can also silently not deliver if called without proper DB context.

# Contradictions

- Module comment (line 22) lists WhatsApp as an active per-worker channel. Implementation shows it is a stub with no HTTP call.
- Module comment (line 23) marks Telegram as "(future)". Telegram was implemented in Phase 842 — it makes real HTTP calls. The comment is outdated.
- `_CHANNEL_PRIORITY` list treats LINE, WhatsApp, and Telegram as equivalent tier-1 channels. They are not equivalent at runtime: only two of the three make real HTTP calls.
- WhatsApp stub docstring says "tests inject mocks via `adapters` parameter" — this is accurate for test coverage, but does not communicate to an operator that production WhatsApp dispatch is also a mock.
- The stub adapters return `success=True`, meaning `DispatchResult.sent=True` propagates upward as a false delivery confirmation. Any monitoring, audit logging, or retry logic that uses `DispatchResult.sent` as a signal will be misled.

# What is confirmed

- LINE adapter makes a real HTTPS POST to `api.line.me/v2/bot/message/push` using DB-fetched credentials.
- Telegram adapter makes a real HTTPS POST to `api.telegram.org/bot{token}/sendMessage` using DB-fetched credentials.
- WhatsApp adapter contains zero HTTP calls and always returns `success=True`.
- FCM adapter contains zero HTTP calls and always returns `success=True`.
- Email adapter contains zero HTTP calls and always returns `success=True`.
- SMS adapter contains zero HTTP calls and always returns `success=True`.
- The dispatcher's `sent` field is derived from `any(a.success for a in attempts)` — meaning stub adapters produce false-positive delivery confirmations.

# What is not confirmed

- Whether any real workers currently have `channel_type="whatsapp"`, `"fcm"`, `"email"`, or `"sms"` registered in the `notification_channels` table. If no workers use stub channels, the impact is theoretical.
- Whether there is a separate integration path for WhatsApp (e.g., an inbound webhook or a different sender module not in `notification_dispatcher.py`) that operates independently.
- Whether the SLA dispatch bridge or any caller checks `DispatchResult.sent` for alarm conditions. If callers treat `sent=False` as an alert condition and `sent=True` as clean, stubs are silently problematic. If callers do not use this signal, the immediate impact is limited.
- Whether the admin UI (`/admin` integrations page) exposes the WhatsApp token configuration. If it does, operators may believe they can configure WhatsApp and have it work, when the adapter ignores any configured token.

# Practical interpretation

Today, in production:
- Workers registered with LINE receive real notifications.
- Workers registered with Telegram receive real notifications.
- Workers registered with WhatsApp, FCM, Email, or SMS receive nothing — silently.

This matters most for SLA escalations. If a CRITICAL task is assigned to a worker who has `channel_type="whatsapp"`, the SLA engine will dispatch, receive `sent=True`, and log the escalation as delivered. The worker receives nothing. The 5-minute SLA clock continues. No retry fires. The task remains unacknowledged.

The operational safe state is: all workers in production must be registered under LINE or Telegram. Any worker registered under another channel type is in a silent non-delivery state.

# Risk if misunderstood

**If notification channels are assumed all live:** Workers are onboarded with WhatsApp or FCM channels, SLA escalations are assumed delivered, and workers miss critical assignments with no operational visibility into the failure.

**If LINE/Telegram assumed only for "advanced" users:** Developers may deprioritize completing stub channels assuming basic workers use simpler channels (SMS, email) — but those simpler channels don't work at all.

**If the stub `success=True` pattern is copied to new channel adapters:** Future adapters may inherit the pattern of returning success before real wiring is complete, expanding the silent failure surface.

# Recommended follow-up check

1. Query the `notification_channels` table for any rows where `channel_type` is `whatsapp`, `fcm`, `email`, or `sms`. Count how many workers are registered under stub channels.
2. Check whether `src/channels/sla_dispatch_bridge.py` or any caller acts on `DispatchResult.sent=False` as an alert condition.
3. Read `ihouse-ui/app/(app)/admin/page.tsx` fully to confirm whether the WhatsApp token configuration UI is exposed to operators (and thus creates a false expectation of WhatsApp functionality).
4. Verify whether `IHOUSE_WHATSAPP_TOKEN` is documented as an expected environment variable in any `.env.example` or deployment guide — if so, operators may believe it is wired.
