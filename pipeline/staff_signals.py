"""Multi-signal staff classification (per visitor, decided after the whole clip).

Clothing colour alone is unreliable in this store (many customers also wear dark).
So we fuse evidence accumulated across a visitor's whole track:

  STRONG access signals (customers physically cannot do these):
    - stockroom_access   : seen in the back/stock room
    - behind_counter     : seen in the staff side of the billing counter (cash desk)

  BEHAVIOUR signals (how staff move vs shop):
    - long_presence      : present for most of the clip (staff stay; customers pass through)
    - multi_zone_roaming : visits many distinct zones (staff cover the floor)
    - frequent_zone_changes : many zone transitions (restocking / assisting)

  ACTION signal (optional VLM):
    - vlm_working        : VLM says the person is arranging/cleaning/billing, not shopping

  APPEARANCE signal (weak, supporting only):
    - dark_uniform       : dominant dark top

A customer browsing one zone in dark clothes scores LOW (only the weak appearance
signal fires) and is no longer mis-flagged as staff — which was the failure of the
clothing-only approach.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# behaviour thresholds (clips are ~150 s)
LONG_PRESENCE_S = 90.0
MULTI_ZONE = 3
FREQUENT_CHANGES = 5
DARK_RATIO = 0.6
BEHIND_COUNTER_RATIO = 0.25

STAFF_THRESHOLD = 0.6


@dataclass
class VisitorEvidence:
    visitor_id: str
    first_t: float = 1e18
    last_t: float = -1e18
    frames: int = 0
    zones: set[str] = field(default_factory=set)
    zone_enter_count: int = 0
    in_stockroom: bool = False
    behind_counter_frames: int = 0
    billing_frames: int = 0
    dark_votes: int = 0
    appearance_votes: int = 0
    vlm_working: bool | None = None  # True=working, False=shopping, None=unknown

    def observe(self, t: float):
        self.first_t = min(self.first_t, t)
        self.last_t = max(self.last_t, t)
        self.frames += 1

    @property
    def presence_s(self) -> float:
        return max(0.0, self.last_t - self.first_t)

    @property
    def dark_ratio(self) -> float:
        return self.dark_votes / self.appearance_votes if self.appearance_votes else 0.0

    @property
    def behind_counter_ratio(self) -> float:
        return self.behind_counter_frames / self.billing_frames if self.billing_frames else 0.0


def score_visitor(ev: VisitorEvidence) -> tuple[bool, float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if ev.in_stockroom:
        score += 0.6; reasons.append("stockroom_access")
    if ev.behind_counter_ratio >= BEHIND_COUNTER_RATIO:
        score += 0.5; reasons.append("behind_counter")
    if ev.presence_s >= LONG_PRESENCE_S:
        score += 0.3; reasons.append("long_presence")
    if len(ev.zones - {None}) >= MULTI_ZONE:
        score += 0.2; reasons.append("multi_zone_roaming")
    if ev.zone_enter_count >= FREQUENT_CHANGES:
        score += 0.15; reasons.append("frequent_zone_changes")
    if ev.dark_ratio >= DARK_RATIO:
        score += 0.15; reasons.append("dark_uniform")

    if ev.vlm_working is True:
        score += 0.5; reasons.append("vlm_working_action")
    elif ev.vlm_working is False:
        score -= 0.3; reasons.append("vlm_shopping")

    is_staff = score >= STAFF_THRESHOLD
    conf = min(0.98, max(0.5, score)) if is_staff else min(0.95, max(0.5, 1.0 - score))
    return is_staff, round(conf, 2), reasons


def classify_all(evidence: dict[str, VisitorEvidence]) -> dict[str, dict]:
    """Return {visitor_id: {is_staff, confidence, reasons}}."""
    out = {}
    for vid, ev in evidence.items():
        is_staff, conf, reasons = score_visitor(ev)
        out[vid] = {"is_staff": is_staff, "confidence": conf, "reasons": reasons}
    return out
