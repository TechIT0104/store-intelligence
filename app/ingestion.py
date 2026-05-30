"""Event ingestion: per-item validation, dedup, partial success.

POST /events/ingest must:
  - accept up to 500 events
  - validate each independently (one bad event must not reject the batch)
  - be idempotent by event_id (re-posting the same payload is a no-op)
  - return a structured summary: received / accepted / duplicates / rejected + errors
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select

from .db import EventRow, session_scope
from .models import Event, IngestItemError, IngestResponse
from .observability import EVENTS_INGESTED


def _conflict_safe_insert(session, rows: list["EventRow"]) -> None:
    """Bulk insert that is safe under concurrent identical payloads.

    Uses INSERT ... ON CONFLICT DO NOTHING on the event_id primary key (Postgres
    and SQLite both support it), so two requests racing the same event_id can't
    raise a primary-key violation -> idempotency holds even under concurrency.
    """
    if not rows:
        return
    dialect = session.bind.dialect.name
    values = [{
        "event_id": r.event_id, "store_id": r.store_id, "camera_id": r.camera_id,
        "visitor_id": r.visitor_id, "event_type": r.event_type, "ts": r.ts,
        "zone_id": r.zone_id, "dwell_ms": r.dwell_ms, "is_staff": r.is_staff,
        "confidence": r.confidence, "queue_depth": r.queue_depth,
        "sku_zone": r.sku_zone, "session_seq": r.session_seq,
        # Core insert bypasses the ORM Python-side default, so set it explicitly.
        "ingested_at": r.ingested_at or datetime.now(timezone.utc),
    } for r in rows]
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _ins
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _ins
    else:  # fallback: plain add (other engines)
        session.add_all(rows)
        return
    session.execute(_ins(EventRow).values(values).on_conflict_do_nothing(
        index_elements=["event_id"]))


def _to_row(ev: Event) -> EventRow:
    return EventRow(
        event_id=str(ev.event_id),
        store_id=ev.store_id,
        camera_id=ev.camera_id,
        visitor_id=ev.visitor_id,
        event_type=ev.event_type if isinstance(ev.event_type, str) else ev.event_type.value,
        ts=ev.timestamp,
        zone_id=ev.zone_id,
        dwell_ms=ev.dwell_ms,
        is_staff=ev.is_staff,
        confidence=ev.confidence,
        queue_depth=ev.metadata.queue_depth,
        sku_zone=ev.metadata.sku_zone,
        session_seq=ev.metadata.session_seq,
    )


def ingest_events(raw_events: list[dict]) -> IngestResponse:
    errors: list[IngestItemError] = []
    valid: dict[str, Event] = {}  # event_id -> Event (dedups within the batch too)

    for idx, raw in enumerate(raw_events):
        try:
            ev = Event.model_validate(raw)
        except ValidationError as e:
            errors.append(IngestItemError(
                index=idx,
                event_id=str(raw.get("event_id")) if isinstance(raw, dict) else None,
                error="; ".join(f"{'.'.join(str(p) for p in er['loc'])}: {er['msg']}"
                                for er in e.errors()[:5]),
            ))
            continue
        valid[str(ev.event_id)] = ev  # last-wins on intra-batch dupe id

    received = len(raw_events)
    rejected = len(errors)
    duplicates = 0
    accepted = 0

    if valid:
        with session_scope() as s:
            existing = set(
                s.scalars(select(EventRow.event_id).where(
                    EventRow.event_id.in_(list(valid.keys())))).all()
            )
            to_insert = []
            for eid, ev in valid.items():
                if eid in existing:
                    duplicates += 1
                else:
                    to_insert.append(_to_row(ev))
            if to_insert:
                _conflict_safe_insert(s, to_insert)
                accepted = len(to_insert)

    if accepted:
        EVENTS_INGESTED.inc(accepted)
    return IngestResponse(
        received=received,
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        errors=errors,
    )
