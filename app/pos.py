"""POS transaction loading + visitor->purchase correlation.

POS has no customer identity. A visitor is 'converted' if they were in the
BILLING zone within `conversion_window_min` minutes BEFORE a transaction
timestamp for the same store (per the problem statement).

Supports two CSV shapes:
  * Simple   : store_id, transaction_id, timestamp(ISO), basket_value_inr
  * Real POS : the Brigade_Bangalore export (order_id, order_date DD-MM-YYYY,
               order_time HH:MM:SS in IST, store_id, total_amount, ... with one
               row PER LINE ITEM). We group line items into one transaction per
               order_id, sum total_amount, and convert IST -> UTC.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from .db import PosRow, session_scope

IST = timezone(timedelta(hours=5, minutes=30))


def _parse_iso(s: str) -> datetime:
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse_real_dt(date_s: str, time_s: str) -> datetime:
    # order_date "10-04-2026" (DD-MM-YYYY) + order_time "16:55:36" (IST)
    d = datetime.strptime(date_s.strip(), "%d-%m-%Y").date()
    t = datetime.strptime(time_s.strip().split(".")[0], "%H:%M:%S").time()
    return datetime.combine(d, t, tzinfo=IST).astimezone(timezone.utc)


def _read_transactions(path: Path) -> list[dict]:
    """Return one record per transaction: {transaction_id, store_id, ts, basket}."""
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cols = set(rows[0].keys())

    if {"transaction_id", "timestamp"} <= cols:        # simple schema
        out = []
        for r in rows:
            tid = (r.get("transaction_id") or "").strip()
            if not tid:
                continue
            try:
                out.append({"transaction_id": tid,
                            "store_id": (r.get("store_id") or "").strip(),
                            "ts": _parse_iso(r["timestamp"]),
                            "basket": float(r.get("basket_value_inr") or 0)})
            except Exception:
                continue
        return out

    if {"order_id", "order_date", "order_time"} <= cols:   # real Purplle export
        agg: dict[str, dict] = {}
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            oid = (r.get("order_id") or "").strip()
            if not oid:
                continue
            if oid not in agg:
                try:
                    ts = _parse_real_dt(r["order_date"], r["order_time"])
                except Exception:
                    continue
                agg[oid] = {"transaction_id": oid,
                            "store_id": (r.get("store_id") or "").strip(), "ts": ts}
            try:
                totals[oid] += float(r.get("total_amount") or 0)
            except Exception:
                pass
        for oid, rec in agg.items():
            rec["basket"] = round(totals[oid], 2)
        return list(agg.values())

    return []


def load_pos_csv(path: str | Path) -> int:
    """Load POS transactions into the DB (idempotent by transaction_id)."""
    p = Path(path)
    if not p.exists():
        return 0
    txns = _read_transactions(p)
    added = 0
    with session_scope() as s:
        existing = set(s.scalars(select(PosRow.transaction_id)).all())
        for t in txns:
            if t["transaction_id"] in existing:
                continue
            s.add(PosRow(transaction_id=t["transaction_id"], store_id=t["store_id"],
                         ts=t["ts"], basket_value_inr=t["basket"]))
            existing.add(t["transaction_id"])
            added += 1
    return added
