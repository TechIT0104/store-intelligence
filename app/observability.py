"""Prometheus metrics. Exposed at GET /metrics for scraping.

Kept tiny and dependency-light. The request counter/latency histogram are recorded
by the logging middleware; ingest volume is incremented by the ingestion module.
"""
from __future__ import annotations

from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Histogram,
                               generate_latest)

REQUESTS = Counter(
    "storeiq_requests_total", "HTTP requests", ["endpoint", "method", "status"]
)
LATENCY = Histogram(
    "storeiq_request_latency_seconds", "Request latency", ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
EVENTS_INGESTED = Counter(
    "storeiq_events_ingested_total", "Behavioural events accepted by /events/ingest"
)


def record_request(endpoint: str, method: str, status: int, latency_s: float) -> None:
    # collapse store-id path params so cardinality stays bounded
    if "/stores/" in endpoint:
        parts = endpoint.split("/")
        if len(parts) > 2:
            parts[2] = "{id}"
        endpoint = "/".join(parts)
    REQUESTS.labels(endpoint=endpoint, method=method, status=str(status)).inc()
    LATENCY.labels(endpoint=endpoint).observe(latency_s)


def render_latest() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
