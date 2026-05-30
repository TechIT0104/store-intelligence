"""Shared query helpers: time-window resolution + staff exclusion.

'Today' is defined as a rolling window of `metrics_window_hours` anchored to the
LATEST event timestamp for the store (not wall-clock), so the same code path is
correct for both live ingestion and replayed historical clips. Callers may pass
explicit (start, end) to override — used by tests for determinism.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import EventRow, PosRow


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; coerce any DB-read datetime back to aware UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def latest_event_ts(session: Session, store_id: str) -> Optional[datetime]:
    ts = session.scalar(
        select(func.max(EventRow.ts)).where(EventRow.store_id == store_id)
    )
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def resolve_window(session: Session, store_id: str, *, hours: int | None = None,
                   start: datetime | None = None, end: datetime | None = None
                   ) -> tuple[datetime, datetime]:
    if start is not None and end is not None:
        return start, end
    hours = hours or get_settings().metrics_window_hours
    anchor = latest_event_ts(session, store_id) or datetime.now(timezone.utc)
    e = end or anchor
    s = start or (e - timedelta(hours=hours))
    return s, e


def customer_events_stmt(store_id: str, start: datetime, end: datetime):
    """Base SELECT for non-staff events of a store within [start, end]."""
    return select(EventRow).where(
        EventRow.store_id == store_id,
        EventRow.is_staff.is_(False),
        EventRow.ts >= start,
        EventRow.ts <= end,
    )


def unique_visitors(session: Session, store_id: str, start: datetime,
                    end: datetime) -> set[str]:
    rows = session.scalars(
        select(EventRow.visitor_id).where(
            EventRow.store_id == store_id,
            EventRow.is_staff.is_(False),
            EventRow.ts >= start,
            EventRow.ts <= end,
        ).distinct()
    ).all()
    return set(rows)


def pos_in_window(session: Session, store_id: str, start: datetime,
                  end: datetime) -> list[PosRow]:
    return list(session.scalars(
        select(PosRow).where(
            PosRow.store_id == store_id,
            PosRow.ts >= start,
            PosRow.ts <= end,
        )
    ).all())


def converted_visitors(session: Session, store_id: str, start: datetime,
                       end: datetime) -> set[str]:
    """Visitors who were in BILLING within conversion_window before a POS txn.

    POS correlation has no customer id -> match by (store, time window). We extend
    the lookback for billing presence slightly before `start` so a purchase early
    in the window still finds its preceding billing visit.
    """
    win = timedelta(minutes=get_settings().conversion_window_min)
    pos_rows = pos_in_window(session, store_id, start, end)
    if not pos_rows:
        return set()

    # billing presence events (visitor was at billing): zone_id == BILLING
    billing = session.execute(
        select(EventRow.visitor_id, EventRow.ts).where(
            EventRow.store_id == store_id,
            EventRow.is_staff.is_(False),
            EventRow.zone_id == "BILLING",
            EventRow.ts >= start - win,
            EventRow.ts <= end,
        )
    ).all()

    converted: set[str] = set()
    for txn in pos_rows:
        txn_ts = _aware(txn.ts)
        lo = txn_ts - win
        for vid, bts in billing:
            bts = _aware(bts)
            if lo <= bts <= txn_ts:
                converted.add(vid)
    return converted
