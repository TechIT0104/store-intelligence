"""Health endpoint — the first thing an on-call engineer checks.

Reports per-store last event timestamp AND last ingestion wall-clock time. The
STALE_FEED warning is based on INGESTION recency (is the feed still flowing now?),
not the event's embedded timestamp — so it stays correct even when replaying
historical clips whose timestamps are days old. DB reachability is checked
explicitly so /health can report `degraded` instead of throwing.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import EventRow, healthcheck, session_scope


def health_report() -> dict:
    cfg = get_settings()
    now = datetime.now(timezone.utc)

    if not healthcheck():
        return {"status": "degraded", "db": "unavailable", "stores": [], "time": now.isoformat()}

    stores = []
    overall_stale = False
    with session_scope() as s:  # type: Session
        rows = s.execute(
            select(
                EventRow.store_id,
                func.max(EventRow.ts),
                func.max(EventRow.ingested_at),
                func.count(),
            ).group_by(EventRow.store_id)
        ).all()
        for store_id, last_ts, last_ingest, n in rows:
            if last_ingest is not None and last_ingest.tzinfo is None:
                last_ingest = last_ingest.replace(tzinfo=timezone.utc)
            lag_min = ((now - last_ingest).total_seconds() / 60.0) if last_ingest else None
            stale = lag_min is not None and lag_min > cfg.stale_feed_minutes
            overall_stale = overall_stale or stale
            stores.append({
                "store_id": store_id,
                "events": int(n),
                "last_event_ts": last_ts.isoformat() if last_ts else None,
                "last_ingest_ts": last_ingest.isoformat() if last_ingest else None,
                "ingest_lag_minutes": round(lag_min, 2) if lag_min is not None else None,
                "feed": "STALE_FEED" if stale else "OK",
            })

    return {
        "status": "ok",
        "db": "ok",
        "time": now.isoformat(),
        "stale_feed": overall_stale,
        "stores": stores,
    }
