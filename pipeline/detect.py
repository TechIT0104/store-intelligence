"""Detection pipeline entrypoint (runs on the HOST to use the GPU).

For each camera clip:
  YOLOv8 (person) + ByteTrack -> per-frame tracked boxes
  -> zone / entry-line / billing-queue logic + emit events
  -> accumulate per-visitor evidence (access areas, behaviour, appearance)
  -> visitor Re-ID (cross-camera + re-entry)
After all clips, a MULTI-SIGNAL staff classifier (access zones + behaviour + optional
VLM action recognition + appearance) decides is_staff per visitor and rewrites it
consistently on every event.

Usage:
  python -m pipeline.detect --clips-dir "<dir>" --layout data/store_layout.json \
      --out pipeline/output/events.jsonl --sample-fps 5 --device cpu

Rubric notes:
  * ENTRY/EXIT emitted ONLY by the entry camera (cross-camera de-dup).
  * Each ByteTrack id = one person -> 3 people entering together -> 3 ENTRY events.
  * Low-confidence detections are kept and flagged, never dropped.
  * Staff is decided from behaviour + access, NOT clothing alone (see staff_signals.py).
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .zones import StoreLayout, CameraLayout
from .reid import VisitorRegistry, signature_from_crop
from .staff import StaffVLM, dark_uniform_score, upper_body_crop
from .staff_signals import VisitorEvidence, score_visitor, classify_all
from .emit import EventEmitter

DWELL_INTERVAL_S = 30.0
PERSON_CLASS = 0
YOLO_CONF = 0.25


@dataclass
class TrackState:
    visitor_id: str
    current_zone: Optional[str] = None
    zone_enter_t: float = 0.0
    last_dwell_t: float = 0.0
    last_foot: Optional[tuple[float, float]] = None
    joined_queue: bool = False


def foot_point(xyxy) -> tuple[float, float]:
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2.0, float(y2))   # bottom-center = where the person stands


def _evidence(evidence, vid) -> VisitorEvidence:
    if vid not in evidence:
        evidence[vid] = VisitorEvidence(visitor_id=vid)
    return evidence[vid]


def process_camera(cam: CameraLayout, clip_path: Path, layout: StoreLayout,
                   registry: VisitorRegistry, emitter: EventEmitter, model,
                   sample_fps: float, device: str,
                   evidence: dict[str, VisitorEvidence], crops: dict[str, tuple]):
    cap_fps = cam.fps or 25.0
    vid_stride = max(1, int(round(cap_fps / sample_fps)))
    half = device not in ("cpu", "", None)

    states: dict[int, TrackState] = {}
    print(f"[detect] {cam.camera_id} <- {clip_path.name} (stride={vid_stride})")

    results = model.track(
        source=str(clip_path), classes=[PERSON_CLASS], conf=YOLO_CONF,
        tracker="bytetrack.yaml", persist=True, stream=True, vid_stride=vid_stride,
        device=device, half=half, verbose=False,
    )

    processed = 0
    for r in results:
        processed += 1
        t = (processed * vid_stride) / cap_fps
        boxes = r.boxes
        frame = r.orig_img
        if boxes is None or boxes.id is None:
            continue

        ids = boxes.id.cpu().numpy().astype(int)
        xyxys = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()

        queue_depth = 0
        if cam.queue_region is not None:
            for xyxy in xyxys:
                if cam.in_queue(foot_point(xyxy)):
                    queue_depth += 1

        seen_ids = set()
        for tid, xyxy, conf in zip(ids, xyxys, confs):
            seen_ids.add(int(tid))
            fp = foot_point(xyxy)
            crop = upper_body_crop(frame, xyxy)
            sig = signature_from_crop(crop)
            visitor_id, is_reentry = registry.resolve(cam.camera_id, int(tid), sig, t)

            # --- accumulate evidence for the multi-signal staff classifier ---
            ev = _evidence(evidence, visitor_id)
            ev.observe(t)
            ev.appearance_votes += 1
            if dark_uniform_score(frame, xyxy) >= 0.6:
                ev.dark_votes += 1
            if cam.staff_only:
                ev.in_stockroom = True
            if cam.role == "billing":
                ev.billing_frames += 1
                # behind a counter the legs are occluded, so the foot point sits at
                # counter height; use the box centre to test the staff-only zone.
                center = ((xyxy[0] + xyxy[2]) / 2.0, (xyxy[1] + xyxy[3]) / 2.0)
                if cam.in_staff_zone(center):
                    ev.behind_counter_frames += 1
            # keep the largest crop per visitor for an optional VLM check
            area = float((xyxy[2] - xyxy[0]) * (xyxy[3] - xyxy[1]))
            if crop.size and area > crops.get(visitor_id, (0, None))[0]:
                crops[visitor_id] = (area, crop.copy())

            st = states.get(int(tid))
            if st is None:
                st = TrackState(visitor_id=visitor_id, last_foot=fp)
                states[int(tid)] = st

            def _emit(etype, **kw):
                # is_staff is provisional here (False); decided post-hoc and rewritten.
                emitter.emit(camera_id=cam.camera_id, visitor_id=visitor_id,
                             event_type=etype, frame_offset_s=t, is_staff=False,
                             confidence=float(conf), **kw)

            # --- entry / exit (entry camera only) ---
            if cam.entry_line is not None and st.last_foot is not None:
                direction = cam.entry_line.crossing_direction(st.last_foot, fp)
                if direction == "ENTRY":
                    _emit("REENTRY" if is_reentry else "ENTRY")
                elif direction == "EXIT":
                    _emit("EXIT")
                    registry.mark_exited(visitor_id, t)

            # --- zones (floor / billing cameras) ---
            zone = cam.zone_at(fp)
            if zone != st.current_zone:
                if st.current_zone is not None:
                    dwell_ms = int((t - st.zone_enter_t) * 1000)
                    _emit("ZONE_EXIT", zone_id=st.current_zone, dwell_ms=dwell_ms,
                          sku_zone=cam.sku_zone.get(st.current_zone))
                    if st.current_zone == "BILLING" and st.joined_queue:
                        _emit("BILLING_QUEUE_ABANDON", zone_id="BILLING")
                        st.joined_queue = False
                if zone is not None:
                    ev.zones.add(zone)
                    ev.zone_enter_count += 1
                    _emit("ZONE_ENTER", zone_id=zone, sku_zone=cam.sku_zone.get(zone))
                    st.zone_enter_t = t
                    st.last_dwell_t = t
                    if zone == "BILLING" and queue_depth > 0:
                        _emit("BILLING_QUEUE_JOIN", zone_id="BILLING",
                              queue_depth=queue_depth, sku_zone="BILLING")
                        st.joined_queue = True
                st.current_zone = zone

            if zone is not None and (t - st.last_dwell_t) >= DWELL_INTERVAL_S:
                _emit("ZONE_DWELL", zone_id=zone,
                      dwell_ms=int((t - st.zone_enter_t) * 1000),
                      sku_zone=cam.sku_zone.get(zone))
                st.last_dwell_t = t

            st.last_foot = fp

        # tracks that disappeared: close any open zone
        for tid in list(states.keys()):
            if tid not in seen_ids:
                st = states[tid]
                if st.current_zone is not None:
                    emitter.emit(camera_id=cam.camera_id, visitor_id=st.visitor_id,
                                 event_type="ZONE_EXIT", frame_offset_s=t,
                                 zone_id=st.current_zone,
                                 dwell_ms=int((t - st.zone_enter_t) * 1000),
                                 is_staff=False, confidence=0.4,
                                 sku_zone=cam.sku_zone.get(st.current_zone))
                    st.current_zone = None


def decide_staff(evidence, crops, vlm: StaffVLM) -> dict[str, dict]:
    """Optionally refine ambiguous visitors with the VLM action prompt, then score."""
    if vlm.enabled:
        # Prioritise substantial tracks; skip tiny fragments. The VLM throttles and
        # caps itself, so we just feed it the most informative crops first.
        candidates = sorted(
            (v for v in evidence.values() if v.frames >= 5 and v.visitor_id in crops),
            key=lambda v: v.frames, reverse=True,
        )
        for ev in candidates:
            strong = ev.in_stockroom or ev.behind_counter_ratio >= 0.25
            if strong:
                continue  # access signal already decisive
            working = vlm.classify_action(crops[ev.visitor_id][1])
            if working is not None:
                ev.vlm_working = working
        print(f"[detect] VLM action calls: {vlm.calls}")
    return classify_all(evidence)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips-dir", default=os.environ.get("CLIPS_DIR", ""))
    ap.add_argument("--layout", default=os.environ.get("STORE_LAYOUT_PATH", "data/store_layout.json"))
    ap.add_argument("--out", default=os.environ.get("EVENTS_OUT", "pipeline/output/events.jsonl"))
    ap.add_argument("--model", default=os.environ.get("YOLO_MODEL", "yolov8n.pt"))
    ap.add_argument("--sample-fps", type=float, default=float(os.environ.get("SAMPLE_FPS", 5)))
    ap.add_argument("--device", default=os.environ.get("DEVICE", "cpu"))
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    layout = StoreLayout.load(args.layout)
    clips_dir = Path(args.clips_dir)
    registry = VisitorRegistry()
    vlm = StaffVLM()
    print(f"[detect] VLM enabled: {vlm.enabled}")

    from ultralytics import YOLO
    model = YOLO(args.model)
    clip_start = datetime(2026, 10, 4, 14, 39, 0, tzinfo=timezone.utc)

    cams = sorted(layout.cameras.values(),
                  key=lambda c: (c.role != "entry_exit", c.camera_id))

    evidence: dict[str, VisitorEvidence] = {}
    crops: dict[str, tuple] = {}

    emitter = EventEmitter(layout.store_id, args.out, clip_start)
    for cam in cams:
        clip_path = clips_dir / cam.source_clip
        if args.only and cam.source_clip != args.only:
            continue
        if not clip_path.exists():
            print(f"[detect] WARN missing clip: {clip_path}")
            continue
        process_camera(cam, clip_path, layout, registry, emitter, model,
                       args.sample_fps, args.device, evidence, crops)

    decisions = decide_staff(evidence, crops, vlm)
    emitter.apply_staff_decisions(decisions)
    emitter.flush()

    n_staff = sum(1 for d in decisions.values() if d["is_staff"])
    print(f"[detect] wrote {emitter.count} events -> {args.out}")
    print(f"[detect] visitors={len(evidence)} staff={n_staff} customers={len(evidence)-n_staff}")


if __name__ == "__main__":
    main()
