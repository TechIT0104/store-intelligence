"""Real-time metrics + heatmap.

All metrics exclude staff (is_staff=true) and handle zero-traffic / zero-purchase
stores without crashing or returning null.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import EventRow
from .queries import (converted_visitors, resolve_window, unique_visitors)


def _round(x: float, n: int = 4) -> float:
    return round(float(x), n)


def compute_metrics(session: Session, store_id: str, *, start: datetime | None = None,
                    end: datetime | None = None) -> dict:
    s, e = resolve_window(session, store_id, start=start, end=end)

    visitors = unique_visitors(session, store_id, s, e)
    n_visitors = len(visitors)
    converted = converted_visitors(session, store_id, s, e)
    n_converted = len(converted & visitors) if visitors else 0
    conversion_rate = _round(n_converted / n_visitors) if n_visitors else 0.0

    # avg dwell per zone (ms) from ZONE_EXIT events (carry total dwell on exit)
    dwell_rows = session.execute(
        select(EventRow.zone_id, func.avg(EventRow.dwell_ms), func.count()).where(
            EventRow.store_id == store_id,
            EventRow.is_staff.is_(False),
            EventRow.event_type == "ZONE_EXIT",
            EventRow.zone_id.isnot(None),
            EventRow.ts >= s, EventRow.ts <= e,
        ).group_by(EventRow.zone_id)
    ).all()
    # Postgres func.avg() returns Decimal; coerce to float before arithmetic.
    avg_dwell_per_zone = {z: _round(float(avg or 0) / 1000.0, 2) for z, avg, _ in dwell_rows}  # seconds

    # queue depth: current (latest join) + max in window
    q_rows = session.execute(
        select(EventRow.queue_depth, EventRow.ts).where(
            EventRow.store_id == store_id,
            EventRow.event_type == "BILLING_QUEUE_JOIN",
            EventRow.queue_depth.isnot(None),
            EventRow.ts >= s, EventRow.ts <= e,
        ).order_by(EventRow.ts)
    ).all()
    queue_depth_current = q_rows[-1][0] if q_rows else 0
    queue_depth_max = max((r[0] for r in q_rows), default=0)

    # abandonment rate = visitors who abandoned / visitors who reached billing
    billing_visitors = set(session.scalars(
        select(EventRow.visitor_id).where(
            EventRow.store_id == store_id, EventRow.is_staff.is_(False),
            EventRow.zone_id == "BILLING", EventRow.ts >= s, EventRow.ts <= e,
        ).distinct()).all())
    abandon_visitors = set(session.scalars(
        select(EventRow.visitor_id).where(
            EventRow.store_id == store_id, EventRow.is_staff.is_(False),
            EventRow.event_type == "BILLING_QUEUE_ABANDON",
            EventRow.ts >= s, EventRow.ts <= e,
        ).distinct()).all())
    abandonment_rate = _round(len(abandon_visitors) / len(billing_visitors)) if billing_visitors else 0.0

    return {
        "store_id": store_id,
        "window": {"start": s.isoformat(), "end": e.isoformat()},
        "unique_visitors": n_visitors,
        "converted_visitors": n_converted,
        "conversion_rate": conversion_rate,
        "avg_dwell_seconds_per_zone": avg_dwell_per_zone,
        "queue_depth_current": int(queue_depth_current),
        "queue_depth_max": int(queue_depth_max),
        "abandonment_rate": abandonment_rate,
        "data_confidence": "high" if n_visitors >= get_settings().heatmap_min_sessions else "low",
    }


def compute_heatmap(session: Session, store_id: str, *, start: datetime | None = None,
                    end: datetime | None = None) -> dict:
    s, e = resolve_window(session, store_id, start=start, end=end)

    # per-zone: distinct visitors (frequency) + avg dwell seconds
    enter_rows = session.execute(
        select(EventRow.zone_id, func.count(func.distinct(EventRow.visitor_id))).where(
            EventRow.store_id == store_id, EventRow.is_staff.is_(False),
            EventRow.event_type == "ZONE_ENTER", EventRow.zone_id.isnot(None),
            EventRow.ts >= s, EventRow.ts <= e,
        ).group_by(EventRow.zone_id)
    ).all()
    dwell_rows = session.execute(
        select(EventRow.zone_id, func.avg(EventRow.dwell_ms)).where(
            EventRow.store_id == store_id, EventRow.is_staff.is_(False),
            EventRow.event_type == "ZONE_EXIT", EventRow.zone_id.isnot(None),
            EventRow.ts >= s, EventRow.ts <= e,
        ).group_by(EventRow.zone_id)
    ).all()

    freq = {z: int(c) for z, c in enter_rows}
    dwell = {z: float(a or 0) / 1000.0 for z, a in dwell_rows}
    zones = sorted(set(freq) | set(dwell))

    max_freq = max(freq.values(), default=0)
    max_dwell = max(dwell.values(), default=0.0)

    cells = []
    for z in zones:
        f = freq.get(z, 0)
        d = dwell.get(z, 0.0)
        cells.append({
            "zone_id": z,
            "visits": f,
            "avg_dwell_seconds": _round(d, 2),
            "freq_score": _round(100 * f / max_freq, 1) if max_freq else 0.0,
            "dwell_score": _round(100 * d / max_dwell, 1) if max_dwell else 0.0,
        })

    n_sessions = len(unique_visitors(session, store_id, s, e))
    return {
        "store_id": store_id,
        "window": {"start": s.isoformat(), "end": e.isoformat()},
        "sessions": n_sessions,
        "data_confidence": "low" if n_sessions < get_settings().heatmap_min_sessions else "high",
        "zones": cells,
    }
