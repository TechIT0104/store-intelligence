"""Event ingestion: per-item validation, dedup, partial success.

POST /events/ingest must:
  - accept up to 500 events
  - validate each independently (one bad event must not reject the batch)
  - be idempotent by event_id (re-posting the same payload is a no-op)
  - return a structured summary: received / accepted / duplicates / rejected + errors
"""
from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import select

from .db import EventRow, session_scope
from .models import Event, IngestItemError, IngestResponse


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
                s.add_all(to_insert)
                accepted = len(to_insert)

    return IngestResponse(
        received=received,
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        errors=errors,
    )
