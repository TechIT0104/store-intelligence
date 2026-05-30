# PROMPT: "Write pytest tests for POS CSV loading (idempotent by transaction_id) and for
#   the replayer's event loading + timestamp ordering and its fallback to the bundled
#   sample_events.jsonl when no detection output exists."
# CHANGES MADE: Added the idempotency assertion (loading the same CSV twice adds 0 the
#   second time) which the model omitted, and tested the fallback path explicitly by
#   pointing EVENTS_PATH at a missing file.
from __future__ import annotations

import json

from app.db import PosRow, session_scope
from app.pos import load_pos_csv


def test_load_pos_csv_idempotent(tmp_path):
    csv = tmp_path / "pos.csv"
    csv.write_text(
        "store_id,transaction_id,timestamp,basket_value_inr\n"
        "STORE_BLR_002,TXN_1,2026-10-04T14:40:00Z,1240.00\n"
        "STORE_BLR_002,TXN_2,2026-10-04T14:41:00Z,680.00\n",
        encoding="utf-8",
    )
    assert load_pos_csv(csv) == 2
    assert load_pos_csv(csv) == 0  # idempotent re-load
    with session_scope() as s:
        assert s.query(PosRow).count() == 2


def test_load_pos_missing_file_is_noop(tmp_path):
    assert load_pos_csv(tmp_path / "nope.csv") == 0


def test_replay_loads_and_sorts(tmp_path, monkeypatch):
    import pipeline.replay as replay
    f = tmp_path / "events.jsonl"
    lines = [
        {"event_id": "b", "timestamp": "2026-10-04T14:40:05Z"},
        {"event_id": "a", "timestamp": "2026-10-04T14:40:01Z"},
    ]
    f.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    monkeypatch.setattr(replay, "EVENTS_PATH", str(f))
    events = replay._load_events()
    assert [e["event_id"] for e in events] == ["a", "b"]  # sorted by timestamp


def test_replay_fallback_to_sample(tmp_path, monkeypatch):
    import pipeline.replay as replay
    monkeypatch.setattr(replay, "EVENTS_PATH", str(tmp_path / "missing.jsonl"))
    monkeypatch.setattr(replay, "FALLBACK_PATH", "data/sample_events.jsonl")
    events = replay._load_events()
    assert len(events) > 0  # used the bundled sample
