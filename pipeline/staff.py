"""Staff classification.

Three signals, combined:
  1. Stockroom presence  -> definitely staff (rule from layout).
  2. Dark-uniform heuristic -> store staff wear near-black tops; the dominant
     upper-body colour being very dark is a strong cue (fast, no network).
  3. Optional VLM (Gemini) -> validates ambiguous crops with a vision prompt.
     Only called when GEMINI_API_KEY is set; otherwise we rely on 1 + 2.

The VLM is deliberately a *validator*, not the primary path: at 5 cameras x
thousands of frames, calling a VLM per detection is too slow/expensive. We call
it sparingly (once per track, on the clearest crop) and cache by track.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

# --- Heuristic ---------------------------------------------------------------

# A top is "dark uniform" if the median brightness of the upper-body crop is low
# and it is not very colourful (low saturation) — i.e. black/charcoal, not a dark
# blue/red garment.
DARK_V_MAX = 70        # HSV value (0-255) below this = dark
LOW_SAT_MAX = 80       # HSV saturation below this = not strongly coloured


def upper_body_crop(frame: np.ndarray, xyxy: tuple[float, float, float, float]) -> np.ndarray:
    x1, y1, x2, y2 = [int(v) for v in xyxy]
    h = y2 - y1
    # torso ~ top 20%-55% of the box (below head, above legs)
    ty1 = y1 + int(0.20 * h)
    ty2 = y1 + int(0.55 * h)
    x1 = max(0, x1); ty1 = max(0, ty1)
    crop = frame[ty1:ty2, x1:x2]
    return crop


def dark_uniform_score(frame_bgr: np.ndarray, xyxy) -> float:
    """Return P(staff) in [0,1] from the dark-uniform heuristic."""
    import cv2
    crop = upper_body_crop(frame_bgr, xyxy)
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    v = float(np.median(hsv[:, :, 2]))
    s = float(np.median(hsv[:, :, 1]))
    if v <= DARK_V_MAX and s <= LOW_SAT_MAX:
        # the darker / less saturated, the more confident
        return float(np.clip(1.0 - (v / DARK_V_MAX) * 0.5, 0.6, 0.95))
    return float(np.clip(0.3 - (v - DARK_V_MAX) / 255.0, 0.0, 0.3))


# --- Optional VLM validator --------------------------------------------------

@dataclass
class VLMResult:
    is_staff: bool
    confidence: float
    raw: str


class StaffVLM:
    """Gemini vision validator (REST). No-op if no API key — degrades gracefully.

    Uses the Generative Language REST API directly (verified working with the
    AQ.* key format and gemini-2.5-flash) so we avoid an extra SDK dependency.
    """

    # PROMPT used for staff validation (also reproduced in docs/DESIGN.md):
    PROMPT = (
        "You are labelling anonymised retail CCTV crops for a beauty store. "
        "Faces are blurred. Store STAFF wear a dark/black uniform top and often "
        "stand behind counters or move between back areas. CUSTOMERS wear varied "
        "colours and browse shelves. Look at this single cropped person and answer "
        "strictly as JSON: {\"is_staff\": true|false, \"confidence\": 0.0-1.0, "
        "\"reason\": \"...\"}. If unsure, set confidence below 0.6."
    )
    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    MIN_INTERVAL_S = 5.0   # throttle to stay under the free-tier RPM
    MAX_CALLS = 12         # hard cap on VLM calls per run

    def __init__(self):
        self.key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.model = os.environ.get("VLM_MODEL", "gemini-2.0-flash")
        self.enabled = bool(self.key)
        self._last_t = 0.0
        self.calls = 0

    # Action-recognition prompt: behaviour, not just clothing (also in DESIGN.md).
    ACTION_PROMPT = (
        "Anonymised retail CCTV crop from a beauty store (faces blurred). Decide whether "
        "this person is WORKING as staff or SHOPPING as a customer. Staff actions: "
        "arranging/restocking products on shelves, cleaning/dusting, operating the billing "
        "till, standing behind the counter, escorting/assisting. Customer actions: browsing, "
        "holding/examining a product to buy, queuing at billing, carrying a basket. Answer "
        "STRICT JSON: {\"working\": true|false, \"confidence\": 0.0-1.0, \"action\": \"...\"}."
    )

    def _call(self, prompt: str, crop_bgr: np.ndarray) -> dict | None:
        if self.calls >= self.MAX_CALLS:
            return None
        try:
            import base64
            import json as _json
            import time
            import cv2
            import requests
            # throttle to respect the free-tier rate limit
            dt = time.time() - self._last_t
            if dt < self.MIN_INTERVAL_S:
                time.sleep(self.MIN_INTERVAL_S - dt)
            ok, buf = cv2.imencode(".jpg", crop_bgr)
            if not ok:
                return None
            self._last_t = time.time()
            self.calls += 1
            body = {"contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg",
                                 "data": base64.b64encode(buf.tobytes()).decode()}},
            ]}]}
            r = requests.post(self.ENDPOINT.format(model=self.model),
                              params={"key": self.key}, json=body, timeout=30)
            if r.status_code != 200:
                print(f"[staff] VLM http {r.status_code}: {r.text[:120]}")
                return None
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().strip("`")
            if text.startswith("json"):
                text = text[4:]
            return _json.loads(text)
        except Exception as e:
            print(f"[staff] VLM call failed: {e}")
            return None

    def classify(self, crop_bgr: np.ndarray) -> VLMResult | None:
        if not self.enabled or crop_bgr is None or crop_bgr.size == 0:
            return None
        data = self._call(self.PROMPT, crop_bgr)
        if data is None:
            return None
        return VLMResult(bool(data.get("is_staff", False)),
                         float(data.get("confidence", 0.5)), str(data))

    def classify_action(self, crop_bgr: np.ndarray) -> bool | None:
        """Return True if working (staff), False if shopping, None if unknown/disabled."""
        if not self.enabled or crop_bgr is None or crop_bgr.size == 0:
            return None
        data = self._call(self.ACTION_PROMPT, crop_bgr)
        if data is None or "working" not in data:
            return None
        if float(data.get("confidence", 0)) < 0.55:
            return None  # not confident enough to use
        return bool(data["working"])


def decide_is_staff(in_stockroom: bool, heuristic_p: float,
                    vlm: VLMResult | None) -> tuple[bool, float]:
    """Fuse the three signals into (is_staff, staff_confidence)."""
    if in_stockroom:
        return True, 0.97
    if vlm is not None and vlm.confidence >= 0.6:
        return vlm.is_staff, vlm.confidence
    return heuristic_p >= 0.6, heuristic_p
