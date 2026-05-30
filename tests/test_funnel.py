# PROMPT: "Write pytest tests for a conversion funnel (Entry -> Zone Visit -> Billing
#   Queue -> Purchase) where the unit is a session (visitor_id), re-entries must not
#   double-count a visitor, and stages must be monotonically non-increasing."
# CHANGES MADE: Added an explicit re-entry test (same visitor_id with ENTRY + REENTRY)
#   asserting the entry stage counts the visitor once. Also asserted monotonicity across
#   all stages rather than only checking the final purchase count.
from __future__ import annotations

from datetime import timedelta

from app.db import session_scope
from app.funnel import compute_funnel
from tests.conftest import BASE_TS, make_event, seed_events, seed_pos

WIN_START = BASE_TS - timedelta(hours=1)
WIN_END = BASE_TS + timedelta(hours=1)


def _funnel():
    with session_scope() as s:
        return compute_funnel(s, "STORE_BLR_002", start=WIN_START, end=WIN_END)


def _stage(funnel, name):
    return next(s for s in funnel["stages"] if s["stage"] == name)


def test_funnel_full_path_and_monotonic():
    seed_events([
        make_event("VIS_buy", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_buy", "ZONE_ENTER", 10, zone_id="MAKEUP"),
        make_event("VIS_buy", "ZONE_ENTER", 600, camera_id="CAM_BILLING_01",
                   zone_id="BILLING"),
        make_event("VIS_look", "ENTRY", 5, camera_id="CAM_ENTRY_01"),
        make_event("VIS_look", "ZONE_ENTER", 15, zone_id="SKINCARE"),
    ])
    seed_pos([("TXN_9", 650, 999.0)])
    f = _funnel()
    counts = [s["count"] for s in f["stages"]]
    assert counts == sorted(counts, reverse=True)  # monotonic
    assert _stage(f, "entry")["count"] == 2
    assert _stage(f, "zone_visit")["count"] == 2
    assert _stage(f, "billing_queue")["count"] == 1
    assert _stage(f, "purchase")["count"] == 1


def test_reentry_not_double_counted():
    # same physical visitor (same visitor_id) leaves and returns
    seed_events([
        make_event("VIS_re", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_re", "EXIT", 30, camera_id="CAM_ENTRY_01"),
        make_event("VIS_re", "REENTRY", 90, camera_id="CAM_ENTRY_01"),
        make_event("VIS_re", "ZONE_ENTER", 100, zone_id="MAKEUP"),
    ])
    f = _funnel()
    assert _stage(f, "entry")["count"] == 1  # counted once despite re-entry


def test_drop_off_percentages():
    seed_events([
        make_event("VIS_1", "ENTRY", 0, camera_id="CAM_ENTRY_01"),
        make_event("VIS_2", "ENTRY", 1, camera_id="CAM_ENTRY_01"),
        make_event("VIS_1", "ZONE_ENTER", 10, zone_id="MAKEUP"),
    ])
    f = _funnel()
    zone = _stage(f, "zone_visit")
    assert zone["count"] == 1
    assert zone["drop_off_pct_from_prev"] == 50.0  # 2 -> 1
