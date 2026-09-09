from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .models import ScrewPlan, Side
from .service import LEVEL_ORDER

# Residual thresholds are numerical-fit diagnostics only. The planned rod now
# interpolates screw-seat centers, so a large residual indicates a geometry or
# sampling problem rather than a clinical implant threshold.
FIT_CAUTION_MM = 0.5
FIT_WARNING_MM = 1.0


@dataclass(slots=True)
class RodPlan:
    """One fitted posterior rod for construct review (patient LPS, millimetres)."""

    side: Side
    levels: tuple[str, ...]
    material: str
    diameter_mm: float
    centerline_lps_mm: tuple[tuple[float, float, float], ...]
    length_mm: float
    sagittal_bend_deg: float
    coronal_bend_deg: float
    minimum_bend_radius_mm: float | None
    superior_overhang_mm: float
    inferior_overhang_mm: float
    seat_gap_mm: dict[str, float]
    seat_points_lps_mm: dict[str, tuple[float, float, float]]
    seat_projection_lps_mm: dict[str, tuple[float, float, float]]
    max_seat_gap_mm: float
    mean_seat_gap_mm: float
    worst_level: str | None
    max_straight_rod_offset_mm: float
    warning: str | None = None

    @property
    def fit_state(self) -> str:
        if self.max_seat_gap_mm > FIT_WARNING_MM:
            return "GEOMETRY CHECK"
        if self.max_seat_gap_mm > FIT_CAUTION_MM:
            return "CHECK SEATING"
        return "SEATED"


def rod_seat_point(plan: ScrewPlan) -> np.ndarray:
    """Approximate tulip rod-seat center from the simplified screw-head model."""

    entry = np.asarray(plan.entry_point, dtype=float)
    direction = np.asarray(plan.direction, dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm < 1e-8:
        direction = np.array([0.0, -1.0, 0.0], dtype=float)
    else:
        direction /= norm
    head_length = max(3.0, float(plan.diameter_mm) * 0.8)
    return entry - direction * (0.70 * head_length)


def build_rod_plan(
    plans: Mapping[tuple[str, Side], ScrewPlan],
    side: Side,
    *,
    material: str = "Ti-6Al-4V",
    diameter_mm: float = 5.5,
    overhang_mm: float = 8.0,
    samples: int = 160,
) -> RodPlan | None:
    """Create a smooth interpolating rod through all screw rod-seat centers.

    Unlike the previous least-squares implementation, this contour *passes
    through every planned seat*. Therefore the displayed seat residual answers
    "did the generated rod actually connect the screw heads?" rather than
    penalizing a deliberately straight approximation.
    """

    rows = [
        plan
        for (level, plan_side), plan in plans.items()
        if plan_side == side and level in LEVEL_ORDER
    ]
    rows.sort(key=lambda p: LEVEL_ORDER.index(p.level))
    if len(rows) < 2:
        return None

    seats = np.vstack([rod_seat_point(plan) for plan in rows])
    levels = tuple(plan.level for plan in rows)

    curve = _interpolating_curve(seats, max(48, int(samples)))
    first_tangent = _unit(curve[1] - curve[0])
    last_tangent = _unit(curve[-1] - curve[-2])
    first = curve[0] - first_tangent * float(overhang_mm)
    last = curve[-1] + last_tangent * float(overhang_mm)
    centerline = np.vstack((first, curve, last))

    seat_points: dict[str, tuple[float, float, float]] = {}
    projections: dict[str, tuple[float, float, float]] = {}
    gaps: dict[str, float] = {}
    for level, seat in zip(levels, seats, strict=True):
        projection, distance = _closest_point_on_polyline(centerline, seat)
        seat_points[level] = tuple(float(v) for v in seat)
        projections[level] = tuple(float(v) for v in projection)
        gaps[level] = float(distance)

    length_mm = float(np.linalg.norm(np.diff(centerline, axis=0), axis=1).sum())
    max_gap = max(gaps.values(), default=0.0)
    mean_gap = float(np.mean(list(gaps.values()))) if gaps else 0.0
    worst_level = max(gaps, key=gaps.get) if gaps else None

    sagittal_bend = _projected_bend_deg(centerline, (1, 2))
    coronal_bend = _projected_bend_deg(centerline, (0, 2))
    minimum_radius = _minimum_bend_radius(centerline)
    straight_offset = _max_distance_from_terminal_chord(seats)

    warning = None
    if max_gap > FIT_WARNING_MM:
        warning = "Generated rod does not pass cleanly through all screw-seat centers; review geometry."
    elif max_gap > FIT_CAUTION_MM:
        warning = "Small numerical rod-seat residual detected; review the generated contour."

    return RodPlan(
        side=side,
        levels=levels,
        material=material,
        diameter_mm=float(diameter_mm),
        centerline_lps_mm=tuple(tuple(float(v) for v in point) for point in centerline),
        length_mm=length_mm,
        sagittal_bend_deg=sagittal_bend,
        coronal_bend_deg=coronal_bend,
        minimum_bend_radius_mm=minimum_radius,
        superior_overhang_mm=float(overhang_mm),
        inferior_overhang_mm=float(overhang_mm),
        seat_gap_mm=gaps,
        seat_points_lps_mm=seat_points,
        seat_projection_lps_mm=projections,
        max_seat_gap_mm=float(max_gap),
        mean_seat_gap_mm=float(mean_gap),
        worst_level=worst_level,
        max_straight_rod_offset_mm=float(straight_offset),
        warning=warning,
    )


def _interpolating_curve(points: np.ndarray, samples: int) -> np.ndarray:
    if len(points) == 2:
        return np.linspace(points[0], points[1], samples)

    # Catmull-Rom interpolation: local, smooth, and passes exactly through each
    # supplied screw-seat point without requiring scipy.
    segments = len(points) - 1
    per_segment = max(12, int(np.ceil(samples / segments)))
    output: list[np.ndarray] = []
    for i in range(segments):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(len(points) - 1, i + 2)]
        for u in np.linspace(0.0, 1.0, per_segment, endpoint=False):
            u2 = u * u
            u3 = u2 * u
            point = 0.5 * (
                (2.0 * p1)
                + (-p0 + p2) * u
                + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
                + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3
            )
            output.append(point)
    output.append(points[-1].copy())
    return np.vstack(output)


