# PROMPT: "Write pytest tests for a multi-signal staff classifier that fuses access-area
#   signals (stockroom, behind-counter), behaviour (long presence, multi-zone roaming,
#   frequent zone changes), an optional VLM 'working' verdict, and a weak dark-uniform
#   signal. A customer in dark clothes browsing one zone must NOT be classified staff."
# CHANGES MADE: Added the explicit 'dark customer is not staff' regression (the exact
#   over-flagging bug clothing-only detection caused) and a VLM-override case where the
#   VLM verdict flips a borderline visitor.
from __future__ import annotations

from pipeline.staff_signals import VisitorEvidence, score_visitor, classify_all


def _ev(**kw):
    e = VisitorEvidence("v")
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def test_dark_customer_not_staff():
    e = _ev(first_t=0, last_t=25, zones={"MAKEUP"}, zone_enter_count=1,
            appearance_votes=10, dark_votes=10)
    is_staff, conf, reasons = score_visitor(e)
    assert is_staff is False
    assert reasons == ["dark_uniform"]


def test_behind_counter_is_staff():
    e = _ev(first_t=0, last_t=140, billing_frames=20, behind_counter_frames=10)
    is_staff, conf, reasons = score_visitor(e)
    assert is_staff is True
    assert "behind_counter" in reasons


def test_stockroom_is_staff():
    e = _ev(first_t=0, last_t=10, in_stockroom=True)
    assert score_visitor(e)[0] is True


def test_behaviour_roaming_is_staff():
    # no access area, but present the whole clip across many zones with many changes
    e = _ev(first_t=0, last_t=145, zones={"MAKEUP", "SKINCARE", "BILLING"},
            zone_enter_count=7)
    assert score_visitor(e)[0] is True


def test_vlm_working_flips_borderline():
    base = dict(first_t=0, last_t=95, zones={"MAKEUP"}, zone_enter_count=1)
    without = score_visitor(_ev(**base))          # long_presence only -> borderline
    e = _ev(**base); e.vlm_working = True
    with_vlm = score_visitor(e)
    assert with_vlm[0] is True
    assert "vlm_working_action" in with_vlm[2]


def test_classify_all_shape():
    out = classify_all({"a": _ev(in_stockroom=True), "b": _ev(first_t=0, last_t=5)})
    assert out["a"]["is_staff"] is True
    assert out["b"]["is_staff"] is False
    assert "reasons" in out["a"]
