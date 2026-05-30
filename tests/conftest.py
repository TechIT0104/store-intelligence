"""Shared test fixtures.

Each test runs against an isolated temp SQLite DB. We set env BEFORE importing the
app so settings pick up the test database, then reset the lru_cache.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# --- isolate DB + data paths before app import ---
_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["POS_CSV_PATH"] = os.path.join(_TMP, "nonexistent_pos.csv")  # start with no POS
os.environ["LOG_LEVEL"] = "WARNING"

from app import config  # noqa: E402
config.get_settings.cache_clear()

from app.db import (Base, PosRow, create_all, init_engine, session_scope)  # noqa: E402

BASE_TS = datetime(2026, 10, 4, 14, 39, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="function", autouse=True)
def fresh_db():
    """Recreate schema for every test for isolation."""
    eng = init_engine(os.environ["DATABASE_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


# --- builders -------------------------------------------------------------

def make_event(visitor_id: str, event_type: str, offset_s: int = 0, *,
               store_id: str = "STORE_BLR_002", camera_id: str = "CAM_FLOOR_01",
               zone_id=None, dwell_ms: int = 0, is_staff: bool = False,
               confidence: float = 0.9, queue_depth=None, sku_zone=None,
               session_seq: int = 1, event_id: str | None = None) -> dict:
    ts = (BASE_TS + timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": ts,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": {"queue_depth": queue_depth, "sku_zone": sku_zone or zone_id,
                     "session_seq": session_seq},
    }


def seed_events(events: list[dict]):
    from app.ingestion import ingest_events
    return ingest_events(events)


def seed_pos(rows: list[tuple[str, int, float]], store_id: str = "STORE_BLR_002"):
    """rows = list of (transaction_id, offset_seconds_from_BASE_TS, basket_value)."""
    with session_scope() as s:
        for tid, off, val in rows:
            s.add(PosRow(transaction_id=tid, store_id=store_id,
                         ts=BASE_TS + timedelta(seconds=off), basket_value_inr=val))
