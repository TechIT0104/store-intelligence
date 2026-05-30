# PROMPT: "Write pytest tests for an optional security layer that must be OFF by default
#   (so an unauthenticated scoring harness still works) but enforce X-API-Key auth on the
#   ingest write path and per-IP rate limiting when configured via env. Also assert
#   security headers are always present."
# CHANGES MADE: Added the 'off by default' assertions first (the model only tested the
#   enabled paths), and reset the settings lru_cache after mutating env so the per-request
#   settings lookup actually sees the new config.
from __future__ import annotations

import os

from app import config
from tests.conftest import make_event


def _set(**env):
    for k, v in env.items():
        os.environ[k] = str(v)
    config.get_settings.cache_clear()


def _clear(*keys):
    for k in keys:
        os.environ.pop(k, None)
    config.get_settings.cache_clear()


def test_security_headers_always_present(client):
    r = client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_auth_off_by_default(client):
    _clear("API_KEY")
    ev = make_event("VIS_s", "ENTRY", 0, camera_id="CAM_ENTRY_01")
    r = client.post("/events/ingest", json={"events": [ev]})
    assert r.status_code == 200  # no key required


def test_auth_enforced_when_configured(client):
    _set(API_KEY="secret123")
    try:
        ev = make_event("VIS_s2", "ENTRY", 0, camera_id="CAM_ENTRY_01")
        # missing key -> 401
        r = client.post("/events/ingest", json={"events": [ev]})
        assert r.status_code == 401
        # correct key -> 200
        r = client.post("/events/ingest", json={"events": [ev]},
                        headers={"X-API-Key": "secret123"})
        assert r.status_code == 200
    finally:
        _clear("API_KEY")


def test_rate_limit_when_configured(client):
    _set(RATE_LIMIT_PER_MIN=3)
    try:
        codes = [client.get("/stores/STORE_BLR_002/metrics").status_code for _ in range(6)]
        assert 429 in codes  # budget exceeded within the window
    finally:
        _clear("RATE_LIMIT_PER_MIN")
