"""Generate the dataset files the challenge ships but we did not receive.

We only got the 5 CCTV clips, so we synthesise the three companion artifacts the
problem statement references, in the EXACT output schema, deterministically:

  - sample_events.jsonl    : ~200 schema-valid example events (validation fixture)
  - pos_transactions.csv   : POS records aligned to the clip timeline
  - (assertions.py is hand-written separately, mirroring the challenge's example)

The synthesised events deliberately include every edge case the footage contains
(group entry, staff, re-entry, billing queue + abandonment, empty period, low
confidence) so they double as test fixtures and a recall target for the real
detection pipeline. Documented in docs/DESIGN.md.

Run:  python data/synth/generate_sample_data.py
"""
from __future__ import annotations

import csv
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(20260529)  # deterministic output

STORE = "STORE_BLR_002"
# Clip overlay reads 2026-10-04 ~20:09 IST -> UTC base.
BASE = datetime(2026, 10, 4, 14, 39, 0, tzinfo=timezone.utc)

CAM = {
    "ENTRY": "CAM_ENTRY_01",
    "SKINCARE": "CAM_FLOOR_01",
    "MAKEUP": "CAM_FLOOR_02",
    "BILLING": "CAM_BILLING_01",
    "STOCKROOM": "CAM_BACK_01",
}

OUT_DIR = Path(__file__).resolve().parents[1]  # .../data
events: list[dict] = []
pos_rows: list[dict] = []


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ev(visitor, etype, t, zone=None, dwell=0, staff=False, conf=0.9, seq=0, qdepth=None):
    cam = CAM.get(zone, CAM["ENTRY"]) if zone else CAM["ENTRY"]
    if etype in ("BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON"):
        cam = CAM["BILLING"]
    events.append({
        "event_id": str(uuid.uuid4()),
        "store_id": STORE,
        "camera_id": cam,
        "visitor_id": visitor,
        "event_type": etype,
        "timestamp": iso(t),
        "zone_id": zone,
        "dwell_ms": dwell,
        "is_staff": staff,
        "confidence": round(conf, 2),
        "metadata": {
            "queue_depth": qdepth,
            "sku_zone": zone,
            "session_seq": seq,
        },
    })


def visitor_id() -> str:
    return "VIS_" + uuid.uuid4().hex[:6]


def session(start_offset_s, zones, *, staff=False, base_conf=0.9, buys=False,
            abandons=False, reenter=False, queue_depth=0):
    """Emit a full visit session. Returns (visitor_id, billing_time|None)."""
    vid = visitor_id()
    t = BASE + timedelta(seconds=start_offset_s)
    seq = 1
    ev(vid, "ENTRY", t, None, 0, staff, base_conf, seq); seq += 1
    billing_t = None
    for z in zones:
        t += timedelta(seconds=random.randint(8, 25))
        ev(vid, "ZONE_ENTER", t, z, 0, staff, base_conf, seq); seq += 1
        dwell_s = random.randint(20, 95)
        # ZONE_DWELL every 30s of continued presence
        for d in range(30, dwell_s + 1, 30):
            ev(vid, "ZONE_DWELL", t + timedelta(seconds=d), z, d * 1000, staff,
               base_conf, seq); seq += 1
        t += timedelta(seconds=dwell_s)
        ev(vid, "ZONE_EXIT", t, z, dwell_s * 1000, staff, base_conf, seq); seq += 1

    if "BILLING" in zones or buys or abandons:
        t += timedelta(seconds=random.randint(5, 15))
        billing_t = t
        if queue_depth > 0:
            ev(vid, "BILLING_QUEUE_JOIN", t, "BILLING", 0, staff, base_conf, seq,
               qdepth=queue_depth); seq += 1
        if abandons:
            t += timedelta(seconds=random.randint(40, 120))
            ev(vid, "BILLING_QUEUE_ABANDON", t, "BILLING", 0, staff, base_conf, seq)
            seq += 1
            billing_t = None  # abandoned -> no purchase

    t += timedelta(seconds=random.randint(5, 20))
    ev(vid, "EXIT", t, None, 0, staff, base_conf, seq); seq += 1

    if reenter:
        t += timedelta(seconds=random.randint(30, 90))
        ev(vid, "REENTRY", t, None, 0, staff, base_conf, seq); seq += 1
        ev(vid, "ZONE_ENTER", t + timedelta(seconds=10), "MAKEUP", 0, staff,
           base_conf, seq + 1)
    return vid, billing_t


