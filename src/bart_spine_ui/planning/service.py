from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from ..imaging.models import MedicalVolume
from ..segmentation import SegmentationVolume
from .models import ScrewPlan, Side

LEVEL_ORDER = tuple([f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)])
STANDARD_DIAMETERS_MM = tuple(np.arange(3.0, 8.5, 0.5).tolist())
STANDARD_LENGTHS_MM = tuple(range(25, 81, 5))


def parse_levels_of_interest(region: str | None) -> list[str]:
    """Parse case strings such as 'L3 – L5', 'T11-L2', or 'L3, L4, L5'."""

    if not region:
        return []
    tokens = [token.upper() for token in re.findall(r"\b[TL]\s*\d{1,2}\b", region.upper())]
    tokens = [token.replace(" ", "") for token in tokens if token.replace(" ", "") in LEVEL_ORDER]
    if not tokens:
        return []

    # A two-endpoint string is interpreted as a superior-to-inferior range.
    if len(tokens) == 2 and re.search(r"[-–—]|\bTO\b", region.upper()):
        a, b = (LEVEL_ORDER.index(tokens[0]), LEVEL_ORDER.index(tokens[1]))
        lo, hi = sorted((a, b))
        return list(LEVEL_ORDER[lo : hi + 1])

    # Preserve anatomical superior -> inferior ordering and remove duplicates.
    unique = set(tokens)
    return [level for level in LEVEL_ORDER if level in unique]


