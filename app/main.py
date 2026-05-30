"""FastAPI entrypoint — wires endpoints, middleware, startup, error handling.

Acceptance gate: `docker compose up` starts this; GET /stores/STORE_BLR_002/metrics
returns valid JSON; POST /events/ingest never 5xx on malformed input (partial success).
"""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .security import (RateLimitMiddleware, SecurityHeadersMiddleware,
                       require_api_key)
from .stream import event_stream

from .anomalies import detect_anomalies
from .config import get_settings
from .db import DBUnavailable, create_all, init_engine, session_scope
from .funnel import compute_funnel
from .health import health_report
from .ingestion import ingest_events
from .logging_conf import (RequestLoggingMiddleware, configure_logging,
                           event_count_var, trace_id_var)
from .metrics import compute_heatmap, compute_metrics
from .pos import load_pos_csv

log = logging.getLogger("storeiq.api")

app = FastAPI(title="Apex Retail — Store Intelligence API", version="1.0.0")

_cors = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_cors or ["*"], allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


class RawIngestBatch(BaseModel):
    # raw dicts so we can validate per-item and return partial success
    events: list[dict] = Field(min_length=1, max_length=500)


@app.on_event("startup")
def _startup():
    cfg = get_settings()
    configure_logging(cfg.log_level)
    init_engine(cfg.database_url)
    try:
        create_all()
        added = load_pos_csv(cfg.pos_csv_path)
        log.info("startup complete", extra={"pos_rows_loaded": added})
    except Exception as e:  # never crash the app on startup data issues
        log.warning("startup data load skipped: %s", e)


# ---- error handlers: structured bodies, no raw stack traces ----

@app.exception_handler(DBUnavailable)
async def _db_unavailable(request, exc: DBUnavailable):
    return JSONResponse(
        status_code=503,
        content={"error": "database_unavailable",
                 "detail": "The database is temporarily unreachable. Retry shortly.",
                 "trace_id": trace_id_var.get()},
    )


@app.exception_handler(Exception)
async def _unhandled(request, exc: Exception):
    log.exception("unhandled error", extra={"trace_id": trace_id_var.get()})
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An unexpected error occurred.",
                 "trace_id": trace_id_var.get()},
    )


# ---- endpoints ----

@app.get("/")
def root():
    return {"service": "store-intelligence", "version": "1.0.0",
            "endpoints": ["/events/ingest", "/stores/{id}/metrics", "/stores/{id}/funnel",
                          "/stores/{id}/heatmap", "/stores/{id}/anomalies", "/health"]}


@app.post("/events/ingest")
def ingest(batch: RawIngestBatch, _=Depends(require_api_key)):
    event_count_var.set(len(batch.events))
    result = ingest_events(batch.events)
    # partial success is still a 200/207; full validity -> 200
    status = 200 if result.rejected == 0 else 207
    return JSONResponse(status_code=status, content=result.model_dump())


@app.get("/stores/{id}/metrics")
def metrics(id: str):
    with session_scope() as s:
        return compute_metrics(s, id)


@app.get("/stores/{id}/funnel")
def funnel(id: str):
    with session_scope() as s:
        return compute_funnel(s, id)


@app.get("/stores/{id}/heatmap")
def heatmap(id: str):
    with session_scope() as s:
        return compute_heatmap(s, id)


@app.get("/stores/{id}/anomalies")
def anomalies(id: str):
    with session_scope() as s:
        return detect_anomalies(s, id)


@app.get("/health")
def health():
    return health_report()


@app.get("/stream/{store_id}")
def stream(store_id: str):
    return StreamingResponse(
        event_stream(store_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
