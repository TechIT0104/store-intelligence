"""Event emission — builds schema-compliant events, buffers them, then flushes.

We buffer events in memory (a clip yields only a few hundred) so that the
multi-signal staff classifier can run AFTER the whole clip is processed and
rewrite `is_staff` consistently across every event of a visitor. The emitter owns:
  - global uniqueness of event_id (uuid4)
  - per-visitor session_seq counter
  - timestamp derivation from clip start + frame offset
  - final JSONL serialisation (one event per line)
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


class EventEmitter:
    def __init__(self, store_id: str, out_path: str | Path, clip_start: datetime):
        self.store_id = store_id
        self.clip_start = clip_start.astimezone(timezone.utc)
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self._seq: dict[str, int] = defaultdict(int)
        self.events: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.flush()

    @property
    def count(self) -> int:
        return len(self.events)

    def _ts(self, frame_offset_s: float) -> str:
        t = self.clip_start + timedelta(seconds=frame_offset_s)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    def emit(self, *, camera_id: str, visitor_id: str, event_type: str,
             frame_offset_s: float, zone_id: Optional[str] = None,
             dwell_ms: int = 0, is_staff: bool = False, confidence: float = 0.9,
             queue_depth: Optional[int] = None, sku_zone: Optional[str] = None) -> dict:
        self._seq[visitor_id] += 1
        event = {
            "event_id": str(uuid.uuid4()),
            "store_id": self.store_id,
            "camera_id": camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp": self._ts(frame_offset_s),
            "zone_id": zone_id,
            "dwell_ms": int(dwell_ms),
            "is_staff": bool(is_staff),
            "confidence": round(float(confidence), 3),
            "metadata": {
                "queue_depth": queue_depth,
                "sku_zone": sku_zone if sku_zone is not None else zone_id,
                "session_seq": self._seq[visitor_id],
            },
        }
        self.events.append(event)
        return event

    def apply_staff_decisions(self, decisions: dict[str, dict]) -> None:
        """Rewrite is_staff (+ reasons) on every event using per-visitor decisions."""
        for ev in self.events:
            d = decisions.get(ev["visitor_id"])
            if d is None:
                continue
            ev["is_staff"] = bool(d["is_staff"])
            ev["metadata"]["staff_reasons"] = d.get("reasons", [])
            if d["is_staff"]:
                ev["metadata"]["staff_confidence"] = d.get("confidence")

    def flush(self) -> None:
        with self.out_path.open("w", encoding="utf-8") as fh:
            for ev in self.events:
                fh.write(json.dumps(ev) + "\n")
