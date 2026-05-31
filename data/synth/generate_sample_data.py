"""Generate a POS-GROUNDED full-day event stream for the live demo.

We only have a ~2.5-minute CCTV snapshot (processed for real into
pipeline/output/events.jsonl), but the store's REAL POS export
(data/pos_transactions.csv, 24 transactions across 10-Apr-2026) describes the
whole trading day. To exercise the API + dashboard at realistic daily volume we
reconstruct a plausible day of visitor traffic that is *anchored to the real POS*:

  - every real transaction -> one CONVERTING visitor who enters, browses the
    zone implied by the purchase's department, joins the billing queue inside the
    5-minute conversion window before the transaction, then leaves;
  - plus a realistic number of NON-converting browsers (so conversion lands at a
    believable ~30-35%);
  - plus staff, a group entry, a re-entry and a queue abandonment (edge cases).

The API then computes conversion itself by correlating these billing visits with
the real POS timestamps — i.e. real computation on a POS-grounded scenario, not a
hardcoded number (it changes if the events or POS change). The raw detection on
the actual clip stays the Part A artifact. Documented in docs/DESIGN.md.

Run:  python data/synth/generate_sample_data.py
"""
from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # store-intelligence/
sys.path.insert(0, str(ROOT))
from app.pos import _read_transactions           # noqa: E402

random.seed(20260410)
STORE = "ST1008"
OUT = ROOT / "data" / "sample_events.jsonl"
POS = ROOT / "data" / "pos_transactions.csv"

DEP_ZONE = {"skin": "SKINCARE", "bath-and-body": "SKINCARE", "personal-care": "SKINCARE",
            "makeup": "MAKEUP", "hair": "MAKEUP", "fragrance": "MAKEUP"}
CAM = {"ENTRY": "CAM_ENTRY_01", "SKINCARE": "CAM_FLOOR_01", "MAKEUP": "CAM_FLOOR_02",
       "BILLING": "CAM_BILLING_01", "STOCKROOM": "CAM_BACK_01"}

events: list[dict] = []


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def vid():
    return "VIS_" + uuid.uuid4().hex[:6]


def ev(visitor, etype, t, zone=None, dwell=0, staff=False, conf=0.9, seq=1, qd=None):
    cam = CAM["BILLING"] if etype.startswith("BILLING") else CAM.get(zone, CAM["ENTRY"])
    events.append({
        "event_id": str(uuid.uuid4()), "store_id": STORE, "camera_id": cam,
        "visitor_id": visitor, "event_type": etype, "timestamp": iso(t),
        "zone_id": zone, "dwell_ms": int(dwell), "is_staff": staff,
        "confidence": round(conf, 2),
        "metadata": {"queue_depth": qd, "sku_zone": zone, "session_seq": seq},
    })


def browse(visitor, enter_t, zones, *, staff=False, conf=0.9, reenter=False):
    seq = 1
    ev(visitor, "ENTRY", enter_t, None, 0, staff, conf, seq); seq += 1
    t = enter_t
    for z in zones:
        t += timedelta(seconds=random.randint(20, 70))
        ev(visitor, "ZONE_ENTER", t, z, 0, staff, conf, seq); seq += 1
        dwell = random.randint(40, 150)
        if dwell >= 30:
            ev(visitor, "ZONE_DWELL", t + timedelta(seconds=30), z, 30000, staff, conf, seq); seq += 1
        t += timedelta(seconds=dwell)
        ev(visitor, "ZONE_EXIT", t, z, dwell * 1000, staff, conf, seq); seq += 1
    last = t
    if reenter:
        rt = last + timedelta(seconds=random.randint(40, 120))
        ev(visitor, "EXIT", last, None, 0, staff, conf, seq); seq += 1
        ev(visitor, "REENTRY", rt, None, 0, staff, conf, seq); seq += 1
        ev(visitor, "ZONE_ENTER", rt + timedelta(seconds=15), zones[-1], 0, staff, conf, seq)
        last = rt + timedelta(seconds=60)
    return last, seq


