from __future__ import annotations

import numpy as np

from bart_spine_ui.planning.collision import find_screw_collisions
from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.planning.rod import build_rod_plan


def _screw(
    level: str,
    side: str,
    entry: tuple[float, float, float],
    direction: tuple[float, float, float] = (0.0, -1.0, 0.0),
    length: float = 40.0,
) -> ScrewPlan:
    d = np.asarray(direction, dtype=float)
    d /= np.linalg.norm(d)
    endpoint = np.asarray(entry, dtype=float) + d * length
    return ScrewPlan(
        level=level,
        side=side,
        entry_point=entry,
        direction=tuple(float(v) for v in d),
        endpoint=tuple(float(v) for v in endpoint),
        anatomical_length_mm=length + 4.0,
        pedicle_width_mm=8.0,
        diameter_mm=6.5,
        length_mm=length,
        endplate_normal=(0.0, 0.0, 1.0),
    )


def test_build_rod_requires_two_screws() -> None:
    plans = {("L2", "left"): _screw("L2", "left", (20.0, 10.0, 40.0))}
    assert build_rod_plan(plans, "left") is None


def test_three_level_rod_interpolates_all_seats() -> None:
    plans = {
        ("L3", "left"): _screw("L3", "left", (20.0, 10.0, 40.0)),
        ("L4", "left"): _screw("L4", "left", (25.0, 13.0, 20.0)),
        ("L5", "left"): _screw("L5", "left", (19.0, 17.0, 0.0)),
    }
    rod = build_rod_plan(plans, "left")
    assert rod is not None
    assert rod.levels == ("L3", "L4", "L5")
    assert rod.max_seat_gap_mm < 1e-6
    assert rod.mean_seat_gap_mm < 1e-6
    assert rod.max_straight_rod_offset_mm > 0.1
    assert rod.fit_state == "SEATED"


def test_crossing_screws_are_detected() -> None:
    plans = {
        ("L4", "left"): _screw("L4", "left", (10.0, 10.0, 0.0), (-0.25, -1.0, 0.0), 35.0),
        ("L4", "right"): _screw("L4", "right", (-10.0, 10.0, 0.0), (0.25, -1.0, 0.0), 35.0),
    }
    collisions = find_screw_collisions(plans)
    assert collisions
    assert collisions[0].overlap_mm > 0.0


def test_separated_screws_are_not_collisions() -> None:
    plans = {
        ("L3", "left"): _screw("L3", "left", (20.0, 10.0, 20.0)),
        ("L5", "left"): _screw("L5", "left", (20.0, 10.0, -20.0)),
    }
    assert find_screw_collisions(plans) == []