def main():
    converted_billing_times: list[datetime] = []

    # --- Normal customer sessions (varied paths) ---
    plans = [
        (10,  ["SKINCARE", "MAKEUP", "BILLING"], dict(buys=True, queue_depth=2)),
        (18,  ["MAKEUP"],                         dict()),
        (25,  ["SKINCARE", "BILLING"],            dict(buys=True, queue_depth=1)),
        (33,  ["MAKEUP", "SKINCARE"],             dict()),
        (40,  ["SKINCARE", "MAKEUP", "BILLING"], dict(abandons=True, queue_depth=4)),
        (55,  ["MAKEUP", "BILLING"],              dict(buys=True, queue_depth=3)),
        (70,  ["SKINCARE"],                        dict(reenter=True)),
        (88,  ["MAKEUP", "SKINCARE", "BILLING"], dict(buys=True, queue_depth=2)),
        (95,  ["SKINCARE", "MAKEUP"],             dict()),
        (110, ["BILLING"],                         dict(abandons=True, queue_depth=5)),
    ]
    for off, zones, kw in plans:
        _, bt = session(off, zones, **kw)
        if bt is not None:
            converted_billing_times.append(bt)

    # --- Group entry: 3 people enter together (distinct visitor_ids, ~same time) ---
    for i in range(3):
        session(48 + i, ["MAKEUP", "SKINCARE"])

    # --- Staff sessions: dark uniform / stockroom; must be excluded from metrics ---
    session(5,  ["STOCKROOM", "MAKEUP"], staff=True, base_conf=0.88)
    session(60, ["BILLING", "STOCKROOM"], staff=True, base_conf=0.85, queue_depth=0)

    # --- Low-confidence (partial occlusion) — kept, not suppressed ---
    session(120, ["SKINCARE"], base_conf=0.34)

    # --- Empty-store gap is simply the absence of events between ~130s and ~150s ---

    # Sort by timestamp for realism
    events.sort(key=lambda e: e["timestamp"])

    # Pad to ~200 events with extra short browse sessions if needed
    extra_off = 130
    while len(events) < 200:
        session(extra_off, [random.choice(["SKINCARE", "MAKEUP"])])
        extra_off += 3
        events.sort(key=lambda e: e["timestamp"])

    # --- Write sample_events.jsonl ---
    sample_path = OUT_DIR / "sample_events.jsonl"
    with sample_path.open("w", encoding="utf-8") as f:
        for e in events[:220]:
            f.write(json.dumps(e) + "\n")

    # --- POS transactions: one per converted billing visit (+ a couple extra) ---
    txn = 441
    for bt in converted_billing_times:
        pos_t = bt + timedelta(seconds=random.randint(30, 200))  # txn shortly after billing
        pos_rows.append({
            "store_id": STORE,
            "transaction_id": f"TXN_{txn:05d}",
            "timestamp": iso(pos_t),
            "basket_value_inr": f"{random.choice([680, 1240, 459, 2100, 899, 1599]):.2f}",
        })
        txn += 1

    pos_path = OUT_DIR / "pos_transactions.csv"
    with pos_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["store_id", "transaction_id", "timestamp",
                                          "basket_value_inr"])
        w.writeheader()
        w.writerows(pos_rows)

    print(f"Wrote {len(events[:220])} events -> {sample_path}")
    print(f"Wrote {len(pos_rows)} POS rows  -> {pos_path}")
    staff_n = sum(1 for e in events if e["is_staff"])
    print(f"  staff events: {staff_n}  | event types: "
          f"{sorted(set(e['event_type'] for e in events))}")


if __name__ == "__main__":
    main()
