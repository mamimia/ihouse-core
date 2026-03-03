import json
import os
import urllib.request

import pytest

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("IHOUSE_API_KEY")

pytestmark = pytest.mark.skipif(
    not BASE_URL or not API_KEY,
    reason="BASE_URL or IHOUSE_API_KEY not set",
)

def _request(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, str]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"x-api-key": API_KEY}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def test_health_ok():
    status, body = _request("/health", "GET")
    assert status == 200, (status, body)

def test_events_smoke_booking_created():
    payload = {
        "type": "BOOKING_CREATED",
        "idempotency": {"request_id": "smoke-001"},
        "actor": {"actor_id": "system", "role": "system"},
        "payload": {"booking_id": "demo-1"},
    }
    status, body = _request("/events", "POST", payload)
    assert status in (200, 201), (status, body)
    data = json.loads(body)
    assert "event_id" in data, data
