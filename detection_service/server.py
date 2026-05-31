"""Detection microservice — the deployed model.

Runs YOLOv8 + ByteTrack INSIDE a container (CPU). Accepts an uploaded video,
detects/tracks people, classifies staff, emits schema-compliant events, posts them
to the intelligence API, and publishes live progress to Redis. This makes the
system genuinely interactive: upload a clip -> the deployed model produces output
that flows onto the live dashboard.

Endpoints:
  POST /jobs        multipart 'file' (+ store_id, camera_id, sample_fps) -> job_id
  GET  /jobs/{id}   job status / results
  GET  /jobs        recent jobs
  GET  /health
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from pipeline.detect import decide_staff, process_camera
from pipeline.emit import EventEmitter
from pipeline.reid import VisitorRegistry
from pipeline.staff import StaffVLM
from pipeline.zones import StoreLayout

API_URL = os.environ.get("API_URL", "http://api:8000")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
LAYOUT_PATH = os.environ.get("STORE_LAYOUT_PATH", "/app/data/store_layout.json")
YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")
DEVICE = os.environ.get("DEVICE", "cpu")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# uploaded-clip events are anchored to the dataset's clip time so they land in the
# dashboard's day window (store ST1008, 10-Apr-2026 ~20:09 IST = 14:39 UTC).
CLIP_BASE = datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)

app = FastAPI(title="Detection Service")
layout = StoreLayout.load(LAYOUT_PATH)
jobs: dict[str, dict] = {}
_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            from ultralytics import YOLO
            _model = YOLO(YOLO_MODEL)
    return _model


def _redis():
    try:
        import redis
        r = redis.from_url(REDIS_URL, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "_video"}


def run_job(job_id: str, video_path: Path, store_id: str, camera_id: str, sample_fps: float):
    import json
    job = jobs[job_id]
    r = _redis()

    def publish():
        if r:
            try:
                r.publish(f"detect:{job_id}", json.dumps(_public(job)))
            except Exception:
                pass

    try:
        job.update(state="detecting", frames=0)
        publish()
        cam = layout.cameras.get(camera_id) or next(iter(layout.cameras.values()))
        registry, vlm = VisitorRegistry(), StaffVLM()
        emitter = EventEmitter(store_id, UPLOAD_DIR / f"{job_id}.jsonl", CLIP_BASE)
        evidence: dict = {}
        crops: dict = {}

        def prog(n):
            job["frames"] = n
            if n % 15 == 0:
                publish()

        process_camera(cam, video_path, layout, registry, emitter, get_model(),
                       sample_fps, DEVICE, evidence, crops, None, prog)

        decisions = decide_staff(evidence, crops, vlm)
        emitter.apply_staff_decisions(decisions)
        events = emitter.events

        # results summary
        job["events_total"] = len(events)
        job["entry"] = sum(1 for e in events if e["event_type"] == "ENTRY")
        job["exit"] = sum(1 for e in events if e["event_type"] == "EXIT")
        job["visitors"] = len(decisions)
        job["staff"] = sum(1 for d in decisions.values() if d["is_staff"])
        zones: dict[str, int] = {}
        for e in events:
            if e["event_type"] == "ZONE_ENTER" and e["zone_id"]:
                zones[e["zone_id"]] = zones.get(e["zone_id"], 0) + 1
        job["zones"] = zones

        # stream events to the API (sim-realtime so the dashboard animates)
        job.update(state="streaming", events_posted=0)
        publish()
        batch = []
        for e in events:
            batch.append(e)
            if len(batch) >= 50:
                _post(batch, store_id, r)
                job["events_posted"] += len(batch)
                batch = []
                publish()
                time.sleep(0.25)
        if batch:
            _post(batch, store_id, r)
            job["events_posted"] += len(batch)

        job.update(state="done", finished_at=time.time())
        publish()
    except Exception as ex:  # never crash the worker
        job.update(state="error", error=str(ex))
        publish()
    finally:
        try:
            video_path.unlink(missing_ok=True)
        except Exception:
            pass


def _post(batch, store_id, r):
    import json
    try:
        requests.post(f"{API_URL}/events/ingest", json={"events": batch}, timeout=15)
    except Exception:
        pass
    if r:  # also feed the main live event ticker
        try:
            r.publish(f"events:{store_id}", json.dumps({"n": len(batch), "last": batch[-1]}))
        except Exception:
            pass


@app.get("/health")
def health():
    return {"status": "ok", "model": YOLO_MODEL, "device": DEVICE,
            "cameras": list(layout.cameras), "active_jobs": len(jobs)}


@app.get("/cameras")
def cameras():
    return {"store_id": layout.store_id,
            "cameras": [{"camera_id": c.camera_id, "role": c.role,
                         "zones": list(c.zones)} for c in layout.cameras.values()]}


@app.post("/jobs")
async def create_job(file: UploadFile = File(...), store_id: str = Form("ST1008"),
                     camera_id: str = Form("CAM_FLOOR_02"), sample_fps: float = Form(5.0)):
    job_id = "job_" + uuid.uuid4().hex[:8]
    dest = UPLOAD_DIR / f"{job_id}_{file.filename}"
    with dest.open("wb") as f:
        f.write(await file.read())
    jobs[job_id] = {"job_id": job_id, "state": "queued", "filename": file.filename,
                    "store_id": store_id, "camera_id": camera_id,
                    "frames": 0, "events_posted": 0, "created_at": time.time()}
    threading.Thread(target=run_job,
                     args=(job_id, dest, store_id, camera_id, sample_fps),
                     daemon=True).start()
    return JSONResponse(status_code=202, content=_public(jobs[job_id]))


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "unknown job"})
    return _public(job)


@app.get("/jobs")
def list_jobs():
    return {"jobs": [_public(j) for j in sorted(jobs.values(),
                     key=lambda x: x["created_at"], reverse=True)[:20]]}
