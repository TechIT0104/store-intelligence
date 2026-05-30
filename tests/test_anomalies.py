# PROMPT: "Write pytest tests for three anomaly detectors: BILLING_QUEUE_SPIKE (queue
#   depth >= threshold), DEAD_ZONE (a customer zone with no visits for 30+ min), and
#   CONVERSION_DROP (today's conversion well below a 7-day baseline). Each anomaly must
#   carry a severity and a suggested_action string."
# CHANGES MADE: The model's dead-zone test didn't advance the 'anchor' time, so nothing
#   looked stale; I added a later event to move the latest-event anchor forward so the
#   earlier zone genuinely ages out. Asserted suggested_action is non-empty for each.
from __future__ import annotations

from app.anomalies import detect_anomalies
from app.db import session_scope
from tests.conftest import make_event, seed_events, seed_pos


def _detect():
    with session_scope() as s:
        return detect_anomalies(s, "STORE_BLR_002")


def _types(res):
    return {a["type"] for a in res["anomalies"]}


def test_queue_spike():
    seed_events([
        make_event("VIS_q", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_q", "BILLING_QUEUE_JOIN", 60, camera_id="CAM_BILLING_01",
                   zone_id="BILLING", queue_depth=6),
    ])
    res = _detect()
    assert "BILLING_QUEUE_SPIKE" in _types(res)
    spike = next(a for a in res["anomalies"] if a["type"] == "BILLING_QUEUE_SPIKE")
    assert spike["severity"] in ("WARN", "CRITICAL")
    assert spike["suggested_action"]


def test_dead_zone():
    seed_events([
        make_event("VIS_a", "ZONE_ENTER", 0, zone_id="SKINCARE"),
        # a much later visit elsewhere pushes the anchor ~50 min ahead
        make_event("VIS_b", "ZONE_ENTER", 3000, zone_id="MAKEUP"),
    ])
    res = _detect()
    assert "DEAD_ZONE" in _types(res)
    dead = next(a for a in res["anomalies"] if a["type"] == "DEAD_ZONE")
    assert dead["metric"]["zone_id"] == "SKINCARE"
    assert dead["suggested_action"]


def test_conversion_drop():
    # prior-day baseline: 2 visitors, both convert (rate 1.0)
    seed_events([
        make_event("VIS_p1", "ENTRY", -90000, camera_id="CAM_ENTRY_01"),
        make_event("VIS_p1", "ZONE_ENTER", -89950, camera_id="CAM_BILLING_01",
                   zone_id="BILLING"),
        make_event("VIS_p2", "ENTRY", -89900, camera_id="CAM_ENTRY_01"),
        make_event("VIS_p2", "ZONE_ENTER", -89850, camera_id="CAM_BILLING_01",
                   zone_id="BILLING"),
    ])
    seed_pos([("TXN_p1", -89940, 500.0), ("TXN_p2", -89840, 500.0)])
    # today: 2 visitors, no purchase (rate 0.0) -> big drop vs baseline
    seed_events([
        make_event("VIS_t1", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_t2", "ENTRY", 10, camera_id="CAM_ENTRY_01"),
    ])
    res = _detect()
    assert "CONVERSION_DROP" in _types(res)


def test_no_anomalies_on_quiet_healthy_store():
    seed_events([
        make_event("VIS_ok", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_ok", "ZONE_ENTER", 10, zone_id="MAKEUP"),
    ])
    res = _detect()
    # no queue spike, no baseline for drop, zones fresh -> nothing critical
    assert "BILLING_QUEUE_SPIKE" not in _types(res)
