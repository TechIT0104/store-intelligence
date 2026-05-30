"""Structured JSON logging + request middleware.

Every request logs exactly the fields the rubric (Part C) asks for:
  trace_id, store_id, endpoint, latency_ms, event_count, status_code
"""
from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# request-scoped context so any log line within a request carries the trace id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
event_count_var: ContextVar[int] = ContextVar("event_count", default=0)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


logger = logging.getLogger("storeiq")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex[:12]
        trace_id_var.set(trace_id)
        event_count_var.set(0)
        # store_id from path if present
        store_id = request.path_params.get("id") if request.path_params else None
        if store_id is None and "/stores/" in request.url.path:
            try:
                store_id = request.url.path.split("/stores/")[1].split("/")[0]
            except Exception:
                store_id = None

        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_s = time.perf_counter() - start
            latency_ms = round(latency_s * 1000, 2)
            try:
                from .observability import record_request
                record_request(request.url.path, request.method, status_code, latency_s)
            except Exception:
                pass
            logger.info(
                "request",
                extra={
                    "trace_id": trace_id,
                    "store_id": store_id,
                    "endpoint": request.url.path,
                    "method": request.method,
                    "latency_ms": latency_ms,
                    "event_count": event_count_var.get(),
                    "status_code": status_code,
                },
            )
            # surface the trace id to the caller for correlation
            try:
                response.headers["x-trace-id"] = trace_id  # type: ignore[name-defined]
            except Exception:
                pass
