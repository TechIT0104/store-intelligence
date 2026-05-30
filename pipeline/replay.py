"""Replayer — bridges the offline detection pipeline to the live API.

Runs inside Docker (`replayer` service). Reads the events the host pipeline
produced (pipeline/output/events.jsonl), and streams them into the API in
simulated real time, ordered by timestamp. Each delivered batch is also
published to a Redis channel so the dashboard can update live.

If events.jsonl is absent (detection not run yet), it falls back to the bundled
data/sample_events.jsonl so `docker compose up` always demonstrates a live feed.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

API_URL = os.environ.get("API_URL", "http://api:8000")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
EVENTS_PATH = os.environ.get("EVENTS_PATH", "/app/pipeline/output/events.jsonl")
FALLBACK_PATH = os.environ.get("FALLBACK_PATH", "/app/data/sample_events.jsonl")
REPLAY_SPEED = float(os.environ.get("REPLAY_SPEED", "20"))  # x real time
BATCH_MAX = 100
CHANNEL = "events:STORE_BLR_002"


def _load_events() -> list[dict]:
    path = Path(EVENTS_PATH)
    if not path.exists() or path.stat().st_size == 0:
        print(f"[replay] {EVENTS_PATH} empty -> falling back to {FALLBACK_PATH}")
        path = Path(FALLBACK_PATH)
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    events.sort(key=lambda e: e["timestamp"])
    print(f"[replay] loaded {len(events)} events from {path}")
    return events


def _wait_for_api():
    for _ in range(60):
        try:
            r = requests.get(f"{API_URL}/health", timeout=2)
            if r.status_code < 500:
                print("[replay] API is up")
                return
        except Exception:
            pass
        time.sleep(2)
    print("[replay] WARN: API never became healthy; proceeding anyway")


def _connect_redis():
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        r.ping()
        return r
    except Exception as e:
        print(f"[replay] redis unavailable ({e}); dashboard pub disabled")
        return None


def _post(batch: list[dict]) -> None:
    try:
        resp = requests.post(f"{API_URL}/events/ingest", json={"events": batch}, timeout=10)
        print(f"[replay] ingested {len(batch)} -> {resp.status_code} {resp.text[:120]}")
    except Exception as e:
        print(f"[replay] ingest failed: {e}")


def main():
    _wait_for_api()
    r = _connect_redis()
    events = _load_events()
    if not events:
        print("[replay] no events to replay")
        return

    def ts(e):
        return datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))

    t0 = ts(events[0])
    wall0 = time.time()
    batch: list[dict] = []
    batch_anchor = t0

    for e in events:
        # pace delivery to (event_time - t0) / speed
        target = (ts(e) - t0).total_seconds() / max(REPLAY_SPEED, 0.01)
        elapsed = time.time() - wall0
        if target > elapsed:
            time.sleep(min(target - elapsed, 5.0))

        batch.append(e)
        crossed_window = (ts(e) - batch_anchor).total_seconds() / max(REPLAY_SPEED, 0.01) > 1.0
        if len(batch) >= BATCH_MAX or crossed_window:
            _post(batch)
            if r is not None:
                r.publish(CHANNEL, json.dumps({"n": len(batch), "last": batch[-1]}))
            batch = []
            batch_anchor = ts(e)

    if batch:
        _post(batch)
        if r is not None:
            r.publish(CHANNEL, json.dumps({"n": len(batch), "last": batch[-1]}))
    print("[replay] done")


if __name__ == "__main__":
    main()
