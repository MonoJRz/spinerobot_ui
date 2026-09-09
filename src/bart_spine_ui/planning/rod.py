from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from .models import HEAD_HEIGHT_MM, ScrewPlan, Side
from .service import LEVEL_ORDER

# Research-planning thresholds for the reduction distance from a smooth
# candidate rod to a tulip seat. They are not clinical acceptance limits.
FIT_CAUTION_MM = 0.5
FIT_WARNING_MM = 1.0
GENERIC_TI_ROD_DIAMETER_MM = 5.5
ROD_LENGTH_INCREMENT_MM = 5.0


@dataclass(slots=True)
class RodPlan:
    """One fitted posterior rod for construct review (patient LPS, millimetres)."""

    side: Side
    levels: tuple[str, ...]
    material: str
    diameter_mm: float
    centerline_lps_mm: tuple[tuple[float, float, float], ...]
    length_mm: float
    required_length_mm: float
    sagittal_bend_deg: float
    coronal_bend_deg: float
    minimum_bend_radius_mm: float | None
    superior_overhang_mm: float
    inferior_overhang_mm: float
    seat_gap_mm: dict[str, float]
    seat_points_lps_mm: dict[str, tuple[float, float, float]]
    seat_projection_lps_mm: dict[str, tuple[float, float, float]]
    tulip_slot_directions_lps: dict[str, tuple[float, float, float]]
    max_seat_gap_mm: float
    mean_seat_gap_mm: float
    worst_level: str | None
    max_straight_rod_offset_mm: float
    fitting_order: int
    sagittal_curvature_reversals: int
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
    return entry - direction * (0.70 * HEAD_HEIGHT_MM)


