"""Operational anomaly detection.

Three detectors, each emitting severity (INFO/WARN/CRITICAL) + suggested_action:
  - BILLING_QUEUE_SPIKE : queue depth crossed threshold recently
  - CONVERSION_DROP     : today's conversion well below the 7-day average
  - DEAD_ZONE           : a customer zone has had no visits for 30+ minutes

All times are anchored to the store's latest event so this works on replayed data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import EventRow
from .metrics import compute_metrics
from .queries import converted_visitors, latest_event_ts, resolve_window, unique_visitors


def _anchor(session: Session, store_id: str) -> datetime:
    return latest_event_ts(session, store_id) or datetime.now(timezone.utc)


def _queue_spike(session: Session, store_id: str, anchor: datetime, cfg) -> list[dict]:
    lo = anchor - timedelta(minutes=cfg.metrics_window_hours * 60)
    mx = session.scalar(
        select(func.max(EventRow.queue_depth)).where(
            EventRow.store_id == store_id,
            EventRow.event_type == "BILLING_QUEUE_JOIN",
            EventRow.ts >= lo, EventRow.ts <= anchor,
        )
    )
    if mx is None or mx < cfg.queue_spike_depth:
        return []
    severity = "CRITICAL" if mx >= cfg.queue_spike_depth + 3 else "WARN"
    return [{
        "type": "BILLING_QUEUE_SPIKE",
        "severity": severity,
        "detail": f"Billing queue reached depth {mx} (threshold {cfg.queue_spike_depth}).",
        "metric": {"queue_depth_max": int(mx)},
        "suggested_action": "Open an additional billing counter and route staff to checkout.",
    }]


def _conversion_drop(session: Session, store_id: str, anchor: datetime, cfg) -> list[dict]:
    # today's window
    s, e = resolve_window(session, store_id)
    cur = compute_metrics(session, store_id, start=s, end=e)["conversion_rate"]

    # 7 prior daily windows
    rates = []
    for d in range(1, 8):
        ws = s - timedelta(days=d)
        we = e - timedelta(days=d)
        v = unique_visitors(session, store_id, ws, we)
        if not v:
            continue
        c = converted_visitors(session, store_id, ws, we) & v
        rates.append(len(c) / len(v))
    if not rates:
        return []  # no baseline -> can't flag a drop
    baseline = sum(rates) / len(rates)
    if baseline <= 0:
        return []
    drop_pct = 100 * (baseline - cur) / baseline
    if drop_pct < cfg.conversion_drop_pct:
        return []
    severity = "CRITICAL" if drop_pct >= cfg.conversion_drop_pct * 1.5 else "WARN"
    return [{
        "type": "CONVERSION_DROP",
        "severity": severity,
        "detail": f"Conversion {cur:.2%} is {drop_pct:.0f}% below the 7-day avg {baseline:.2%}.",
        "metric": {"current": round(cur, 4), "baseline_7d": round(baseline, 4)},
        "suggested_action": "Check staffing on the floor and at billing; verify no checkout outage.",
    }]


def _dead_zones(session: Session, store_id: str, anchor: datetime, cfg) -> list[dict]:
    out = []
    cutoff = anchor - timedelta(minutes=cfg.dead_zone_minutes)
    # customer-facing zones only (exclude staff-only STOCKROOM)
    zones = session.scalars(
        select(EventRow.zone_id).where(
            EventRow.store_id == store_id, EventRow.zone_id.isnot(None),
            EventRow.zone_id != "STOCKROOM",
        ).distinct()
    ).all()
    for z in zones:
        last = session.scalar(
            select(func.max(EventRow.ts)).where(
                EventRow.store_id == store_id, EventRow.zone_id == z,
                EventRow.is_staff.is_(False),
            )
        )
        if last is None:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last < cutoff:
            mins = int((anchor - last).total_seconds() // 60)
            out.append({
                "type": "DEAD_ZONE",
                "severity": "WARN",
                "detail": f"Zone {z} has had no customer visits for {mins} minutes.",
                "metric": {"zone_id": z, "minutes_since_last_visit": mins},
                "suggested_action": f"Check {z} display/lighting and consider a floor walk or promotion.",
            })
    return out


def detect_anomalies(session: Session, store_id: str) -> dict:
    cfg = get_settings()
    anchor = _anchor(session, store_id)
    anomalies = []
    anomalies += _queue_spike(session, store_id, anchor, cfg)
    anomalies += _conversion_drop(session, store_id, anchor, cfg)
    anomalies += _dead_zones(session, store_id, anchor, cfg)

    order = {"CRITICAL": 0, "WARN": 1, "INFO": 2}
    anomalies.sort(key=lambda a: order.get(a["severity"], 3))
    return {
        "store_id": store_id,
        "as_of": anchor.isoformat(),
        "active_count": len(anomalies),
        "anomalies": anomalies,
    }
