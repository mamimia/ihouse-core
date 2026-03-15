#!/usr/bin/env python3
"""
Phase 802 — Operational Day Simulation (Runtime E2E Proof)
=========================================================

Runs sequential scenarios against a LIVE staging Docker instance
(localhost:8001) and verifies observable side-effects at every stage.

Pipeline under test:
    Webhook → apply_envelope → booking_state → task_automator → sync_trigger → state transitions

Usage:
    python3 tests/day_simulation_e2e.py

Requirements:
    - Staging Docker running on localhost:8001
    - Supabase live with tenant_e2e_amended data (Phase 801 seeded)
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE = "http://localhost:8001"
TENANT = "tenant_e2e_amended"
DEV_SECRET = "dev"
TS = int(time.time())

# Reservation IDs (lowercase — normalize_reservation_ref lowercases)
ABNB_RES_1 = f"sim802-a-{TS}"
ABNB_RES_2 = f"sim802-b-{TS}"

# Properties (seeded in Phase 801)
PROP_1 = "phangan-villa-01"   # 3 channels: agoda, airbnb, bookingcom
PROP_2 = "samui-resort-02"    # 2 channels

# Dates
CHECKIN_1 = "2026-06-01"
CHECKOUT_1 = "2026-06-05"
CHECKIN_2 = "2026-06-10"
CHECKOUT_2 = "2026-06-14"

results: list[tuple[str, bool, str]] = []


def step(name: str, passed: bool, detail: str = ""):
    tag = "✅" if passed else "❌"
    results.append((name, passed, detail))
    print(f"  {tag} Step {len(results):2d}: {name}")
    if detail:
        for line in detail.strip().split("\n"):
            print(f"          {line}")
    print()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_jwt() -> str:
    r = requests.post(f"{BASE}/auth/dev-login", json={
        "tenant_id": TENANT, "role": "admin", "secret": DEV_SECRET,
    })
    r.raise_for_status()
    data = r.json()
    return data.get("data", {}).get("token") or data.get("token", "")


def hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Payloads (Airbnb format — uses listing_id)
# ---------------------------------------------------------------------------

def airbnb_created(res_id: str, prop: str, ci: str, co: str, guest: str, price: float) -> dict:
    return {
        "reservation_id": res_id, "listing_id": prop,
        "tenant_id": TENANT, "event_id": f"evt-{res_id}-create",
        "event_type": "new",
        "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
        "check_in": ci, "check_out": co,
        "guest_name": guest, "total_price": price,
        "currency": "THB", "status": "confirmed", "guest_count": 2,
    }

def airbnb_canceled(res_id: str, prop: str) -> dict:
    return {
        "reservation_id": res_id, "listing_id": prop,
        "tenant_id": TENANT, "event_id": f"evt-{res_id}-cancel",
        "event_type": "canceled",
        "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
        "check_in": CHECKIN_2, "check_out": CHECKOUT_2,
        "guest_name": "John Smith", "total_price": 0,
        "currency": "THB", "status": "canceled", "guest_count": 0,
    }


def unwrap(resp_json: dict) -> dict:
    """Unwrap response envelope if present."""
    d = resp_json.get("data", resp_json)
    if isinstance(d, dict) and "booking" in d:
        d = d["booking"]
    return d


# ===========================================================================
# SIMULATION
# ===========================================================================

def main():
    print("=" * 70)
    print("  Phase 802 — Operational Day Simulation")
    print(f"  Target: {BASE}  |  Tenant: {TENANT}  |  Run: {TS}")
    print("=" * 70)
    print()

    token = get_jwt()
    h = hdrs(token)

    bid_1 = f"airbnb_{ABNB_RES_1}"
    bid_2 = f"airbnb_{ABNB_RES_2}"

    # ── STEP 1: BOOKING_CREATED #1 (phangan-villa-01) ──────────────────
    r = requests.post(f"{BASE}/webhooks/airbnb",
        json=airbnb_created(ABNB_RES_1, PROP_1, CHECKIN_1, CHECKOUT_1, "Jane Doe", 15000),
        headers=h)
    step("BOOKING_CREATED #1 → phangan-villa-01",
         r.status_code == 200, f"HTTP {r.status_code}")

    # ── STEP 2: Verify booking_state ───────────────────────────────────
    time.sleep(4)
    r2 = requests.get(f"{BASE}/bookings/{bid_1}", headers=h)
    if r2.status_code == 200:
        bk = unwrap(r2.json())
        st = bk.get("status", "?").upper()
        step("Verify booking #1 in booking_state",
             st == "ACTIVE", f"status={st} prop={bk.get('property_id')}")
    else:
        step("Verify booking #1 in booking_state", False, f"HTTP {r2.status_code}")

    # ── STEP 3: Admin summary ──────────────────────────────────────────
    r3 = requests.get(f"{BASE}/admin/summary", headers=h)
    if r3.status_code == 200:
        s = r3.json().get("data", r3.json())
        cnt = s.get("booking_count", s.get("total_bookings", 0))
        step("Admin summary has bookings", cnt > 0, f"booking_count={cnt}")
    else:
        step("Admin summary", False, f"HTTP {r3.status_code}")

    # ── STEP 4: Tasks auto-created ────────────────────────────────────
    r4 = requests.get(f"{BASE}/tasks", params={"booking_id": bid_1}, headers=h)
    task_list = []
    if r4.status_code == 200:
        td = r4.json().get("data", r4.json())
        task_list = td.get("tasks", [])
        kinds = sorted(set(t.get("kind", "?") for t in task_list))
        has_ci = "CHECKIN_PREP" in kinds
        has_cl = "CLEANING" in kinds
        step("Tasks auto-created (CHECKIN_PREP + CLEANING)",
             has_ci and has_cl, f"kinds={kinds} count={len(task_list)}")
    else:
        step("Tasks auto-created", False, f"HTTP {r4.status_code}")

    # ── STEP 5: Task state transitions ────────────────────────────────
    if task_list:
        target = next((t for t in task_list if t.get("kind") == "CHECKIN_PREP"), task_list[0])
        tid = target["task_id"]
        transitions = ["ACKNOWLEDGED", "IN_PROGRESS", "COMPLETED"]
        all_ok = True
        dets = []
        for ns in transitions:
            rt = requests.patch(f"{BASE}/tasks/{tid}/status", json={"status": ns}, headers=h)
            ok = rt.status_code == 200
            all_ok = all_ok and ok
            dets.append(f"→{ns}: {'OK' if ok else f'FAIL({rt.status_code})'}")
        step("Task lifecycle: PENDING → ACK → IN_PROGRESS → COMPLETED",
             all_ok, " | ".join(dets))
    else:
        step("Task lifecycle", False, "No tasks to transition")

    # ── STEP 6: Sync trigger → P801 channel mappings ─────────────────
    r6 = requests.post(f"{BASE}/internal/sync/trigger",
        json={"booking_id": bid_1}, headers=h)
    if r6.status_code == 200:
        plan = r6.json().get("data", r6.json())
        ch = plan.get("total_channels", 0)
        provs = [a.get("provider", "?") for a in plan.get("actions", [])]
        step("Sync trigger → P801 channel mappings",
             ch >= 3, f"channels={ch} providers={provs}")
    else:
        step("Sync trigger → channels", False, f"HTTP {r6.status_code}")

    # ── STEP 7: BOOKING_CREATED #2 (samui-resort-02) ──────────────────
    r7 = requests.post(f"{BASE}/webhooks/airbnb",
        json=airbnb_created(ABNB_RES_2, PROP_2, CHECKIN_2, CHECKOUT_2, "John Smith", 22000),
        headers=h)
    step("BOOKING_CREATED #2 → samui-resort-02",
         r7.status_code == 200, f"HTTP {r7.status_code}")

    # ── STEP 8: BOOKING_CANCELED #2 ──────────────────────────────────
    time.sleep(4)  # let create complete
    r8 = requests.post(f"{BASE}/webhooks/airbnb",
        json=airbnb_canceled(ABNB_RES_2, PROP_2), headers=h)
    step("BOOKING_CANCELED #2 → samui-resort-02",
         r8.status_code == 200, f"HTTP {r8.status_code}")

    # ── STEP 9: Verify cancellation ──────────────────────────────────
    time.sleep(4)
    r9 = requests.get(f"{BASE}/bookings/{bid_2}", headers=h)
    if r9.status_code == 200:
        bk2 = unwrap(r9.json())
        cs = bk2.get("status", "?").upper()
        step("Verify booking #2 status = CANCELED",
             cs == "CANCELED", f"status={cs}")
    else:
        step("Verify booking #2 CANCELED", False, f"HTTP {r9.status_code}")

    # ── STEP 10: Property config intact ──────────────────────────────
    r10 = requests.get(f"{BASE}/admin/property-config", headers=h)
    if r10.status_code == 200:
        pc = r10.json().get("data", r10.json())
        pc_n = pc.get("count", 0)
        step("Property config intact (P801 survives simulation)",
             pc_n >= 3, f"properties={pc_n}")
    else:
        step("Property config intact", False, f"HTTP {r10.status_code}")

    # ── SUMMARY ──────────────────────────────────────────────────────
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"  RESULT: {passed}/{total} steps passed")
    if passed == total:
        print("  🎉 Phase 802 — Day Simulation PASSED")
    else:
        print("  ⚠️  Some steps failed:")
        for name, ok, detail in results:
            if not ok:
                print(f"    ❌ {name}: {detail}")
    print("=" * 70)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
