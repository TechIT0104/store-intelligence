"""Staff / store-operations analytics from the real POS salesperson data.

The Purplle POS export carries `salesperson_name` / `employee_code` and a precise
`order_time` per line item. From that we reconstruct each employee's working day:
  - transactions handled & customers attended (a billed order ~ a served customer)
  - items sold and revenue generated
  - shift span (first -> last activity) and active hours
  - the largest idle gap in their activity (a proxy for the lunch/long break)
  - a simple utilisation estimate (busy minutes vs shift minutes)

This is grounded entirely in the real data — no hardcoding — and powers the
Store Operations page. Detection's staff events (zone presence) can layer on top.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import get_settings
from .pos import IST

# a gap longer than this between a salesperson's billings is treated as a break
BREAK_GAP_MIN = 25
# assume a customer interaction occupies roughly this many minutes around a sale
SERVICE_MIN = 6


def _parse_dt(date_s: str, time_s: str) -> datetime | None:
    try:
        d = datetime.strptime(date_s.strip(), "%d-%m-%Y").date()
        t = datetime.strptime(time_s.strip().split(".")[0], "%H:%M:%S").time()
        return datetime.combine(d, t, tzinfo=IST)
    except Exception:
        return None


def compute_staff_ops(store_id: str, pos_path: str | None = None) -> dict:
    path = Path(pos_path or get_settings().pos_csv_path)
    if not path.exists():
        return {"store_id": store_id, "staff": [], "summary": {}}

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    # group line items into orders, then attribute orders to salespeople
    orders: dict[str, dict] = {}
    for r in rows:
        if (r.get("store_id") or "").strip() not in (store_id, "") and store_id != "ST1008":
            pass  # the export is single-store; keep all rows
        oid = (r.get("order_id") or "").strip()
        if not oid:
            continue
        dt = _parse_dt(r.get("order_date", ""), r.get("order_time", ""))
        o = orders.setdefault(oid, {
            "salesperson": (r.get("salesperson_name") or "Unknown").strip() or "Unknown",
            "employee_code": (r.get("employee_code") or "").strip(),
            "dt": dt, "amount": 0.0, "qty": 0,
        })
        try:
            o["amount"] += float(r.get("total_amount") or 0)
        except Exception:
            pass
        try:
            o["qty"] += int(float(r.get("qty") or 0))
        except Exception:
            pass

    by_person: dict[str, list[dict]] = defaultdict(list)
    for o in orders.values():
        if o["dt"] is not None:
            by_person[(o["salesperson"], o["employee_code"])].append(o)

    staff = []
    for (name, code), os_ in by_person.items():
        os_.sort(key=lambda x: x["dt"])
        times = [o["dt"] for o in os_]
        first, last = times[0], times[-1]
        span_min = (last - first).total_seconds() / 60.0
        revenue = round(sum(o["amount"] for o in os_), 2)
        items = sum(o["qty"] for o in os_)
        txns = len(os_)

        # largest idle gap -> likely break
        gaps = [(times[i + 1] - times[i]).total_seconds() / 60.0 for i in range(len(times) - 1)]
        breaks = [g for g in gaps if g >= BREAK_GAP_MIN]
        longest_break = round(max(gaps), 1) if gaps else 0.0
        break_total = round(sum(breaks), 1)

        busy_min = txns * SERVICE_MIN
        utilisation = round(min(1.0, busy_min / span_min), 3) if span_min > 0 else 0.0

        staff.append({
            "salesperson": name,
            "employee_code": code,
            "transactions": txns,
            "customers_attended": txns,
            "items_sold": items,
            "revenue_inr": revenue,
            "avg_basket_inr": round(revenue / txns, 2) if txns else 0.0,
            "first_seen": first.astimezone(timezone.utc).isoformat(),
            "last_seen": last.astimezone(timezone.utc).isoformat(),
            "shift_hours": round(span_min / 60.0, 2),
            "active_minutes_est": busy_min,
            "longest_break_min": longest_break,
            "break_minutes_est": break_total,
            "took_lunch_break": bool(breaks),
            "utilisation": utilisation,
        })

    staff.sort(key=lambda s: s["revenue_inr"], reverse=True)
    total_rev = round(sum(s["revenue_inr"] for s in staff), 2)
    return {
        "store_id": store_id,
        "staff_count": len(staff),
        "summary": {
            "total_revenue_inr": total_rev,
            "total_transactions": sum(s["transactions"] for s in staff),
            "total_items": sum(s["items_sold"] for s in staff),
            "top_performer": staff[0]["salesperson"] if staff else None,
            "avg_utilisation": round(sum(s["utilisation"] for s in staff) / len(staff), 3) if staff else 0.0,
        },
        "staff": staff,
    }
