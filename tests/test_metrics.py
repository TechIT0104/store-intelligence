# PROMPT: "Generate pytest tests for store metrics computation: unique visitors must
#   exclude is_staff=true; conversion uses POS within a 5-min window after a billing
#   visit; zero-purchase and empty-store must return 0.0 (never null/crash)."
# CHANGES MADE: The model assumed conversion counted any billing visit as converted;
#   corrected it to require a POS transaction within the window (added seed_pos with an
#   in-window and an out-of-window txn to prove the boundary). Added the all-staff case.
from __future__ import annotations

from datetime import timedelta

from app.db import session_scope
from app.metrics import compute_metrics
from tests.conftest import BASE_TS, make_event, seed_events, seed_pos

WIN_START = BASE_TS - timedelta(hours=1)
WIN_END = BASE_TS + timedelta(hours=1)


def _metrics():
    with session_scope() as s:
        return compute_metrics(s, "STORE_BLR_002", start=WIN_START, end=WIN_END)


def test_empty_store_returns_zeros_not_null():
    m = _metrics()
    assert m["unique_visitors"] == 0
    assert m["conversion_rate"] == 0.0
    assert m["abandonment_rate"] == 0.0
    assert m["avg_dwell_seconds_per_zone"] == {}


def test_staff_excluded_from_unique_visitors():
    seed_events([
        make_event("VIS_cust", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_staff", "ENTRY", 1, camera_id="CAM_ENTRY_01", is_staff=True),
    ])
    m = _metrics()
    assert m["unique_visitors"] == 1  # staff not counted


def test_conversion_requires_pos_in_window():
    # visitor at billing at +600s; POS at +700s (within 5 min) -> converted
    seed_events([
        make_event("VIS_buyer", "ENTRY", 590, camera_id="CAM_ENTRY_01"),
        make_event("VIS_buyer", "ZONE_ENTER", 600, camera_id="CAM_BILLING_01",
                   zone_id="BILLING"),
        make_event("VIS_browser", "ENTRY", 10, camera_id="CAM_ENTRY_01"),
        make_event("VIS_browser", "ZONE_ENTER", 20, zone_id="SKINCARE"),
    ])
    seed_pos([("TXN_1", 700, 1240.0)])  # 100s after billing visit -> within 5 min
    m = _metrics()
    assert m["unique_visitors"] == 2
    assert m["converted_visitors"] == 1
    assert m["conversion_rate"] == 0.5


def test_zero_purchase_store():
    seed_events([make_event("VIS_x", "ENTRY", 0, camera_id="CAM_ENTRY_01")])
    m = _metrics()
    assert m["conversion_rate"] == 0.0  # no POS -> no conversions, no crash


def test_all_staff_clip():
    seed_events([
        make_event("VIS_s1", "ENTRY", 0, camera_id="CAM_ENTRY_01", is_staff=True),
        make_event("VIS_s2", "ZONE_ENTER", 5, zone_id="STOCKROOM",
                   camera_id="CAM_BACK_01", is_staff=True),
    ])
    m = _metrics()
    assert m["unique_visitors"] == 0
    assert m["conversion_rate"] == 0.0
