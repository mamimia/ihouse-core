# iHouse Core — Operator Runbook

Phase 481 — Production Operations Reference

## Quick Reference

| Action | Command/URL |
|--------|-------------|
| Health Check | `GET /health` |
| App Version | Check `version` in health response |
| Environment | Check `env` in health response |

## Daily Checks

1. **Health endpoint**: `GET /health` → `status: ok`
2. **DLQ count**: Check `checks.dlq.unprocessed_count` in health response
3. **Outbound sync probes**: Check `checks.outbound.providers` for failure rates

## Incident Response

### Supabase Unreachable (`status: unhealthy`)
1. Check Supabase dashboard for outages
2. Verify SUPABASE_URL and SUPABASE_KEY env vars
3. Check network connectivity from the container
4. If persistent: restart the API container

### High DLQ Count (`dlq.unprocessed_count > 5`)
1. `GET /dlq-inspector?limit=10` — inspect failed events
2. Check for OTA payload format changes
3. Replay fixable events via `POST /dlq-inspector/{id}/replay`
4. Purge unfixable events if confirmed stale

### Outbound Sync Degraded
1. Check `failure_rate_7d` per provider
2. Verify OTA API credentials are valid
3. Check rate limit headers from OTA APIs
4. Review outbound_sync_log for error patterns

### Rate Limit Exceeded (HTTP 429)
1. Check `checks.rate_limiter` in health endpoint
2. Default: 60 RPM per tenant
3. Adjust: set `IHOUSE_RATE_LIMIT_RPM` env var
4. Identify tenant causing excess traffic

## Environment Variables (Critical)

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service role key for admin operations |
| `IHOUSE_JWT_SECRET` | ✅ | JWT signing secret (≥32 chars) |
| `IHOUSE_ENV` | Recommended | `production` / `staging` / `development` |
| `IHOUSE_RATE_LIMIT_RPM` | Optional | Rate limit per tenant (default: 60) |
| `IHOUSE_DRY_RUN` | Optional | `true` to disable outbound syncs |

## Deployment

See `docs/deploy-quickstart.md` for Docker deployment instructions.
