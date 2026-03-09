"""
Phase 141 — Expedia / VRBO Outbound Adapter (Rate-Limit Enforcement)

Expedia and VRBO share the same Partner Solutions API (same credentials).

Credentials (from environment):
    EXPEDIA_API_KEY   / VRBO_API_KEY   — same key works for both
    EXPEDIA_API_BASE  / VRBO_API_BASE  — defaults to Expedia Partner Solutions

Availability block endpoint (simplified):
    POST /v1/properties/{external_id}/availability
    Body: { "status": "blocked", "booking_id": "<booking_id>" }

Rate limits: 60 requests/min.
"""
from __future__ import annotations

import logging
import os

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter, _throttle

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.expediapartnersolutions.com/v1"
_PROVIDER_MAP = {"expedia": "EXPEDIA", "vrbo": "EXPEDIA"}   # VRBO uses Expedia key


class ExpediaVrboAdapter(OutboundAdapter):
    """
    Outbound adapter for Expedia/VRBO Partner Solutions API (Tier A — api_first).
    provider argument selects the log label; both use EXPEDIA_API_KEY.
    """
    def __init__(self, provider: str = "expedia"):
        self.provider = provider   # type: ignore[assignment]

    def send(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 60,
        dry_run: bool = False,
    ) -> AdapterResult:
        env_prefix = _PROVIDER_MAP.get(self.provider, "EXPEDIA")
        api_key  = os.environ.get(f"{env_prefix}_API_KEY", "")
        base_url = os.environ.get(f"{env_prefix}_API_BASE", _DEFAULT_BASE)
        global_dry_run = os.environ.get("IHOUSE_DRY_RUN", "false").lower() == "true"

        if dry_run or global_dry_run or not api_key:
            reason = (
                "IHOUSE_DRY_RUN=true" if global_dry_run
                else f"{env_prefix}_API_KEY not configured — dry-run mode"
                if not api_key else "dry_run=True requested"
            )
            logger.info("[DRY-RUN] %s api_first: external_id=%s reason=%s",
                        self.provider, external_id, reason)
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="api_first", status="dry_run",
                http_status=None,
                message=f"[Phase 139 dry-run] {self.provider}: {reason}",
            )

        try:
            if httpx is None:  # pragma: no cover
                raise RuntimeError("httpx not available")
            url = f"{base_url}/properties/{external_id}/availability"
            payload = {"status": "blocked", "booking_id": booking_id}
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            }
            _throttle(rate_limit)
            resp = httpx.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code in (200, 201, 204):
                return AdapterResult(
                    provider=self.provider, external_id=external_id,
                    strategy="api_first", status="ok",
                    http_status=resp.status_code,
                    message=f"{self.provider} block sent. HTTP {resp.status_code}.",
                )
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="api_first", status="failed",
                http_status=resp.status_code,
                message=f"{self.provider} API error HTTP {resp.status_code}: {resp.text[:200]}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s adapter exception: %s", self.provider, exc)
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="api_first", status="failed",
                http_status=None,
                message=f"{self.provider} adapter exception: {exc}",
            )
