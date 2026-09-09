from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .models import ScrewPlan, Side


@dataclass(frozen=True, slots=True)
class ScrewCollision:
    first_key: tuple[str, Side]
    second_key: tuple[str, Side]
    centerline_distance_mm: float
    surface_clearance_mm: float

    @property
    def overlap_mm(self) -> float:
        return max(0.0, -self.surface_clearance_mm)


def find_screw_collisions(
    plans: Mapping[tuple[str, Side], ScrewPlan],
    *,
    clearance_margin_mm: float = 0.0,
) -> list[ScrewCollision]:
    """Return shaft-shaft collisions using finite 3D screw segments.

    The test treats each planned screw shaft as a capsule whose radius is half
    the planned screw diameter. `clearance_margin_mm` can be used for a research
    warning band, but zero is the geometric overlap criterion.
    """

    items = list(plans.items())
    collisions: list[ScrewCollision] = []
    for i, (key_a, a) in enumerate(items):
        for key_b, b in items[i + 1 :]:
            # Same-side adjacent screws are checked as well; they normally have
            # ample separation, while contralateral same-level intersections are
            # the common failure this guard is intended to catch.
            p0 = np.asarray(a.entry_point, dtype=float)
            p1 = np.asarray(a.endpoint, dtype=float)
            q0 = np.asarray(b.entry_point, dtype=float)
            q1 = np.asarray(b.endpoint, dtype=float)
            centerline_distance = _segment_segment_distance(p0, p1, q0, q1)
            required = float(a.diameter_mm) / 2.0 + float(b.diameter_mm) / 2.0
            surface_clearance = centerline_distance - required
            if surface_clearance <= float(clearance_margin_mm):
                collisions.append(
                    ScrewCollision(
                        first_key=key_a,
                        second_key=key_b,
                        centerline_distance_mm=float(centerline_distance),
                        surface_clearance_mm=float(surface_clearance),
                    )
                )
    return collisions


def collisions_for_key(
    plans: Mapping[tuple[str, Side], ScrewPlan],
    key: tuple[str, Side],
    *,
    clearance_margin_mm: float = 0.0,
) -> list[ScrewCollision]:
    return [
        c
        for c in find_screw_collisions(plans, clearance_margin_mm=clearance_margin_mm)
        if key in (c.first_key, c.second_key)
    ]


def _segment_segment_distance(p0: np.ndarray, p1: np.ndarray, q0: np.ndarray, q1: np.ndarray) -> float:
    """Shortest distance between two finite 3D line segments."""

    u = p1 - p0
    v = q1 - q0
    w = p0 - q0
    a = float(np.dot(u, u))
    b = float(np.dot(u, v))
    c = float(np.dot(v, v))
    d = float(np.dot(u, w))
    e = float(np.dot(v, w))
    eps = 1e-12

    if a <= eps and c <= eps:
        return float(np.linalg.norm(p0 - q0))
    if a <= eps:
        t = float(np.clip(e / c if c > eps else 0.0, 0.0, 1.0))
        return float(np.linalg.norm(p0 - (q0 + t * v)))
    if c <= eps:
        s = float(np.clip(-d / a, 0.0, 1.0))
        return float(np.linalg.norm((p0 + s * u) - q0))

    denom = a * c - b * b
    if denom > eps:
        s = float(np.clip((b * e - c * d) / denom, 0.0, 1.0))
    else:
        s = 0.0
    t = (b * s + e) / c

    if t < 0.0:
        t = 0.0
        s = float(np.clip(-d / a, 0.0, 1.0))
    elif t > 1.0:
        t = 1.0
        s = float(np.clip((b - d) / a, 0.0, 1.0))

    closest_p = p0 + s * u
    closest_q = q0 + t * v
    return float(np.linalg.norm(closest_p - closest_q))
