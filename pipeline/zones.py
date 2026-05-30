"""Geometry helpers: zone polygons + entry-line crossing.

All coordinates are in pixels of the 1920x1080 frame. The store layout
(polygons, entry line) comes from data/store_layout.json. We keep this pure
(no OpenCV/torch) so it is trivially unit-testable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


Point = tuple[float, float]


def point_in_polygon(pt: Point, poly: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _side(p1: Point, p2: Point, q: Point) -> float:
    """Signed area / cross product — which side of line (p1->p2) is point q on."""
    return (p2[0] - p1[0]) * (q[1] - p1[1]) - (p2[1] - p1[1]) * (q[0] - p1[0])


@dataclass
class EntryLine:
    p1: Point
    p2: Point
    inside_normal: Point  # direction vector pointing into the store interior

    def signed_side(self, q: Point) -> float:
        return _side(self.p1, self.p2, q)

    def crossing_direction(self, prev: Point, curr: Point) -> Optional[str]:
        """Return 'ENTRY' (moved to interior side), 'EXIT' (to exterior), or None.

        We compare the sign of the point's side before/after. A change of sign
        means the segment was crossed. Direction is decided by which side is the
        'inside' (the side the inside_normal points toward from the line midpoint).
        """
        s_prev = self.signed_side(prev)
        s_curr = self.signed_side(curr)
        if s_prev == 0 or s_curr == 0 or (s_prev > 0) == (s_curr > 0):
            return None  # no crossing
        # Determine which sign corresponds to "inside" using the normal.
        mid = ((self.p1[0] + self.p2[0]) / 2, (self.p1[1] + self.p2[1]) / 2)
        inside_probe = (mid[0] + self.inside_normal[0], mid[1] + self.inside_normal[1])
        inside_sign = self.signed_side(inside_probe) > 0
        moved_to_inside = (s_curr > 0) == inside_sign
        return "ENTRY" if moved_to_inside else "EXIT"


@dataclass
class CameraLayout:
    camera_id: str
    source_clip: str
    role: str
    fps: float
    zones: dict[str, list[list[float]]] = field(default_factory=dict)  # zone_id -> polygon
    sku_zone: dict[str, str] = field(default_factory=dict)
    entry_line: Optional[EntryLine] = None
    queue_region: Optional[list[list[float]]] = None
    staff_zone: Optional[list[list[float]]] = None   # behind-counter / cash-desk: staff-only
    staff_only: bool = False

    def zone_at(self, pt: Point) -> Optional[str]:
        """Return the zone_id whose polygon contains pt, else None."""
        for zid, poly in self.zones.items():
            if point_in_polygon(pt, poly):
                return zid
        return None

    def in_queue(self, pt: Point) -> bool:
        return self.queue_region is not None and point_in_polygon(pt, self.queue_region)

    def in_staff_zone(self, pt: Point) -> bool:
        return self.staff_zone is not None and point_in_polygon(pt, self.staff_zone)


@dataclass
class StoreLayout:
    store_id: str
    frame_width: int
    frame_height: int
    cameras: dict[str, CameraLayout]          # camera_id -> CameraLayout
    clip_to_camera: dict[str, str]            # source clip filename -> camera_id
    zone_catalogue: list[str]
    staff_rules: dict

    @classmethod
    def load(cls, path: str | Path) -> "StoreLayout":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cams: dict[str, CameraLayout] = {}
        clip_map: dict[str, str] = {}
        for c in data["cameras"]:
            zones = {}
            sku = {}
            for zid, z in (c.get("zones") or {}).items():
                zones[zid] = z["polygon"]
                sku[zid] = z.get("sku_zone", zid)
            line = None
            if c.get("entry_line"):
                el = c["entry_line"]
                line = EntryLine(tuple(el["p1"]), tuple(el["p2"]),
                                 tuple(el.get("inside_normal", [0, -1])))
            cam = CameraLayout(
                camera_id=c["camera_id"],
                source_clip=c["source_clip"],
                role=c["role"],
                fps=float(c.get("fps", 25)),
                zones=zones,
                sku_zone=sku,
                entry_line=line,
                queue_region=(c.get("queue_region") or {}).get("polygon"),
                staff_zone=(c.get("staff_zone") or {}).get("polygon"),
                staff_only=bool(c.get("staff_only", False)),
            )
            cams[cam.camera_id] = cam
            clip_map[c["source_clip"]] = cam.camera_id
        return cls(
            store_id=data["store_id"],
            frame_width=data["frame_size"]["width"],
            frame_height=data["frame_size"]["height"],
            cameras=cams,
            clip_to_camera=clip_map,
            zone_catalogue=data.get("zone_catalogue", []),
            staff_rules=data.get("staff_rules", {}),
        )
