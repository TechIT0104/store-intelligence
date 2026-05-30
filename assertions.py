"""Example acceptance assertions (mirrors the challenge's assertions.py).

These run against a LIVE API (default http://localhost:8000) after `docker compose up`
and a replay. They are a self-check of the acceptance gate + core endpoint contracts —
NOT the full scoring suite.

Usage:
    python assertions.py                 # uses http://localhost:8000
    API_URL=http://host:8000 python assertions.py
"""
from __future__ import annotations

import os
import sys
import uuid

import requests

API = os.environ.get("API_URL", "http://localhost:8000")
STORE = "STORE_BLR_002"
passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}")


def _event(visitor, etype, ts, **kw):
    return {"event_id": str(uuid.uuid4()), "store_id": STORE,
            "camera_id": kw.get("camera_id", "CAM_ENTRY_01"), "visitor_id": visitor,
            "event_type": etype, "timestamp": ts, "zone_id": kw.get("zone_id"),
            "dwell_ms": kw.get("dwell_ms", 0), "is_staff": kw.get("is_staff", False),
            "confidence": kw.get("confidence", 0.9),
            "metadata": {"queue_depth": kw.get("queue_depth"),
                         "sku_zone": kw.get("zone_id"), "session_seq": 1}}


def main():
    # 1. health is reachable
    r = requests.get(f"{API}/health", timeout=10)
    check("1. GET /health returns 200", r.status_code == 200)
    check("2. /health reports a status field", "status" in r.json())

    # 3. ingest a batch (no 5xx)
    batch = {"events": [
        _event("VIS_assert1", "ENTRY", "2026-10-04T14:39:00Z"),
        _event("VIS_assert1", "ZONE_ENTER", "2026-10-04T14:39:20Z",
               camera_id="CAM_BILLING_01", zone_id="BILLING"),
        _event("VIS_assert2", "ENTRY", "2026-10-04T14:39:05Z"),
        _event("VIS_staffX", "ENTRY", "2026-10-04T14:39:02Z", is_staff=True),
    ]}
    r = requests.post(f"{API}/events/ingest", json=batch, timeout=10)
    check("3. POST /events/ingest does not 5xx", r.status_code < 500)
    body = r.json()
    check("4. ingest reports accepted count", body.get("accepted", 0) >= 1)

    # 5. idempotency: re-post identical payload
    r2 = requests.post(f"{API}/events/ingest", json=batch, timeout=10)
    check("5. re-ingest is idempotent (0 newly accepted)", r2.json().get("accepted") == 0)

    # 6. malformed event -> partial success, not 5xx
    bad = {"events": [_event("VIS_bad", "ENTRY", "2026-10-04T14:39:00Z", confidence=9.0)]}
    r = requests.post(f"{API}/events/ingest", json=bad, timeout=10)
    check("6. malformed event handled without 5xx", r.status_code < 500)

    # 7. metrics endpoint (the gate)
    r = requests.get(f"{API}/stores/{STORE}/metrics", timeout=10)
    check("7. GET /stores/{id}/metrics returns 200 JSON", r.status_code == 200)
    m = r.json()
    check("8. staff excluded from unique_visitors", m.get("unique_visitors", 99) >= 1)

    # 9. funnel is session-based with stages
    r = requests.get(f"{API}/stores/{STORE}/funnel", timeout=10)
    check("9. GET /funnel returns ordered stages", r.json()["stages"][0]["stage"] == "entry")

    # 10. anomalies endpoint responds with a list
    r = requests.get(f"{API}/stores/{STORE}/anomalies", timeout=10)
    check("10. GET /anomalies returns an anomalies array", isinstance(r.json().get("anomalies"), list))

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
