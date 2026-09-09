from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

Side = Literal["left", "right"]

# Simplified tulip geometry shared by screw rendering and rod-seat placement.
HEAD_DIAMETER_MM = 13.0
HEAD_HEIGHT_MM = 15.0
TULIP_SLOT_WIDTH_MM = 6.0


@dataclass(slots=True)
class ScrewPlan:
    """One editable pedicle screw plan in patient LPS coordinates (millimetres)."""

    level: str
    side: Side
    entry_point: tuple[float, float, float]
    direction: tuple[float, float, float]
    endpoint: tuple[float, float, float]
    anatomical_length_mm: float
    pedicle_width_mm: float
    diameter_mm: float
    length_mm: float
    endplate_normal: tuple[float, float, float]
    pedicle_midpoint: tuple[float, float, float] | None = None
    screw_tip_point: tuple[float, float, float] | None = None
    trajectory_method: str = "STP"
    warning: str | None = None

    @property
    def axial_angle_deg(self) -> float:
        """Axial angle relative to anterior (-Y in LPS), positive toward +X."""

        direction = np.asarray(self.direction, dtype=float)
        return float(math.degrees(math.atan2(direction[0], -direction[1])))

    @property
    def sagittal_angle_deg(self) -> float:
        """Cranial/caudal angle relative to the axial plane."""

        direction = np.asarray(self.direction, dtype=float)
        axial_length = float(np.hypot(direction[0], direction[1]))
        return float(math.degrees(math.atan2(direction[2], axial_length)))

    def with_dimensions(
        self,
        *,
        diameter_mm: float | None = None,
        length_mm: float | None = None,
    ) -> ScrewPlan:
        diameter = self.diameter_mm if diameter_mm is None else float(diameter_mm)
        length = self.length_mm if length_mm is None else float(length_mm)
        start = np.asarray(self.entry_point, dtype=float)
        direction = np.asarray(self.direction, dtype=float)
        endpoint = start + direction * length
        return replace(
            self,
            diameter_mm=diameter,
            length_mm=length,
            endpoint=tuple(float(v) for v in endpoint),
        )

    def with_angles(
        self,
        *,
        axial_angle_deg: float,
        sagittal_angle_deg: float,
    ) -> ScrewPlan:
        axial = math.radians(float(axial_angle_deg))
        sagittal = math.radians(float(sagittal_angle_deg))
        cos_sagittal = math.cos(sagittal)
        direction = np.array(
            (
                math.sin(axial) * cos_sagittal,
                -math.cos(axial) * cos_sagittal,
                math.sin(sagittal),
            ),
            dtype=float,
        )
        direction /= np.linalg.norm(direction)
        entry = np.asarray(self.entry_point, dtype=float)
        endpoint = entry + direction * self.length_mm
        return replace(
            self,
            direction=tuple(float(v) for v in direction),
            endpoint=tuple(float(v) for v in endpoint),
        )

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "side": self.side,
            "entry_point_lps_mm": list(self.entry_point),
            "direction_lps": list(self.direction),
            "endpoint_lps_mm": list(self.endpoint),
            "estimated_anatomical_length_mm": round(self.anatomical_length_mm, 2),
            "estimated_pedicle_width_mm": round(self.pedicle_width_mm, 2),
            "screw_diameter_mm": round(self.diameter_mm, 2),
            "screw_length_mm": round(self.length_mm, 2),
            "axial_angle_deg": round(self.axial_angle_deg, 2),
            "sagittal_angle_deg": round(self.sagittal_angle_deg, 2),
            "estimated_endplate_normal_lps": list(self.endplate_normal),
            "pedicle_midpoint_lps_mm": (
                list(self.pedicle_midpoint) if self.pedicle_midpoint is not None else None
            ),
            "screw_tip_point_lps_mm": (
                list(self.screw_tip_point) if self.screw_tip_point is not None else None
            ),
            "trajectory_method": self.trajectory_method,
            "warning": self.warning,
        }