def build_rod_plan(
    plans: Mapping[tuple[str, Side], ScrewPlan],
    side: Side,
    *,
    material: str = "Ti-6Al-4V",
    diameter_mm: float = GENERIC_TI_ROD_DIAMETER_MM,
    overhang_mm: float = 12.0,
    samples: int = 160,
) -> RodPlan | None:
    """Create a fair candidate rod constrained by, but not forced through, tulips.

    The rod is fit globally to all tulip seats. It uses the lowest polynomial
    order that captures the broad contour without sagittal curvature reversals,
    leaving polyaxial tulips to accommodate the remaining reduction distance.
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

    curve, fitting_order, curvature_reversals = _fair_candidate_curve(
        seats, max(48, int(samples))
    )
    first_tangent = _unit(curve[1] - curve[0])
    last_tangent = _unit(curve[-1] - curve[-2])
    first = curve[0] - first_tangent * float(overhang_mm)
    last = curve[-1] + last_tangent * float(overhang_mm)
    centerline = np.vstack((first, curve, last))

    seat_points: dict[str, tuple[float, float, float]] = {}
    projections: dict[str, tuple[float, float, float]] = {}
    gaps: dict[str, float] = {}
    tulip_slot_directions: dict[str, tuple[float, float, float]] = {}
    for level, seat, plan in zip(levels, seats, rows, strict=True):
        projection, distance = _closest_point_on_polyline(centerline, seat)
        seat_points[level] = tuple(float(v) for v in seat)
        projections[level] = tuple(float(v) for v in projection)
        gaps[level] = float(distance)
        # A polyaxial tulip rotates independently around the shank. Its U-slot
        # is therefore driven by the local rod direction, projected into the
        # plane normal to the shank (the mechanically realizable orientation).
        tangent = _polyline_tangent_at_closest_point(centerline, projection)
        tulip_slot_directions[level] = tuple(
            float(v) for v in _tulip_slot_direction(tangent, np.asarray(plan.direction, dtype=float))
        )

    required_length_mm = float(np.linalg.norm(np.diff(centerline, axis=0), axis=1).sum())
    length_mm = _round_up_to_increment(required_length_mm, ROD_LENGTH_INCREMENT_MM)
    max_gap = max(gaps.values(), default=0.0)
    mean_gap = float(np.mean(list(gaps.values()))) if gaps else 0.0
    worst_level = max(gaps, key=gaps.get) if gaps else None

    sagittal_bend = _projected_bend_deg(centerline, (1, 2))
    coronal_bend = _projected_bend_deg(centerline, (0, 2))
    minimum_radius = _minimum_bend_radius(centerline)
    straight_offset = _max_distance_from_terminal_chord(seats)

    warning = None
    if max_gap > FIT_WARNING_MM:
        warning = "Smooth candidate requires tulip reduction; review rod-to-seat distances."
    elif max_gap > FIT_CAUTION_MM:
        warning = "Small tulip reduction is required to seat this smooth rod."
    if curvature_reversals:
        warning = "Sagittal curvature reversal detected; review the planned contour."

    return RodPlan(
        side=side,
        levels=levels,
        material=material,
        diameter_mm=float(diameter_mm),
        centerline_lps_mm=tuple(tuple(float(v) for v in point) for point in centerline),
        length_mm=length_mm,
        required_length_mm=required_length_mm,
        sagittal_bend_deg=sagittal_bend,
        coronal_bend_deg=coronal_bend,
        minimum_bend_radius_mm=minimum_radius,
        superior_overhang_mm=float(overhang_mm),
        inferior_overhang_mm=float(overhang_mm),
        seat_gap_mm=gaps,
        seat_points_lps_mm=seat_points,
        seat_projection_lps_mm=projections,
        tulip_slot_directions_lps=tulip_slot_directions,
        max_seat_gap_mm=float(max_gap),
        mean_seat_gap_mm=float(mean_gap),
        worst_level=worst_level,
        max_straight_rod_offset_mm=float(straight_offset),
        fitting_order=fitting_order,
        sagittal_curvature_reversals=curvature_reversals,
        warning=warning,
    )


def _round_up_to_increment(value_mm: float, increment_mm: float) -> float:
    """Select a stock rod length that never undershoots the required span."""

    return float(np.ceil((value_mm - 1e-9) / increment_mm) * increment_mm)


def _fair_candidate_curve(points: np.ndarray, samples: int) -> tuple[np.ndarray, int, int]:
    """Fit a global, slowly varying rod contour without local spline wiggles."""

    if len(points) == 2:
        return np.linspace(points[0], points[1], samples), 1, 0

    parameters = _chord_parameters(points)
    # A three-screw construct can support one broad quadratic contour. Larger
    # constructs deliberately use fewer coefficients than seats, so tulips are
    # constraints rather than interpolation knots.
    maximum_order = 2 if len(points) == 3 else min(3, len(points) - 2)
    for order in range(maximum_order, 0, -1):
        curve = _least_squares_polynomial_curve(points, parameters, order, samples)
        reversals = _sagittal_curvature_reversals(curve)
        if reversals == 0:
            return curve, order, reversals

    # A straight rod is the final fairing fallback and cannot introduce a
    # repeated or reverse bend.
    return np.linspace(points[0], points[-1], samples), 1, 0


def _chord_parameters(points: np.ndarray) -> np.ndarray:
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(distances)))
    total = float(cumulative[-1])
    if total < 1e-8:
        return np.linspace(0.0, 1.0, len(points))
    return cumulative / total


def _least_squares_polynomial_curve(
    points: np.ndarray,
    parameters: np.ndarray,
    order: int,
    samples: int,
) -> np.ndarray:
    """Fit one low-order global polynomial per patient-space coordinate."""

    design = np.polynomial.polynomial.polyvander(parameters, order)
    # Slight endpoint weighting maintains construct span while intermediate
    # screw locations behave as reduction constraints rather than hard knots.
    weights = np.ones(len(points))
    weights[[0, -1]] = 1.8
    coefficients, *_ = np.linalg.lstsq(design * weights[:, None], points * weights[:, None], rcond=None)
    sample_parameters = np.linspace(0.0, 1.0, samples)
    return np.polynomial.polynomial.polyvander(sample_parameters, order) @ coefficients


def _sagittal_curvature_reversals(points: np.ndarray) -> int:
    """Count meaningful changes in signed curvature in the patient YZ plane."""

    if len(points) < 3:
        return 0
    sagittal = points[:, (1, 2)]
    first = np.diff(sagittal, axis=0)
    signed = first[:-1, 0] * first[1:, 1] - first[:-1, 1] * first[1:, 0]
    if not len(signed):
        return 0
    threshold = max(1e-7, float(np.max(np.abs(signed))) * 0.02)
    signs = np.sign(signed[np.abs(signed) > threshold])
    if len(signs) < 2:
        return 0
    return int(np.count_nonzero(signs[1:] != signs[:-1]))


def _closest_point_on_polyline(polyline: np.ndarray, point: np.ndarray) -> tuple[np.ndarray, float]:
    best_point = polyline[0]
    best_distance = float("inf")
    for a, b in pairwise(polyline):
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


def _polyline_tangent_at_closest_point(polyline: np.ndarray, point: np.ndarray) -> np.ndarray:
    """Return the direction of the rod segment nearest to ``point``."""

    best_vector = polyline[1] - polyline[0]
    best_distance = float("inf")
    for a, b in pairwise(polyline):
        vector = b - a
        denom = float(np.dot(vector, vector))
        if denom < 1e-12:
            continue
        fraction = float(np.clip(np.dot(point - a, vector) / denom, 0.0, 1.0))
        candidate = a + fraction * vector
        distance = float(np.linalg.norm(point - candidate))
        if distance < best_distance:
            best_distance = distance
            best_vector = vector
    return _unit(best_vector)


def _tulip_slot_direction(rod_tangent: np.ndarray, shank_direction: np.ndarray) -> np.ndarray:
    """Align a tulip slot to the rod while preserving an independent shank axis."""

    shank = _unit(shank_direction)
    slot = np.asarray(rod_tangent, dtype=float) - shank * float(np.dot(rod_tangent, shank))
    if float(np.linalg.norm(slot)) < 1e-8:
        reference = np.array([0.0, 0.0, 1.0])
        if abs(float(np.dot(reference, shank))) > 0.9:
            reference = np.array([1.0, 0.0, 0.0])
        slot = np.cross(shank, reference)
    return _unit(slot)


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
