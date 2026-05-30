"""Server-Sent Events stream for the live dashboard.

Subscribes to the Redis channel the replayer publishes to and forwards each
message to the browser as SSE. Kept resilient: if Redis is down, it emits a
single error event and ends rather than crashing the worker.
"""
from __future__ import annotations

import json
import os
import time
from typing import Iterator

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def event_stream(store_id: str) -> Iterator[str]:
    channel = f"events:{store_id}"
    try:
        import redis
        r = redis.from_url(REDIS_URL, socket_connect_timeout=3)
        pubsub = r.pubsub()
        pubsub.subscribe(channel)
        yield "event: hello\ndata: connected\n\n"
        last_ping = time.time()
        for msg in pubsub.listen():
            if msg.get("type") == "message":
                data = msg["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"
            now = time.time()
            if now - last_ping > 15:
                yield ": keep-alive\n\n"
                last_ping = now
    except Exception as e:
        yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
