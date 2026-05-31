"""Database layer — SQLAlchemy ORM + graceful-degradation helpers.

Default engine is SQLite (zero-infra dev/test). docker-compose sets DATABASE_URL
to Postgres. If the DB is unreachable, `session_scope` raises DBUnavailable which
the API maps to HTTP 503 with a structured body (no raw stack traces).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, Float, Integer, String, create_engine,
                        Index)
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import get_settings


class DBUnavailable(Exception):
    """Raised when the database cannot be reached."""


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)  # idempotency key
    store_id: Mapped[str] = mapped_column(String(64), index=True)
    camera_id: Mapped[str] = mapped_column(String(64))
    visitor_id: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    zone_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dwell_ms: Mapped[int] = mapped_column(Integer, default=0)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    queue_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sku_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_seq: Mapped[int] = mapped_column(Integer, default=0)
    # server wall-clock when this event was ingested (drives STALE_FEED on /health,
    # independent of the event's own — possibly replayed/historical — timestamp)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True,
        default=lambda: datetime.now(timezone.utc))


class PosRow(Base):
    __tablename__ = "pos_transactions"

    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    basket_value_inr: Mapped[float] = mapped_column(Float, default=0.0)


Index("ix_events_store_ts", EventRow.store_id, EventRow.ts)
Index("ix_events_store_visitor", EventRow.store_id, EventRow.visitor_id)


_engine = None
_Session = None


def init_engine(database_url: str | None = None):
    global _engine, _Session
    url = database_url or get_settings().database_url
    # Managed Postgres (e.g. Render) hands out a bare postgresql:// URL, which
    # SQLAlchemy maps to psycopg2; we ship psycopg (v3), so normalise the driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def create_all():
    if _engine is None:
        init_engine()
    Base.metadata.create_all(_engine)


def healthcheck() -> bool:
    """Return True if the DB answers a trivial query."""
    from sqlalchemy import text
    try:
        with _Session() as s:
            s.execute(text("SELECT 1"))
        return True
    except (OperationalError, DBAPIError, Exception):
        return False


@contextmanager
def session_scope():
    if _Session is None:
        init_engine()
    try:
        session = _Session()
    except (OperationalError, DBAPIError) as e:
        raise DBUnavailable(str(e))
    try:
        yield session
        session.commit()
    except (OperationalError, DBAPIError) as e:
        session.rollback()
        raise DBUnavailable(str(e))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
