"""Runtime configuration (env-driven, 12-factor)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage. Default to SQLite so the API and tests run with zero infra;
    # docker-compose overrides this with Postgres.
    database_url: str = "sqlite:///./storeiq.db"
    redis_url: str = "redis://localhost:6379/0"

    store_layout_path: str = "data/store_layout.json"
    pos_csv_path: str = "data/pos_transactions.csv"

    log_level: str = "INFO"

    # --- security (gate-safe defaults: OFF unless explicitly configured) ---
    api_key: str = ""                 # if set, write endpoints require X-API-Key
    rate_limit_per_min: int = 0       # if > 0, per-IP request budget per minute
    cors_origins: str = "*"           # comma-separated allowed origins

    # Business windows / thresholds (documented in CHOICES.md).
    conversion_window_min: int = 5        # billing-visit -> POS correlation window
    metrics_window_hours: int = 24        # "today" rolling window anchored to latest event
    dead_zone_minutes: int = 30           # no visits in a zone -> dead-zone anomaly
    stale_feed_minutes: int = 10          # no events from a store -> STALE_FEED
    queue_spike_depth: int = 5            # queue_depth >= this -> queue spike
    conversion_drop_pct: float = 30.0     # drop vs 7-day avg (% relative) -> anomaly
    heatmap_min_sessions: int = 20        # below this -> data_confidence=low


@lru_cache
def get_settings() -> Settings:
    return Settings()
