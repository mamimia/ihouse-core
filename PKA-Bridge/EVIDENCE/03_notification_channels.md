# Claim

LINE and Telegram are the only clearly live notification channels. Other channels (WhatsApp, FCM, Email, SMS) are partial, stubbed, or not fully proven.

# Verdict

PROVEN

# Why this verdict

Direct reading of `src/channels/notification_dispatcher.py` shows two adapters that make real HTTP calls (`api.line.me` for LINE, `api.telegram.org` for Telegram). The remaining four adapters — WhatsApp, FCM, Email, SMS — contain no HTTP calls. They log a message and immediately return `ChannelAttempt(success=True)`. WhatsApp's docstring explicitly states "Stub returns success=True; tests inject mocks." FCM and Email are labeled "reserved for Phase 168+ wiring." SMS is labeled "tier-2 last-resort… future phase."

# Direct repository evidence

- `src/channels/notification_dispatcher.py` — all six channel adapter implementations
- Lines 134–190 — `_default_line_adapter`: fetches `channel_access_token` from `tenant_integrations`, calls `https://api.line.me/v2/bot/message/push` via `httpx.post`
- Lines 245–294 — `_default_telegram_adapter`: fetches `bot_token` from `tenant_integrations`, calls `https://api.telegram.org/bot{token}/sendMessage` via `httpx.post`
- Lines 223–242 — `_default_whatsapp_adapter`: logs to stdout, returns `ChannelAttempt(success=True)` with no HTTP call
- Lines 193–205 — `_default_fcm_adapter`: logs "FCM dispatch (stub)", returns `ChannelAttempt(success=True)`
- Lines 208–220 — `_default_email_adapter`: logs "Email dispatch (stub)", returns `ChannelAttempt(success=True)`
- Lines 297–314 — `_default_sms_adapter`: logs "SMS dispatch (stub)", returns `ChannelAttempt(success=True)`

# Evidence details

**LINE adapter (LIVE):**
```python
url = "https://api.line.me/v2/bot/message/push"
headers = {"Authorization": f"Bearer {channel_access_token}"}
resp = httpx.post(url, headers=headers, json=payload, timeout=5.0)
if resp.status_code == 200:
    return ChannelAttempt(..., success=True)
else:
    err = f"HTTP {resp.status_code}: {resp.text}"
    return ChannelAttempt(..., success=False, error=err)
```
Fetches live credentials from DB, inspects HTTP response code. This is a real integration.

**Telegram adapter (LIVE):**
```python
url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
resp = httpx.post(url, json=payload, timeout=5.0)
if resp.status_code == 200:
    return ChannelAttempt(..., success=True)
```
Same pattern — live DB credential fetch, real HTTP call, HTTP response checking.

**WhatsApp adapter (STUB):**
```python
def _default_whatsapp_adapter(...):
    """
    WhatsApp Cloud API adapter stub (Phase 196).
    In production: HTTP POST to graph.facebook.com/v19.0/{phone_number_id}/messages
    Stub returns success=True; tests inject mocks via `adapters` parameter.
    """
    text = f"{message.title}\n{message.body}"
    logger.info("WhatsApp dispatch to number=%s text_len=%d", channel_id, len(text))
    return ChannelAttempt(channel_type=CHANNEL_WHATSAPP, channel_id=channel_id, success=True)
```
No HTTP call. Always returns `success=True`. The Facebook API URL appears only in a comment.

**FCM adapter (STUB):**
```python
def _default_fcm_adapter(...):
    """FCM stub — reserved for Phase 168+ wiring."""
    logger.info("FCM dispatch to token=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_FCM, channel_id=channel_id, success=True)
```

**Email adapter (STUB):**
```python
def _default_email_adapter(...):
    """Email stub — reserved for Phase 168+ wiring."""
    logger.info("Email dispatch to=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_EMAIL, channel_id=channel_id, success=True)
```

**SMS adapter (STUB):**
```python
def _default_sms_adapter(...):
    """SMS adapter stub — tier-2 last-resort escalation (future phase)."""
    logger.info("SMS dispatch to number=%s (stub)", channel_id)
    return ChannelAttempt(channel_type=CHANNEL_SMS, channel_id=channel_id, success=True)
```

**Important nuance — stub adapters report success=True:**
All four stub adapters return `success=True`. This means that if a worker has their `notification_channels` row set to `channel_type="whatsapp"`, the dispatcher will:
1. Look up the channel
2. Call `_default_whatsapp_adapter`
3. Return `DispatchResult(sent=True, ...)`
4. Log the dispatch as successful

No error or warning will surface. The system will believe the notification was delivered when it was not. This is a silent delivery failure, not a visible error.

**Adapter injection pattern (for testing):**
```python
def dispatch_notification(..., adapters: Optional[dict[...]] = None) -> DispatchResult:
    effective_adapters = adapters if adapters is not None else _DEFAULT_ADAPTERS
```
The dispatcher is testable with mock adapters, which is good design — but the default adapters in production are the stubs above for WhatsApp, FCM, Email, and SMS.

# Conflicts or contradictions

- The module comment at line 22 lists WhatsApp as an active per-worker channel: "Worker B → channel_type='whatsapp' → WhatsApp only." This implies WhatsApp is intended to work, and the comment does not indicate it is a stub. However, the implementation directly contradicts this: the WhatsApp adapter is a stub.
- The `_CHANNEL_PRIORITY` list (lines 71–75) treats LINE, WhatsApp, and Telegram as equivalent "preferred external" tier-1 channels. At runtime they are not equivalent — only LINE and Telegram make real HTTP calls.
- The stub adapters return `success=True`, which creates false telemetry in `DispatchResult`. Any logging, audit, or monitoring that relies on `DispatchResult.sent` will incorrectly indicate WhatsApp, FCM, Email, and SMS notifications are being delivered.

# What is still missing

- Whether any tenant currently has workers registered with `channel_type="whatsapp"` in the `notification_channels` table. If so, those workers are silently not receiving notifications.
- Whether there is a separate integration router or webhook handler that processes inbound WhatsApp messages independently of `notification_dispatcher.py`.
- Whether LINE dry-run mode (lines 150–152) — which also returns `success=True` without a real HTTP call — is triggered when `db=None`. The dry-run path appears to be a test safeguard, but its conditions (`db is None or not tenant_id`) could theoretically be reached in unexpected call paths.
- Whether Telegram's dry-run path (lines 267–269) carries the same risk.

# Risk if misunderstood

If a product decision assumes WhatsApp, FCM, Email, or SMS notifications are live and reliable, operational workflows will fail silently. A cleaner or check-in agent registered under a stub channel will never receive task notifications or SLA alerts. The `DispatchResult.sent=True` return from stub adapters means no error surface exists at the dispatch layer — the failure is invisible.

Conversely, if someone concludes "notifications are broken" without reading the code, they will miss that LINE and Telegram are genuinely live and functional for any worker with those channels registered.
