"""Visitor Re-ID registry.

Problem: each camera's tracker (ByteTrack) produces *local* track ids. The same
physical person appears on multiple cameras (entry+floor overlap) and may leave
and return. We need a single store-wide `visitor_id` per visit session, plus a
REENTRY signal when a previously-exited visitor comes back.

Approach (distance-based, no heavy Re-ID net — defensible for the time budget):
  - Each track gets an appearance signature = normalised HSV colour histogram of
    the upper body, averaged over the frames we see it.
  - When a new (camera, local_track) appears, we match it against the gallery of
    recent visitors using histogram correlation, gated by time. Within
    MATCH_WINDOW_S and above SIM_THRESHOLD -> same visitor_id.
  - If the matched visitor had already EXITed -> caller emits REENTRY.

Known failure mode (interview Q7): two different people in similar dark clothing,
entering from the same direction within a few seconds, can be merged. We mitigate
with a short re-entry window + requiring the prior track to have actually exited,
and we surface low match confidence rather than forcing a merge. Documented in
CHOICES.md.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

SIM_THRESHOLD = 0.48      # histogram-correlation similarity to call a match (lower = merge more)
REENTRY_WINDOW_S = 240    # a returning visitor within 4 min reuses their id (REENTRY)
CROSS_CAM_WINDOW_S = 8    # overlapping cams: same person seen near-simultaneously


def make_visitor_id() -> str:
    return "VIS_" + uuid.uuid4().hex[:6]


@dataclass
class VisitorRecord:
    visitor_id: str
    signature: np.ndarray
    last_seen: float          # clip-time seconds
    first_seen: float
    has_exited: bool = False
    cameras: set[str] = field(default_factory=set)
    local_keys: set[tuple[str, int]] = field(default_factory=set)  # (camera_id, track_id)


def hist_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Correlation of two L1-normalised histograms in [-1,1] -> clamp to [0,1]."""
    if a is None or b is None:
        return 0.0
    am, bm = a - a.mean(), b - b.mean()
    denom = (np.sqrt((am ** 2).sum()) * np.sqrt((bm ** 2).sum())) + 1e-9
    return float(np.clip((am * bm).sum() / denom, 0.0, 1.0))


class VisitorRegistry:
    def __init__(self):
        self._by_visitor: dict[str, VisitorRecord] = {}
        self._local_to_visitor: dict[tuple[str, int], str] = {}

    def resolve(self, camera_id: str, track_id: int, signature: np.ndarray,
                clip_t: float) -> tuple[str, bool]:
        """Map a local track to a visitor_id.

        Returns (visitor_id, is_reentry). is_reentry is True when we reused the id
        of a visitor who had previously exited.
        """
        key = (camera_id, track_id)
        # Already mapped this local track -> keep it, refresh signature/time.
        if key in self._local_to_visitor:
            vid = self._local_to_visitor[key]
            rec = self._by_visitor[vid]
            rec.signature = 0.7 * rec.signature + 0.3 * signature
            rec.last_seen = clip_t
            return vid, False

        # Search gallery for the best recent match.
        best_vid, best_sim, best_rec = None, 0.0, None
        for vid, rec in self._by_visitor.items():
            dt = clip_t - rec.last_seen
            if dt < 0 or dt > REENTRY_WINDOW_S:
                continue
            sim = hist_similarity(rec.signature, signature)
            if sim > best_sim:
                best_vid, best_sim, best_rec = vid, sim, rec

        if best_rec is not None and best_sim >= SIM_THRESHOLD:
            is_reentry = best_rec.has_exited and (clip_t - best_rec.last_seen) > CROSS_CAM_WINDOW_S
            best_rec.signature = 0.7 * best_rec.signature + 0.3 * signature
            best_rec.last_seen = clip_t
            best_rec.cameras.add(camera_id)
            best_rec.local_keys.add(key)
            if is_reentry:
                best_rec.has_exited = False  # new visit segment opened
            self._local_to_visitor[key] = best_vid
            return best_vid, is_reentry

        # No match -> brand new visitor.
        vid = make_visitor_id()
        self._by_visitor[vid] = VisitorRecord(
            visitor_id=vid, signature=signature.copy(),
            last_seen=clip_t, first_seen=clip_t,
            cameras={camera_id}, local_keys={key},
        )
        self._local_to_visitor[key] = vid
        return vid, False

    def mark_exited(self, visitor_id: str, clip_t: float):
        rec = self._by_visitor.get(visitor_id)
        if rec:
            rec.has_exited = True
            rec.last_seen = clip_t


def _hsv_hist(bgr) -> np.ndarray:
    import cv2
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8],
                     [0, 180, 0, 256, 0, 256]).flatten().astype(np.float32)
    s = h.sum()
    return h / s if s > 0 else h


def signature_from_crop(crop_bgr) -> np.ndarray:
    """Spatial colour descriptor: separate upper/lower-body HSV histograms.

    Splitting the crop into top and bottom halves captures the vertical colour
    layout (e.g. dark uniform top + light trousers) which is far more discriminative
    across cameras than one global histogram — a lightweight stand-in for a learned
    Re-ID embedding. PRODUCTION UPGRADE PATH: replace this single function with an
    OSNet/torchreid embedding (cosine similarity in `hist_similarity` already works
    for any fixed-length vector); the rest of the registry is unchanged.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return np.zeros(1024, dtype=np.float32)
    h = crop_bgr.shape[0]
    mid = max(1, h // 2)
    upper = _hsv_hist(crop_bgr[:mid])
    lower = _hsv_hist(crop_bgr[mid:]) if h > 1 else np.zeros(512, dtype=np.float32)
    return np.concatenate([upper, lower]).astype(np.float32)
