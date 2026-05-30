"""Conversion funnel: Entry -> Zone Visit -> Billing Queue -> Purchase.

The unit is the SESSION (one visitor_id), never the raw event. Because the
detection layer reuses the same visitor_id across a re-entry, counting distinct
visitor_ids inherently prevents a returning customer from being double-counted.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import EventRow
from .queries import converted_visitors, resolve_window, unique_visitors


def _distinct_visitors(session: Session, store_id: str, start, end, **filters) -> set[str]:
    stmt = select(EventRow.visitor_id).where(
        EventRow.store_id == store_id, EventRow.is_staff.is_(False),
        EventRow.ts >= start, EventRow.ts <= end,
    )
    if "event_type" in filters:
        stmt = stmt.where(EventRow.event_type == filters["event_type"])
    if "zone_id" in filters:
        stmt = stmt.where(EventRow.zone_id == filters["zone_id"])
    return set(session.scalars(stmt.distinct()).all())


def compute_funnel(session: Session, store_id: str, *, start: datetime | None = None,
                   end: datetime | None = None) -> dict:
    s, e = resolve_window(session, store_id, start=start, end=end)

    entered = unique_visitors(session, store_id, s, e)                      # stage 1
    zone_visited = _distinct_visitors(session, store_id, s, e, event_type="ZONE_ENTER")
    billing = _distinct_visitors(session, store_id, s, e, zone_id="BILLING")
    purchased = converted_visitors(session, store_id, s, e) & entered

    # keep funnel monotonic (later stages are subsets of earlier ones)
    zone_visited &= entered
    billing &= entered
    purchased &= billing if billing else purchased

    stages = [
        ("entry", len(entered)),
        ("zone_visit", len(zone_visited)),
        ("billing_queue", len(billing)),
        ("purchase", len(purchased)),
    ]

    out = []
    prev = None
    top = stages[0][1] or 0
    for name, count in stages:
        drop = 0.0
        if prev is not None and prev > 0:
            drop = round(100 * (prev - count) / prev, 2)
        out.append({
            "stage": name,
            "count": count,
            "drop_off_pct_from_prev": drop,
            "pct_of_entry": round(100 * count / top, 2) if top else 0.0,
        })
        prev = count

    return {
        "store_id": store_id,
        "window": {"start": s.isoformat(), "end": e.isoformat()},
        "unit": "session (unique visitor_id)",
        "stages": out,
        "overall_conversion_rate": round(len(purchased) / len(entered), 4) if entered else 0.0,
    }