def _closest_point_on_polyline(polyline: np.ndarray, point: np.ndarray) -> tuple[np.ndarray, float]:
    best_point = polyline[0]
    best_distance = float("inf")
    for a, b in zip(polyline[:-1], polyline[1:], strict=True):
        ab = b - a
        denom = float(np.dot(ab, ab))
        if denom < 1e-12:
            candidate = a
        else:
            t = float(np.clip(np.dot(point - a, ab) / denom, 0.0, 1.0))
            candidate = a + t * ab
        distance = float(np.linalg.norm(point - candidate))
        if distance < best_distance:
            best_distance = distance
            best_point = candidate
    return np.asarray(best_point, dtype=float), best_distance


def _max_distance_from_terminal_chord(points: np.ndarray) -> float:
    if len(points) <= 2:
        return 0.0
    a = points[0]
    b = points[-1]
    ab = b - a
    denom = float(np.dot(ab, ab))
    if denom < 1e-12:
        return float(np.max(np.linalg.norm(points - a, axis=1)))
    distances = []
    for point in points[1:-1]:
        t = float(np.clip(np.dot(point - a, ab) / denom, 0.0, 1.0))
        projection = a + t * ab
        distances.append(float(np.linalg.norm(point - projection)))
    return max(distances, default=0.0)


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-8:
        return np.array([0.0, 0.0, 1.0], dtype=float)
    return vector / norm


def _projected_bend_deg(points: np.ndarray, axes: tuple[int, int]) -> float:
    if len(points) < 3:
        return 0.0
    stride = max(2, len(points) // 30)
    start = points[stride] - points[0]
    end = points[-1] - points[-1 - stride]
    a = start[list(axes)]
    b = end[list(axes)]
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-8 or nb < 1e-8:
        return 0.0
    cosine = float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _minimum_bend_radius(points: np.ndarray) -> float | None:
    if len(points) < 5:
        return None
    radii: list[float] = []
    stride = max(2, len(points) // 45)
    for index in range(stride, len(points) - stride, stride):
        a = points[index - stride]
        b = points[index]
        c = points[index + stride]
        ab = float(np.linalg.norm(b - a))
        bc = float(np.linalg.norm(c - b))
        ca = float(np.linalg.norm(a - c))
        area2 = float(np.linalg.norm(np.cross(b - a, c - a)))
        if min(ab, bc, ca) < 1e-6 or area2 < 1e-7:
            continue
        radius = (ab * bc * ca) / (2.0 * area2)
        if np.isfinite(radius) and radius < 1e6:
            radii.append(float(radius))
    return min(radii) if radii else None
