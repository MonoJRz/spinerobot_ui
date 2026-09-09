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


def test_three_level_rod_uses_a_smooth_near_seat_contour() -> None:
    plans = {
        ("L3", "left"): _screw("L3", "left", (20.0, 10.0, 40.0)),
        ("L4", "left"): _screw("L4", "left", (25.0, 13.0, 20.0)),
        ("L5", "left"): _screw("L5", "left", (19.0, 17.0, 0.0)),
    }
    rod = build_rod_plan(plans, "left")
    assert rod is not None
    assert rod.levels == ("L3", "L4", "L5")
    assert rod.max_seat_gap_mm < 0.01
    assert rod.mean_seat_gap_mm < 0.01
    assert rod.max_straight_rod_offset_mm > 0.1
    assert rod.fit_state == "SEATED"
    assert rod.sagittal_curvature_reversals == 0
    assert rod.length_mm >= rod.required_length_mm
    assert np.isclose(rod.length_mm % 5.0, 0.0)


def test_four_level_candidate_uses_tulips_as_constraints_not_hard_knots() -> None:
    plans = {
        ("L2", "left"): _screw("L2", "left", (18.0, 8.0, 60.0)),
        ("L3", "left"): _screw("L3", "left", (24.0, 12.0, 40.0)),
        ("L4", "left"): _screw("L4", "left", (17.0, 15.0, 20.0)),
        ("L5", "left"): _screw("L5", "left", (22.0, 19.0, 0.0)),
    }
    rod = build_rod_plan(plans, "left")
    assert rod is not None
    assert rod.fitting_order == 2
    assert rod.max_seat_gap_mm > 0.01
    assert rod.sagittal_curvature_reversals == 0


def test_tulip_slot_follows_rod_independently_of_shank() -> None:
    plans = {
        ("L4", "left"): _screw(
            "L4", "left", (20.0, 10.0, 20.0), direction=(0.25, -1.0, 0.15)
        ),
        ("L5", "left"): _screw(
            "L5", "left", (25.0, 13.0, 0.0), direction=(-0.20, -1.0, -0.10)
        ),
    }
    rod = build_rod_plan(plans, "left")
    assert rod is not None

    for level in rod.levels:
        slot = np.asarray(rod.tulip_slot_directions_lps[level])
        shank = np.asarray(plans[(level, "left")].direction)
        assert np.isclose(np.linalg.norm(slot), 1.0)
        # The slot rotates around the shank, rather than inheriting its axis.
        assert abs(float(np.dot(slot, shank))) < 1e-6


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
