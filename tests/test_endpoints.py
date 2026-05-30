# PROMPT: "Write an end-to-end pytest that ingests a small event batch through the API
#   and then asserts every GET endpoint (metrics, funnel, heatmap, anomalies, health)
#   returns 200 with valid JSON — this mirrors the challenge acceptance gate."
# CHANGES MADE: Added the heatmap data_confidence assertion (fewer than 20 sessions ->
#   'low') and the explicit gate check on GET /stores/STORE_BLR_002/metrics, which the
#   model's first version did not cover.
from __future__ import annotations

from tests.conftest import make_event

STORE = "STORE_BLR_002"


def _seed(client):
    events = [
        make_event("VIS_1", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_1", "ZONE_ENTER", 10, zone_id="MAKEUP"),
        make_event("VIS_1", "ZONE_EXIT", 70, zone_id="MAKEUP", dwell_ms=60000),
        make_event("VIS_1", "ZONE_ENTER", 600, camera_id="CAM_BILLING_01",
                   zone_id="BILLING"),
        make_event("VIS_2", "ENTRY", 5, camera_id="CAM_ENTRY_01"),
        make_event("VIS_2", "ZONE_ENTER", 20, zone_id="SKINCARE"),
    ]
    r = client.post("/events/ingest", json={"events": events})
    assert r.status_code == 200


def test_acceptance_gate_metrics(client):
    # gate #4: GET /stores/STORE_BLR_002/metrics returns valid JSON
    _seed(client)
    r = client.get(f"/stores/{STORE}/metrics")
    assert r.status_code == 200
    m = r.json()
    assert m["store_id"] == STORE
    assert m["unique_visitors"] == 2
    assert "conversion_rate" in m


def test_funnel_endpoint(client):
    _seed(client)
    r = client.get(f"/stores/{STORE}/funnel")
    assert r.status_code == 200
    assert r.json()["stages"][0]["stage"] == "entry"


def test_heatmap_endpoint(client):
    _seed(client)
    r = client.get(f"/stores/{STORE}/heatmap")
    assert r.status_code == 200
    body = r.json()
    assert body["data_confidence"] == "low"  # < 20 sessions
    zones = {z["zone_id"] for z in body["zones"]}
    assert "MAKEUP" in zones


def test_anomalies_endpoint(client):
    _seed(client)
    r = client.get(f"/stores/{STORE}/anomalies")
    assert r.status_code == 200
    assert "anomalies" in r.json()


def test_health_endpoint(client):
    _seed(client)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "endpoints" in r.json()
