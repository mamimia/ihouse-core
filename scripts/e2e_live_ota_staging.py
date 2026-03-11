#!/usr/bin/env python3
"""
Phase 281 — First Live OTA Integration Test
============================================
Live staging end-to-end runner.

Simulates a real Booking.com webhook arriving at the iHouse Core API,
passing through the full stack:

  HTTP POST  →  HMAC signature verify  →  JWT auth (dev mode)
            →  payload normalize       →  apply_envelope RPC
            →  event_log INSERT        →  verify row in Supabase

Usage (local, with API running):
    SUPABASE_URL=... SUPABASE_KEY=... IHOUSE_WEBHOOK_SECRET_BOOKINGCOM=... \\
    IHOUSE_DEV_MODE=true \\
    python3 scripts/e2e_live_ota_staging.py --base-url http://localhost:8000

Usage (dry-run, no live Supabase):
    python3 scripts/e2e_live_ota_staging.py --dry-run

Exit code:
    0 — all checks passed
    1 — any check failed

Requirements:
    - API must be running at BASE_URL
    - IHOUSE_WEBHOOK_SECRET_BOOKINGCOM must be set (or --dry-run)
    - SUPABASE_URL + SUPABASE_KEY must be set for Supabase verification
      (or --dry-run skips verification)

Phase 281 goal: process one real OTA webhook end-to-end through the
full production stack without mocking any layer.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

try:
    import urllib.request
    import urllib.error
except ImportError:
    print("ERROR: urllib not available", file=sys.stderr)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Canonical Booking.com test payload
# ─────────────────────────────────────────────────────────────────────────────

def _build_bookingcom_payload(run_id: str) -> dict:
    """
    Builds a minimal Booking.com reservation_created payload.
    This is the format booking.com sends to the webhook endpoint.
    run_id ensures each run's booking_id is unique.
    """
    return {
        "reservation_id": f"LIVE281-{run_id}",
        "property_id": "PROP-STAGING-001",
        "tenant_id": "staging-tenant-001",
        "event_type": "reservation_created",
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "check_in": "2026-12-01",
        "check_out": "2026-12-05",
        "guest_name": "Phase 281 Test Guest",
        "total_price": "1500.00",
        "currency": "THB",
        "num_guests": 2,
        "source": "bookingcom",
    }


def _compute_hmac(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ─────────────────────────────────────────────────────────────────────────────
# Live HTTP test
# ─────────────────────────────────────────────────────────────────────────────

def run_live_test(base_url: str, dry_run: bool) -> bool:
    run_id = uuid.uuid4().hex[:8]
    secret = os.environ.get("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", "")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    print(f"\n{'='*60}")
    print(f"iHouse Core — Phase 281 Live OTA Integration Test")
    print(f"{'='*60}")
    print(f"  Run ID:      {run_id}")
    print(f"  Base URL:    {base_url}")
    print(f"  Dry-run:     {dry_run}")
    print(f"  HMAC secret: {'SET' if secret else 'NOT SET'}")
    print(f"  Supabase:    {'SET' if supabase_url else 'NOT SET'}")
    print()

    # ─── Step 1: Build payload ─────────────────────────────────────────────
    payload = _build_bookingcom_payload(run_id)
    body = json.dumps(payload).encode("utf-8")
    print(f"[1/4] Payload built: reservation_id={payload['reservation_id']}")

    # ─── Step 2: Compute HMAC ─────────────────────────────────────────────
    if not secret:
        if dry_run:
            sig = "sha256=dryrundummysignature"
            print(f"[2/4] HMAC: DRY-RUN (no secret set, signature is placeholder)")
        else:
            print("ERROR: IHOUSE_WEBHOOK_SECRET_BOOKINGCOM not set. Use --dry-run or set the secret.")
            return False
    else:
        sig = _compute_hmac(secret, body)
        print(f"[2/4] HMAC computed: {sig[:30]}...")

    # ─── Step 3: POST to webhook endpoint ─────────────────────────────────
    url = f"{base_url.rstrip('/')}/webhooks/bookingcom"
    headers = {
        "Content-Type": "application/json",
        "X-Booking-Signature": sig,
        "X-Phase281-RunId": run_id,
    }

    if dry_run:
        print(f"[3/4] DRY-RUN: would POST to {url}")
        print(f"      Headers: {list(headers.keys())}")
        print(f"      Body size: {len(body)} bytes")
        print(f"[4/4] DRY-RUN: Supabase verification skipped")
        print()
        print("DRY-RUN completed. Ready for live test when API is running.")
        return True

    print(f"[3/4] POSTing to {url}...")
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            response_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status = e.code
        response_body = e.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"ERROR: HTTP request failed: {e}")
        return False

    try:
        parsed = json.loads(response_body)
    except Exception:
        parsed = {"raw": response_body}

    print(f"      Status: {status}")
    print(f"      Response: {json.dumps(parsed, indent=2)}")

    if status != 200:
        print(f"FAIL: Expected 200, got {status}")
        return False

    idempotency_key = parsed.get("idempotency_key", "")
    print(f"      Idempotency key: {idempotency_key}")
    print(f"[3/4] OK — webhook accepted by API ✅")

    # ─── Step 4: Verify event_log row in Supabase ─────────────────────────
    if not supabase_url or not supabase_key:
        print(f"[4/4] SKIP — SUPABASE_URL/KEY not set, skipping DB verification")
        print()
        print("Result: PARTIAL PASS — API accepted, DB not verified")
        return True

    print(f"[4/4] Verifying event_log row in Supabase...")
    time.sleep(1)  # Brief wait for apply_envelope to complete

    query_url = f"{supabase_url}/rest/v1/event_log?payload_json->>reservation_id=eq.LIVE281-{run_id}&select=event_id,kind,occurred_at"
    query_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    try:
        req = urllib.request.Request(query_url, headers=query_headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"ERROR: Supabase query failed: {e}")
        return False

    if not rows:
        print(f"FAIL: No event_log row found for reservation_id=LIVE281-{run_id}")
        return False

    row = rows[0]
    print(f"      event_id: {row.get('event_id')}")
    print(f"      kind: {row.get('kind')}")
    print(f"      occurred_at: {row.get('occurred_at')}")
    print(f"[4/4] OK — event_log row verified in Supabase ✅")

    print()
    print(f"{'='*60}")
    print(f"Phase 281 PASS — Full end-to-end flow verified ✅")
    print(f"  reservation_id: LIVE281-{run_id}")
    print(f"  idempotency_key: {idempotency_key}")
    print(f"  event_log row: {row.get('event_id')}")
    print(f"{'='*60}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Phase 281 — iHouse Core Live OTA Integration Test"
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://localhost:8000"),
        help="Base URL of the running iHouse Core API",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: build payload + compute HMAC but don't POST",
    )
    args = parser.parse_args()

    success = run_live_test(args.base_url, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
