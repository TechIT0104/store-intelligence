# PROMPT: "Write pytest tests for a FastAPI /events/ingest endpoint that must be
#   idempotent by event_id, return partial success on malformed events, dedup within
#   a batch, and reject batches over 500. Use the TestClient and a temp SQLite DB."
# CHANGES MADE: Tightened the idempotency test to re-POST the *identical* payload and
#   assert accepted=0/duplicates=N (the model's first draft only checked the row count).
#   Added the intra-batch duplicate-id case and the malformed-confidence case, and
#   asserted the response is 207 (not 200) when some items are rejected.
from __future__ import annotations

import uuid

from tests.conftest import make_event


def test_ingest_basic_and_idempotent(client):
    ev = make_event("VIS_a", "ENTRY", 0, camera_id="CAM_ENTRY_01")
    payload = {"events": [ev]}

    r1 = client.post("/events/ingest", json=payload)
    assert r1.status_code == 200
    assert r1.json()["accepted"] == 1

    # re-post identical payload -> idempotent: nothing new accepted, 1 duplicate
    r2 = client.post("/events/ingest", json=payload)
    assert r2.status_code == 200
    body = r2.json()
    assert body["accepted"] == 0
    assert body["duplicates"] == 1


def test_partial_success_on_malformed(client):
    good = make_event("VIS_b", "ENTRY", 1, camera_id="CAM_ENTRY_01")
    bad = make_event("VIS_c", "ENTRY", 2)
    bad["confidence"] = 5.0  # out of [0,1] -> rejected
    r = client.post("/events/ingest", json={"events": [good, bad]})
    assert r.status_code == 207  # partial success
    body = r.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 1
    assert body["errors"][0]["index"] == 1


def test_intra_batch_duplicate_id(client):
    eid = str(uuid.uuid4())
    a = make_event("VIS_d", "ENTRY", 0, event_id=eid, camera_id="CAM_ENTRY_01")
    b = make_event("VIS_d", "EXIT", 5, event_id=eid, camera_id="CAM_ENTRY_01")
    r = client.post("/events/ingest", json={"events": [a, b]})
    assert r.status_code == 200
    # same event_id twice in one batch collapses to a single stored row
    assert r.json()["accepted"] == 1


def test_batch_over_500_rejected(client):
    events = [make_event(f"VIS_{i}", "ENTRY", i, camera_id="CAM_ENTRY_01")
              for i in range(501)]
    r = client.post("/events/ingest", json={"events": events})
    assert r.status_code == 422  # pydantic max_length on the batch envelope


def test_never_5xx_on_garbage(client):
    # acceptance gate #3: ingest must not 5xx on malformed events
    r = client.post("/events/ingest", json={"events": [{"nonsense": True}]})
    assert r.status_code in (200, 207, 422)
    assert r.status_code < 500
