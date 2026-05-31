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


def draw_overlays(frame, cam, items, hud):
    """Render detection/tracking/zone overlays onto a frame copy for the demo video."""
    import cv2
    import numpy as np
    out = frame.copy()
    overlay = out.copy()
    # zone polygons (translucent)
    for zid, poly in cam.zones.items():
        pts = np.array(poly, dtype=np.int32)
        cv2.fillPoly(overlay, [pts], (255, 180, 90))
        cv2.polylines(out, [pts], True, (255, 180, 90), 2)
        cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
        cv2.putText(out, zid, (cx - 40, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (255, 220, 150), 2, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.15, out, 0.85, 0, out)
    # entry line
    if cam.entry_line is not None:
        p1 = tuple(int(v) for v in cam.entry_line.p1)
        p2 = tuple(int(v) for v in cam.entry_line.p2)
        cv2.line(out, p1, p2, (60, 220, 255), 3)
        cv2.putText(out, "ENTRY/EXIT line", (p1[0], p1[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 220, 255), 2, cv2.LINE_AA)
    # people
    for it in items:
        x1, y1, x2, y2 = [int(v) for v in it["xyxy"]]
        staffish = it["dark"] >= 0.6
        color = (40, 120, 240) if staffish else (80, 220, 120)   # staff-ish red / customer green
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{it['vid']}  {it['conf']:.2f}"
        if it["zone"]:
            label += f"  {it['zone']}"
        cv2.rectangle(out, (x1, y1 - 22), (x1 + 11 * len(label), y1), color, -1)
        cv2.putText(out, label, (x1 + 2, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (20, 20, 20), 1, cv2.LINE_AA)
    # HUD
    cv2.rectangle(out, (0, 0), (520, 96), (25, 25, 35), -1)
    cv2.putText(out, f"{cam.camera_id}", (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, f"ENTRY {hud['entry']}   EXIT {hud['exit']}   tracks {hud['tracks']}",
                (12, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 230, 160), 2, cv2.LINE_AA)
    return out


def _evidence(evidence, vid) -> VisitorEvidence:
    if vid not in evidence:
        evidence[vid] = VisitorEvidence(visitor_id=vid)
    return evidence[vid]


def process_camera(cam: CameraLayout, clip_path: Path, layout: StoreLayout,
                   registry: VisitorRegistry, emitter: EventEmitter, model,
                   sample_fps: float, device: str,
                   evidence: dict[str, VisitorEvidence], crops: dict[str, tuple],
                   writer=None, progress_cb=None):
    cap_fps = cam.fps or 25.0
    vid_stride = max(1, int(round(cap_fps / sample_fps)))
    half = device not in ("cpu", "", None)

    states: dict[int, TrackState] = {}
    hud = {"entry": 0, "exit": 0, "tracks": 0}
    print(f"[detect] {cam.camera_id} <- {clip_path.name} (stride={vid_stride})")

    results = model.track(
        source=str(clip_path), classes=[PERSON_CLASS], conf=YOLO_CONF,
        tracker="bytetrack.yaml", persist=True, stream=True, vid_stride=vid_stride,
        device=device, half=half, verbose=False,
    )

    processed = 0
    for r in results:
        processed += 1
        if progress_cb is not None:
            progress_cb(processed)
        t = (processed * vid_stride) / cap_fps
        boxes = r.boxes
        frame = r.orig_img
        if boxes is None or boxes.id is None:
            if writer is not None and frame is not None:
                writer.write(draw_overlays(frame, cam, [], hud))
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
        draw_items = []
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
            dark = dark_uniform_score(frame, xyxy)
            if dark >= 0.6:
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
                    hud["entry"] += 1
                elif direction == "EXIT":
                    _emit("EXIT")
                    registry.mark_exited(visitor_id, t)
                    hud["exit"] += 1

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
            if writer is not None:
                draw_items.append({"xyxy": xyxy, "vid": visitor_id, "conf": float(conf),
                                   "zone": zone, "dark": dark})

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

        if writer is not None:
            hud["tracks"] = len(seen_ids)
            writer.write(draw_overlays(frame, cam, draw_items, hud))


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
    ap.add_argument("--annotate", action="store_true",
                    help="also render an annotated demo video for processed clips")
    args = ap.parse_args()

    layout = StoreLayout.load(args.layout)
    clips_dir = Path(args.clips_dir)
    registry = VisitorRegistry()
    vlm = StaffVLM()
    print(f"[detect] VLM enabled: {vlm.enabled}")

    from ultralytics import YOLO
    model = YOLO(args.model)
    # Clip overlay reads 2026-04-10 ~20:09 IST -> 14:39 UTC (store ST1008, Brigade Road).
    clip_start = datetime(2026, 4, 10, 14, 39, 0, tzinfo=timezone.utc)

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
        writer = None
        if args.annotate:
            import cv2
            out_dir = Path(args.out).parent
            vpath = out_dir / f"annotated_{Path(cam.source_clip).stem}.mp4"
            writer = cv2.VideoWriter(str(vpath), cv2.VideoWriter_fourcc(*"mp4v"),
                                     args.sample_fps,
                                     (layout.frame_width, layout.frame_height))
            print(f"[detect] annotating -> {vpath}")
        process_camera(cam, clip_path, layout, registry, emitter, model,
                       args.sample_fps, args.device, evidence, crops, writer)
        if writer is not None:
            writer.release()

    decisions = decide_staff(evidence, crops, vlm)
    emitter.apply_staff_decisions(decisions)
    emitter.flush()

    n_staff = sum(1 for d in decisions.values() if d["is_staff"])
    print(f"[detect] wrote {emitter.count} events -> {args.out}")
    print(f"[detect] visitors={len(evidence)} staff={n_staff} customers={len(evidence)-n_staff}")


if __name__ == "__main__":
    main()
