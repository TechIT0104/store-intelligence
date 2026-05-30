# PROMPT: "Write pytest tests for a Prometheus /metrics endpoint (text exposition,
#   increments an events-ingested counter) and for concurrency-safe idempotent ingest
#   using INSERT ... ON CONFLICT DO NOTHING, so two identical payloads never raise."
# CHANGES MADE: Added a direct test of the conflict-safe insert with a duplicate id in
#   the SAME batch (the model only re-posted across requests), proving the ON CONFLICT
#   path doesn't raise a primary-key error.
from __future__ import annotations

import uuid

from app.db import EventRow, session_scope
from app.ingestion import _conflict_safe_insert
from tests.conftest import make_event


def test_metrics_endpoint_exposes_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "storeiq_requests_total" in r.text
    assert "storeiq_events_ingested_total" in r.text


def test_events_ingested_counter_increments(client):
    before = _counter_value(client, "storeiq_events_ingested_total")
    ev = make_event("VIS_m", "ENTRY", 0, camera_id="CAM_ENTRY_01")
    assert client.post("/events/ingest", json={"events": [ev]}).status_code == 200
    after = _counter_value(client, "storeiq_events_ingested_total")
    assert after >= before + 1


def _counter_value(client, name) -> float:
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(name + " "):
            return float(line.split()[1])
    return 0.0


def test_conflict_safe_insert_handles_duplicate_id():
    eid = str(uuid.uuid4())
    rows = []
    for et in ("ENTRY", "EXIT"):
        e = make_event("VIS_dup", et, 0, event_id=eid, camera_id="CAM_ENTRY_01")
        rows.append(EventRow(
            event_id=e["event_id"], store_id=e["store_id"], camera_id=e["camera_id"],
            visitor_id=e["visitor_id"], event_type=e["event_type"],
            ts=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            zone_id=None, dwell_ms=0, is_staff=False, confidence=0.9,
            queue_depth=None, sku_zone=None, session_seq=1))
    # duplicate event_id in one insert must NOT raise (ON CONFLICT DO NOTHING)
    with session_scope() as s:
        _conflict_safe_insert(s, rows)
    with session_scope() as s:
        assert s.query(EventRow).filter_by(event_id=eid).count() == 1
