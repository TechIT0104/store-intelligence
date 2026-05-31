# PROMPT: "Write pytest tests for the detection pipeline's pure logic (no video):
#   point-in-polygon and entry-line crossing direction, the visitor Re-ID registry
#   (cross-camera match + re-entry after exit), the event emitter's session_seq, and the
#   staff-signal fusion (stockroom > VLM > heuristic)."
# CHANGES MADE: Added the re-entry assertion (resolve the same signature again after
#   mark_exited and assert is_reentry=True) which the model initially missed, and an
#   anti-merge case (very different signature -> new visitor_id, not a false match).
from __future__ import annotations

import numpy as np

from pipeline.zones import EntryLine, point_in_polygon, StoreLayout
from pipeline.reid import VisitorRegistry, hist_similarity
from pipeline.emit import EventEmitter
from pipeline.staff import decide_is_staff


SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]


def test_point_in_polygon():
    assert point_in_polygon((5, 5), SQUARE)
    assert not point_in_polygon((15, 5), SQUARE)


def test_entry_line_direction():
    line = EntryLine((0, 5), (10, 5), inside_normal=(0, 1))  # inside = larger y
    assert line.crossing_direction((5, 2), (5, 8)) == "ENTRY"
    assert line.crossing_direction((5, 8), (5, 2)) == "EXIT"
    assert line.crossing_direction((5, 6), (5, 8)) is None  # no crossing


def test_layout_loads():
    L = StoreLayout.load("data/store_layout.json")
    assert L.store_id == "ST1008"
    assert "CAM_ENTRY_01" in L.cameras
    assert L.cameras["CAM_ENTRY_01"].entry_line is not None


def test_reid_reentry_and_anti_merge():
    reg = VisitorRegistry()
    sig_a = np.zeros(512, dtype=np.float32); sig_a[10] = 1.0
    sig_b = np.zeros(512, dtype=np.float32); sig_b[400] = 1.0  # very different

    vid1, re1 = reg.resolve("CAM_ENTRY_01", 1, sig_a, clip_t=0.0)
    assert re1 is False
    reg.mark_exited(vid1, clip_t=20.0)

    # same appearance returns later (new local track id) -> REENTRY, same visitor_id
    vid2, re2 = reg.resolve("CAM_ENTRY_01", 2, sig_a, clip_t=60.0)
    assert vid2 == vid1
    assert re2 is True

    # a clearly different person -> brand new visitor, not merged
    vid3, _ = reg.resolve("CAM_ENTRY_01", 3, sig_b, clip_t=61.0)
    assert vid3 != vid1


def test_hist_similarity_bounds():
    a = np.ones(512, dtype=np.float32)
    assert 0.0 <= hist_similarity(a, a) <= 1.0


def test_emitter_session_seq(tmp_path):
    from datetime import datetime, timezone
    out = tmp_path / "ev.jsonl"
    with EventEmitter("STORE_BLR_002", out, datetime(2026, 10, 4, tzinfo=timezone.utc)) as em:
        e1 = em.emit(camera_id="CAM_ENTRY_01", visitor_id="VIS_x", event_type="ENTRY",
                     frame_offset_s=0)
        e2 = em.emit(camera_id="CAM_FLOOR_01", visitor_id="VIS_x", event_type="ZONE_ENTER",
                     frame_offset_s=5, zone_id="MAKEUP")
    assert e1["metadata"]["session_seq"] == 1
    assert e2["metadata"]["session_seq"] == 2
    assert e1["store_id"] == "STORE_BLR_002"


def test_staff_fusion_priorities():
    # stockroom presence dominates
    assert decide_is_staff(True, 0.0, None) == (True, 0.97)
    # heuristic alone, above threshold
    is_staff, conf = decide_is_staff(False, 0.8, None)
    assert is_staff is True and conf == 0.8
    # low heuristic -> customer
    assert decide_is_staff(False, 0.2, None)[0] is False
