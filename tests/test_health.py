# PROMPT: "Write pytest tests for a /health endpoint that reports per-store last event
#   time and an ingest-based STALE_FEED flag, and for graceful degradation: when the DB
#   is unavailable, endpoints must return HTTP 503 with a structured body, not a stack
#   trace."
# CHANGES MADE: The model checked DB-down by pointing the engine at a bad URL, which the
#   app's startup re-initialised back to SQLite; switched to monkeypatching the request's
#   session_scope to raise DBUnavailable, which actually exercises the 503 handler.
from __future__ import annotations

from app.db import DBUnavailable
from tests.conftest import make_event, seed_events


def test_health_empty_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["stores"] == []


def test_health_reports_store_and_fresh_feed(client):
    seed_events([make_event("VIS_h", "ENTRY", 0, camera_id="CAM_ENTRY_01")])
    r = client.get("/health")
    body = r.json()
    store = next(s for s in body["stores"] if s["store_id"] == "STORE_BLR_002")
    assert store["events"] == 1
    assert store["last_event_ts"] is not None
    # just ingested -> not stale
    assert store["feed"] == "OK"
    assert body["stale_feed"] is False


def test_db_unavailable_returns_503(client, monkeypatch):
    def boom():
        raise DBUnavailable("simulated outage")

    # endpoint does `with session_scope() as s:` -> raising on call hits the handler
    monkeypatch.setattr("app.main.session_scope", boom)
    r = client.get("/stores/STORE_BLR_002/metrics")
    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "database_unavailable"
    assert "trace_id" in body
    assert "Traceback" not in r.text  # no raw stack trace leaked