class PediclePlanningService:
    """
    Geometry-only first-pass screw estimation.

    The method intentionally stays conservative and transparent:
      * the user chooses the cortical entry point;
      * the vertebral mask supplies geometry;
      * a PCA-derived superior/inferior axis estimates the endplate normal;
      * the trajectory is projected into that estimated endplate plane;
      * a ray/mask intersection estimates usable length;
      * radial mask clearance along the posterior part of the ray estimates pedicle width.

    It is a research/prototyping aid and is not a clinically validated planner.
    """

    def __init__(
        self,
        *,
        sample_step_mm: float = 0.5,
        cortical_margin_mm: float = 2.0,
        diameter_margin_mm: float = 1.0,
    ):
        self.sample_step_mm = float(sample_step_mm)
        self.cortical_margin_mm = float(cortical_margin_mm)
        self.diameter_margin_mm = float(diameter_margin_mm)

    def available_levels(self, segmentation: SegmentationVolume) -> list[str]:
        names = set(segmentation.labels.values())
        return [level for level in LEVEL_ORDER if level in names]

    def label_value(self, segmentation: SegmentationVolume, level: str) -> int:
        for value, name in segmentation.labels.items():
            if name == level:
                return int(value)
        raise ValueError(f"No segmentation label found for {level}.")

    def suggested_focus_point(
        self,
        segmentation: SegmentationVolume,
        level: str,
        side: Side,
    ) -> tuple[float, float, float]:
        """Posterolateral point on the axial slice with the largest pedicle region."""

        label = self.label_value(segmentation, level)
        points = self._label_points(segmentation.sitk_image, label, max_points=120000)
        if len(points) == 0:
            raise ValueError(f"The {level} mask is empty.")

        center_x = float(np.median(points[:, 0]))
        lateral = points[:, 0] >= center_x if side == "left" else points[:, 0] <= center_x
        candidates = points[lateral]
        if len(candidates) < 50:
            candidates = points

        # LPS: +Y is posterior. The posterolateral quadrant contains the pedicle
        # and excludes most of the vertebral body. Select the axial level where
        # that quadrant has its largest segmented cross-section instead of using
        # the median Z of the whole posterior element.
        posterior_cut = float(np.percentile(points[:, 1], 55))
        posterolateral = candidates[candidates[:, 1] >= posterior_cut]
        if len(posterolateral) < 10:
            posterolateral = candidates

        image = segmentation.sitk_image
        origin = np.asarray(image.GetOrigin(), dtype=float)
        spacing = np.asarray(image.GetSpacing(), dtype=float)
        direction = np.asarray(image.GetDirection(), dtype=float).reshape(3, 3)
        continuous_indices = ((posterolateral - origin) @ direction) / spacing
        axial_indices = np.rint(continuous_indices[:, 2]).astype(int)
        slices, counts = np.unique(axial_indices, return_counts=True)
        largest_count = int(np.max(counts))
        largest_slices = slices[counts == largest_count]
        # Prefer the middle of an equal-sized plateau rather than one arbitrary edge.
        best_slice = int(largest_slices[len(largest_slices) // 2])
        candidates = posterolateral[axial_indices == best_slice]

        x_percentile = 68 if side == "left" else 32
        return (
            float(np.percentile(candidates[:, 0], x_percentile)),
            float(np.median(candidates[:, 1])),
            float(
                image.TransformContinuousIndexToPhysicalPoint(
                    (0.0, 0.0, float(best_slice))
                )[2]
            ),
        )

    def estimate(
        self,
        segmentation: SegmentationVolume,
        level: str,
        side: Side,
        entry_point_lps: tuple[float, float, float],
    ) -> ScrewPlan:
        label = self.label_value(segmentation, level)
        points = self._label_points(segmentation.sitk_image, label, max_points=24000)
        if len(points) < 20:
            raise ValueError(f"The {level} segmentation is too small for planning.")

        entry = np.asarray(entry_point_lps, dtype=float)
        endplate_normal = self._estimate_endplate_normal(points)
        direction = self._estimate_direction(points, entry, side, endplate_normal)
        direction = self._optimize_pedicle_corridor(
            segmentation.sitk_image,
            label,
            entry,
            direction,
            endplate_normal,
        )

        anatomical_length, ray_warning = self._ray_length(
            segmentation.sitk_image,
            label,
            entry,
            direction,
        )
        pedicle_width = self._estimate_pedicle_width(
            segmentation.sitk_image,
            label,
            entry,
            direction,
            endplate_normal,
            anatomical_length,
        )

        recommended_length = self._standard_length(anatomical_length)
        recommended_diameter = self._standard_diameter(pedicle_width)
        endpoint = entry + direction * recommended_length

        warning = ray_warning
        if pedicle_width < 3.5:
            width_warning = "Very small/uncertain mask clearance; verify segmentation and trajectory."
            warning = f"{warning} {width_warning}".strip() if warning else width_warning

        return ScrewPlan(
            level=level,
            side=side,
            entry_point=tuple(float(v) for v in entry),
            direction=tuple(float(v) for v in direction),
            endpoint=tuple(float(v) for v in endpoint),
            anatomical_length_mm=float(anatomical_length),
            pedicle_width_mm=float(pedicle_width),
            diameter_mm=float(recommended_diameter),
            length_mm=float(recommended_length),
            endplate_normal=tuple(float(v) for v in endplate_normal),
            warning=warning,
        )

    def save_plans(
        self,
        volume: MedicalVolume,
        plans: dict[tuple[str, Side], ScrewPlan],
        *,
        case_region: str | None = None,
        accepted: set[tuple[str, Side]] | None = None,
    ) -> Path | None:
        if volume.source_path is None:
            return None
        path = self.plan_path(volume)
        if path is None:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        accepted = accepted or set()
        ordered = sorted(
            plans.values(),
            key=lambda p: (LEVEL_ORDER.index(p.level), 0 if p.side == "left" else 1),
        )
        payload = {
            "coordinate_system": "LPS",
            "units": "mm",
            "case_region": case_region,
            "algorithm_status": "research prototype - manual verification required",
            "plans": [
                {
                    **plan.to_dict(),
                    "status": "accepted"
                    if (plan.level, plan.side) in accepted
                    else "draft",
                }
                for plan in ordered
            ],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load_plans(
        self,
        volume: MedicalVolume,
    ) -> tuple[dict[tuple[str, Side], ScrewPlan], set[tuple[str, Side]]]:
        """Load previously stored screws for a CT, skipping malformed rows."""

        path = self.plan_path(volume)
        if path is None or not path.is_file():
            return {}, set()
        try:
            rows = json.loads(path.read_text(encoding="utf-8")).get("plans", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            return {}, set()

        plans: dict[tuple[str, Side], ScrewPlan] = {}
        accepted: set[tuple[str, Side]] = set()
        for row in rows:
            try:
                level = str(row["level"])
                side = str(row["side"])
                if level not in LEVEL_ORDER or side not in ("left", "right"):
                    continue
                plan = ScrewPlan(
                    level=level,
                    side=side,
                    entry_point=tuple(float(v) for v in row["entry_point_lps_mm"]),
                    direction=tuple(float(v) for v in row["direction_lps"]),
                    endpoint=tuple(float(v) for v in row["endpoint_lps_mm"]),
                    anatomical_length_mm=float(row["estimated_anatomical_length_mm"]),
                    pedicle_width_mm=float(row["estimated_pedicle_width_mm"]),
                    diameter_mm=float(row["screw_diameter_mm"]),
                    length_mm=float(row["screw_length_mm"]),
                    endplate_normal=tuple(
                        float(v) for v in row["estimated_endplate_normal_lps"]
                    ),
                    warning=row.get("warning"),
                )
            except (KeyError, TypeError, ValueError):
                continue
            key = (plan.level, plan.side)
            plans[key] = plan
            if row.get("status") == "accepted":
                accepted.add(key)
        return plans, accepted

    @staticmethod
    def plan_path(volume: MedicalVolume) -> Path | None:
        if volume.source_path is None:
            return None
        source = volume.source_path.expanduser().resolve()
        base = source if source.is_dir() else source.parent
        return base / "planning" / "pedicle_screws.json"

    def _estimate_endplate_normal(self, points: np.ndarray) -> np.ndarray:
        """Fit the slope of the superior vertebral-body surface."""

        z_axis = np.array([0.0, 0.0, 1.0])

        # LPS anterior is -Y. Restrict the fit toward the anterior vertebral body so
        # posterior elements do not dominate the endplate estimate.
        anterior_cut = float(np.percentile(points[:, 1], 55))
        body_points = points[points[:, 1] <= anterior_cut]
        if len(body_points) < 100:
            body_points = points

        # Build a superior envelope: one highest surface point per 2 mm XY bin.
        # This follows the endplate slope rather than fitting an arbitrary upper band.
        xy_bins = np.rint(body_points[:, :2] / 2.0).astype(int)
        _bins, inverse = np.unique(xy_bins, axis=0, return_inverse=True)
        maximum_z = np.full(int(np.max(inverse)) + 1, -np.inf, dtype=float)
        np.maximum.at(maximum_z, inverse, body_points[:, 2])
        surface = body_points[np.isclose(body_points[:, 2], maximum_z[inverse])]
        if len(surface) >= 30:
            design = np.column_stack((surface[:, 0], surface[:, 1], np.ones(len(surface))))
            coefficients, *_ = np.linalg.lstsq(design, surface[:, 2], rcond=None)
            residuals = surface[:, 2] - design @ coefficients
            keep = np.abs(residuals - np.median(residuals)) <= max(
                1.5,
                float(np.percentile(np.abs(residuals - np.median(residuals)), 80)),
            )
            if np.count_nonzero(keep) >= 20:
                coefficients, *_ = np.linalg.lstsq(
                    design[keep], surface[keep, 2], rcond=None
                )
            normal = self._normalize(
                np.array((-coefficients[0], -coefficients[1], 1.0), dtype=float)
            )
            if abs(float(np.dot(normal, z_axis))) >= 0.45:
                return normal

        centered = points - np.mean(points, axis=0)
        covariance = np.cov(centered.T)
        _values, vectors = np.linalg.eigh(covariance)
        idx = int(np.argmax(np.abs(vectors.T @ z_axis)))
        normal = vectors[:, idx]
        if float(np.dot(normal, z_axis)) < 0:
            normal = -normal
        return self._normalize(normal)

    def _estimate_direction(
        self,
        points: np.ndarray,
        entry: np.ndarray,
        side: Side,
        endplate_normal: np.ndarray,
    ) -> np.ndarray:
        # LPS anterior is -Y. Use the anterior-most vertebral body region as a target.
        anterior_cut = float(np.percentile(points[:, 1], 14))
        anterior = points[points[:, 1] <= anterior_cut]
        if len(anterior) < 20:
            anterior = points
        target = np.median(anterior, axis=0)

        # Keep the target slightly ipsilateral so a posterior entry naturally converges medially.
        center_x = float(np.median(points[:, 0]))
        ipsilateral = 1.0 if side == "left" else -1.0
        body_half_width = max(3.0, float(np.percentile(np.abs(points[:, 0] - center_x), 65)))
        target[0] = center_x + ipsilateral * 0.12 * body_half_width

        raw = target - entry
        # Project into the estimated endplate plane: dot(direction, normal) == 0.
        direction = raw - float(np.dot(raw, endplate_normal)) * endplate_normal
        if np.linalg.norm(direction) < 1e-6:
            direction = np.array([0.0, -1.0, 0.0])
        direction = self._normalize(direction)

        # Guard against a pathological PCA/entry combination pointing posteriorly.
        if direction[1] > -0.05:
            anterior = np.array([0.0, -1.0, 0.0])
            anterior -= float(np.dot(anterior, endplate_normal)) * endplate_normal
            direction = self._normalize(0.65 * direction + 0.35 * self._normalize(anterior))
        return direction

    def _optimize_pedicle_corridor(
        self,
        image: sitk.Image,
        label: int,
        entry: np.ndarray,
        initial_direction: np.ndarray,
        endplate_normal: np.ndarray,
    ) -> np.ndarray:
        """Choose a nearby axial trajectory with the best conservative 3D clearance."""

        initial_axial = math.degrees(
            math.atan2(float(initial_direction[0]), -float(initial_direction[1]))
        )
        best_direction = initial_direction
        best_score = -math.inf
        for offset in (-12.0, -8.0, -5.0, -2.5, 0.0, 2.5, 5.0, 8.0, 12.0):
            axial = math.radians(initial_axial + offset)
            horizontal = np.array((math.sin(axial), -math.cos(axial), 0.0), dtype=float)
            candidate = horizontal - float(np.dot(horizontal, endplate_normal)) * endplate_normal
            if np.linalg.norm(candidate) < 1e-8:
                continue
            candidate = self._normalize(candidate)
            if candidate[1] >= -0.05:
                continue
            length, warning = self._ray_length(image, label, entry, candidate)
            if warning and length <= 30.0:
                continue
            clearance = self._coarse_corridor_clearance(
                image,
                label,
                entry,
                candidate,
                endplate_normal,
                length,
            )
            score = clearance * 2.5 + min(length, 70.0) * 0.05 - abs(offset) * 0.08
            if score > best_score:
                best_score = score
                best_direction = candidate
        return best_direction

    def _coarse_corridor_clearance(
        self,
        image: sitk.Image,
        label: int,
        entry: np.ndarray,
        direction: np.ndarray,
        endplate_normal: np.ndarray,
        anatomical_length: float,
    ) -> float:
        u = np.cross(endplate_normal, direction)
        if np.linalg.norm(u) < 1e-8:
            return 0.0
        u = self._normalize(u)
        v = self._normalize(np.cross(direction, u))
        radial_directions = (
            u,
            v,
            self._normalize(u + v),
            self._normalize(u - v),
        )
        diameters: list[float] = []
        end_t = min(26.0, anatomical_length * 0.52)
        for t in np.arange(5.0, end_t + 0.01, 3.0):
            center = entry + direction * float(t)
            if not self._is_label(image, label, center):
                continue
            for radial in radial_directions:
                positive = self._distance_to_edge(
                    image, label, center, radial, max_radius_mm=12.0, step_mm=1.0
                )
                negative = self._distance_to_edge(
                    image, label, center, -radial, max_radius_mm=12.0, step_mm=1.0
                )
                diameters.append(positive + negative)
        return min(diameters) if diameters else 0.0

    def _ray_length(
        self,
        image: sitk.Image,
        label: int,
        entry: np.ndarray,
        direction: np.ndarray,
    ) -> tuple[float, str | None]:
        step = self.sample_step_mm
        distances = np.arange(0.0, 160.0 + step, step)
        inside = np.array(
            [self._is_label(image, label, entry + direction * t) for t in distances],
            dtype=bool,
        )
        hit_indices = np.flatnonzero(inside)
        if len(hit_indices) == 0:
            return 30.0, "Entry ray did not intersect the selected vertebral mask; using fallback length."

        first = int(hit_indices[0])
        if distances[first] > 10.0:
            return 30.0, "Entry point is far from the selected mask; using fallback length."

        # Allow tiny one-voxel gaps but stop after ~2 mm continuously outside the label.
        gap_limit = max(2, round(2.0 / step))
        last_inside = first
        gap = 0
        for i in range(first, len(distances)):
            if inside[i]:
                last_inside = i
                gap = 0
            else:
                gap += 1
                if gap >= gap_limit:
                    break

        exit_distance = float(distances[last_inside])
        safe = max(20.0, exit_distance - self.cortical_margin_mm)
        warning = None
        if safe <= 22.0:
            warning = "Short mask intersection; verify the marked entry point and segmentation."
        return safe, warning

    def _estimate_pedicle_width(
        self,
        image: sitk.Image,
        label: int,
        entry: np.ndarray,
        direction: np.ndarray,
        endplate_normal: np.ndarray,
        anatomical_length: float,
    ) -> float:
        # Since direction lies in the endplate plane, these form a stable cross-section basis.
        u = np.cross(endplate_normal, direction)
        if np.linalg.norm(u) < 1e-6:
            u = np.cross(np.array([0.0, 0.0, 1.0]), direction)
        u = self._normalize(u)
        v = self._normalize(np.cross(direction, u))

        start_t = min(7.0, anatomical_length * 0.15)
        end_t = min(28.0, anatomical_length * 0.52)
        if end_t <= start_t:
            end_t = min(anatomical_length * 0.8, start_t + 8.0)

        cross_section_minima: list[float] = []
        for t in np.arange(start_t, end_t + 0.01, 1.5):
            center = entry + direction * float(t)
            if not self._is_label(image, label, center):
                continue
            diameters: list[float] = []
            for angle in np.linspace(0.0, math.pi, 12, endpoint=False):
                radial = math.cos(angle) * u + math.sin(angle) * v
                positive = self._distance_to_edge(image, label, center, radial)
                negative = self._distance_to_edge(image, label, center, -radial)
                diameters.append(positive + negative)
            if diameters:
                cross_section_minima.append(min(diameters))

        if not cross_section_minima:
            return 4.5
        # Use a conservative low percentile across the full 3D corridor.
        return max(2.5, float(np.percentile(cross_section_minima, 10)))

    def _distance_to_edge(
        self,
        image: sitk.Image,
        label: int,
        center: np.ndarray,
        direction: np.ndarray,
        *,
        max_radius_mm: float = 15.0,
        step_mm: float = 0.5,
    ) -> float:
        last_inside = 0.0
        for radius in np.arange(step_mm, max_radius_mm + step_mm, step_mm):
            if not self._is_label(image, label, center + direction * float(radius)):
                return last_inside
            last_inside = float(radius)
        return last_inside

    def _standard_length(self, anatomical_length: float) -> float:
        # Keep a little extra internal margin before snapping down to a catalog length.
        target = max(STANDARD_LENGTHS_MM[0], anatomical_length - 1.0)
        candidates = [value for value in STANDARD_LENGTHS_MM if value <= target]
        return float(candidates[-1] if candidates else STANDARD_LENGTHS_MM[0])

    def _standard_diameter(self, pedicle_width: float) -> float:
        target = max(STANDARD_DIAMETERS_MM[0], pedicle_width - self.diameter_margin_mm)
        candidates = [value for value in STANDARD_DIAMETERS_MM if value <= target]
        return float(candidates[-1] if candidates else STANDARD_DIAMETERS_MM[0])

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm < 1e-12:
            raise ValueError("Cannot normalize a zero-length vector.")
        return np.asarray(vector, dtype=float) / norm

    @staticmethod
    def _label_points(image: sitk.Image, label: int, *, max_points: int) -> np.ndarray:
        array = sitk.GetArrayFromImage(image)
        zyx = np.argwhere(array == label)
        if len(zyx) == 0:
            return np.empty((0, 3), dtype=float)
        if len(zyx) > max_points:
            selection = np.linspace(0, len(zyx) - 1, max_points, dtype=int)
            zyx = zyx[selection]

        xyz_index = zyx[:, [2, 1, 0]].astype(float)
        spacing = np.asarray(image.GetSpacing(), dtype=float)
        origin = np.asarray(image.GetOrigin(), dtype=float)
        direction = np.asarray(image.GetDirection(), dtype=float).reshape(3, 3)
        return origin + (direction @ (xyz_index * spacing).T).T

    @staticmethod
    def _is_label(image: sitk.Image, label: int, point: np.ndarray) -> bool:
        try:
            continuous = image.TransformPhysicalPointToContinuousIndex(
                tuple(float(v) for v in point)
            )
        except RuntimeError:
            return False
        index = tuple(round(v) for v in continuous)
        size = image.GetSize()
        if any(index[i] < 0 or index[i] >= size[i] for i in range(3)):
            return False
        try:
            return int(image[index]) == int(label)
        except (IndexError, RuntimeError):
            return False