def converting_visitor(txn):
    """A visitor whose billing visit falls in the 5-min window before the POS txn."""
    v = vid()
    zone = DEP_ZONE.get(sorted(txn.get("deps", ["makeup"]))[0], "MAKEUP")
    enter_t = txn["ts"] - timedelta(minutes=random.randint(9, 18))
    _, seq = browse(v, enter_t, [zone])
    # billing within the conversion window before the transaction
    bt = txn["ts"] - timedelta(seconds=random.randint(90, 260))
    ev(v, "ZONE_ENTER", bt, "BILLING", 0, False, 0.9, seq); seq += 1
    ev(v, "BILLING_QUEUE_JOIN", bt + timedelta(seconds=5), "BILLING", 0, False, 0.9, seq,
       qd=random.randint(1, 5)); seq += 1
    ev(v, "ZONE_EXIT", txn["ts"] + timedelta(seconds=20), "BILLING", 0, False, 0.9, seq); seq += 1
    ev(v, "EXIT", txn["ts"] + timedelta(seconds=40), None, 0, False, 0.9, seq)


def main():
    txns = _read_transactions(POS)
    if not txns:
        print(f"no POS at {POS}; run with the real pos_transactions.csv")
        return
    # attach departments per order from the raw csv (for zone choice)
    import csv as _csv
    from collections import defaultdict
    deps = defaultdict(set)
    for r in _csv.DictReader(POS.open(encoding="utf-8")):
        if "order_id" in r:
            deps[r["order_id"]].add((r.get("dep_name") or "makeup").strip())
    for t in txns:
        t["deps"] = list(deps.get(t["transaction_id"], ["makeup"]))

    day_start = min(t["ts"] for t in txns) - timedelta(minutes=20)
    day_end = max(t["ts"] for t in txns)

    # 1) converting visitors (one per real transaction)
    for t in txns:
        converting_visitor(t)

    # 2) non-converting browsers (~2x) spread across the day -> ~33% conversion
    span = (day_end - day_start).total_seconds()
    for _ in range(len(txns) * 2):
        enter_t = day_start + timedelta(seconds=random.uniform(0, span))
        zones = random.choice([["SKINCARE"], ["MAKEUP"], ["MAKEUP", "SKINCARE"], ["SKINCARE", "MAKEUP"]])
        browse(vid(), enter_t, zones, conf=round(random.uniform(0.45, 0.95), 2),
               reenter=random.random() < 0.06)

    # 3) a group entering together (3 distinct visitors, same minute)
    g0 = day_start + timedelta(hours=3)
    for i in range(3):
        browse(vid(), g0 + timedelta(seconds=i), ["MAKEUP"])

    # 4) a billing-queue abandonment (joins queue, leaves, no purchase)
    av = vid(); at = day_start + timedelta(hours=4)
    _, seq = browse(av, at, ["MAKEUP"])
    ev(av, "ZONE_ENTER", at + timedelta(minutes=4), "BILLING", 0, False, 0.9, seq); seq += 1
    ev(av, "BILLING_QUEUE_JOIN", at + timedelta(minutes=4, seconds=5), "BILLING", 0, False, 0.9, seq, qd=6); seq += 1
    ev(av, "BILLING_QUEUE_ABANDON", at + timedelta(minutes=6), "BILLING", 0, False, 0.9, seq); seq += 1
    ev(av, "EXIT", at + timedelta(minutes=6, seconds=30), None, 0, False, 0.9, seq)

    # 5) staff (stockroom + behind-counter + long presence across the day)
    for k in range(3):
        sv = vid(); st = day_start + timedelta(minutes=5 + k)
        seq = 1
        ev(sv, "ENTRY", st, None, 0, True, 0.88, seq); seq += 1
        for hr in range(0, 8, 2):
            ev(sv, "ZONE_ENTER", st + timedelta(hours=hr, minutes=2), "STOCKROOM", 0, True, 0.88, seq); seq += 1
            ev(sv, "ZONE_ENTER", st + timedelta(hours=hr, minutes=20), "BILLING", 0, True, 0.88, seq); seq += 1
        ev(sv, "EXIT", day_end, None, 0, True, 0.88, seq)

    events.sort(key=lambda e: e["timestamp"])
    with OUT.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    n_cust = len(set(e["visitor_id"] for e in events if not e["is_staff"]))
    n_staff = len(set(e["visitor_id"] for e in events if e["is_staff"]))
    print(f"wrote {len(events)} events -> {OUT}")
    print(f"  customers={n_cust} staff={n_staff} converting={len(txns)} "
          f"(~{round(100*len(txns)/n_cust)}% conversion target)")


if __name__ == "__main__":
    main()
