"""POS transaction loading + visitor->purchase correlation.

POS has no customer identity. A visitor is 'converted' if they were in the
BILLING zone within `conversion_window_min` minutes BEFORE a transaction
timestamp for the same store (per the problem statement).
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .db import PosRow, session_scope


def _parse_ts(s: str) -> datetime:
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_pos_csv(path: str | Path) -> int:
    """Load POS rows into the DB (idempotent by transaction_id). Returns rows added."""
    p = Path(path)
    if not p.exists():
        return 0
    added = 0
    with session_scope() as s:
        existing = set(s.scalars(select(PosRow.transaction_id)).all())
        with p.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = (row.get("transaction_id") or "").strip()
                if not tid or tid in existing:
                    continue
                try:
                    s.add(PosRow(
                        transaction_id=tid,
                        store_id=(row.get("store_id") or "").strip(),
                        ts=_parse_ts(row["timestamp"]),
                        basket_value_inr=float(row.get("basket_value_inr") or 0),
                    ))
                    existing.add(tid)
                    added += 1
                except Exception:
                    continue
    return added
