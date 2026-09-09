import numpy as np
import SimpleITK as sitk

from bart_spine_ui.imaging.models import MedicalVolume
from bart_spine_ui.planning import PediclePlanningService, ScrewPlan, parse_levels_of_interest
from bart_spine_ui.segmentation import SegmentationVolume


def test_parse_levels_of_interest_range():
    assert parse_levels_of_interest("L3 – L5") == ["L3", "L4", "L5"]
    assert parse_levels_of_interest("T11-L2") == ["T11", "T12", "L1", "L2"]


def test_estimated_direction_is_parallel_to_estimated_endplate():
    # Synthetic L4: a long anterior-posterior rectangular vertebral mask.
    array = np.zeros((50, 90, 80), dtype=np.uint16)  # z, y, x
    array[15:35, 10:75, 20:60] = 16
    image = sitk.GetImageFromArray(array)
    image.SetSpacing((1.0, 1.0, 1.0))
    image.SetOrigin((0.0, 0.0, 0.0))
    segmentation = SegmentationVolume(
        sitk_image=image,
        vtk_image=None,
        labels={16: "L4"},
        source_directory=None,
    )

    service = PediclePlanningService()
    plan = service.estimate(segmentation, "L4", "left", (50.0, 73.0, 25.0))
    direction = np.asarray(plan.direction)
    normal = np.asarray(plan.endplate_normal)

    assert abs(float(np.dot(direction, normal))) < 1e-6
    assert direction[1] < 0.0  # LPS: anterior is -Y
    assert plan.anatomical_length_mm > 20.0
    assert 3.0 <= plan.diameter_mm <= 8.0
    assert 25.0 <= plan.length_mm <= 80.0


def test_suggested_focus_uses_largest_posterolateral_axial_slice():
    array = np.zeros((15, 30, 30), dtype=np.uint16)  # z, y, x
    # A small left posterior region through several slices.
    array[3:12, 20:24, 18:22] = 16
    # The pedicle region is deliberately widest on axial index 8.
    array[8, 18:27, 16:28] = 16
    image = sitk.GetImageFromArray(array)
    image.SetSpacing((0.7, 0.8, 1.5))
    image.SetOrigin((4.0, 5.0, 10.0))
    segmentation = SegmentationVolume(
        sitk_image=image,
        vtk_image=None,
        labels={16: "L4"},
        source_directory=None,
    )

    focus = PediclePlanningService().suggested_focus_point(
        segmentation, "L4", "left"
    )

    assert image.TransformPhysicalPointToIndex(focus)[2] == 8


def test_screw_plan_angles_update_direction_endpoint_and_json():
    plan = ScrewPlan(
        level="L4",
        side="left",
        entry_point=(10.0, 20.0, 30.0),
        direction=(0.0, -1.0, 0.0),
        endpoint=(10.0, -20.0, 30.0),
        anatomical_length_mm=44.0,
        pedicle_width_mm=7.0,
        diameter_mm=6.0,
        length_mm=40.0,
        endplate_normal=(0.0, 0.0, 1.0),
    )

    updated = plan.with_angles(axial_angle_deg=15.0, sagittal_angle_deg=-10.0)

    assert np.isclose(updated.axial_angle_deg, 15.0)
    assert np.isclose(updated.sagittal_angle_deg, -10.0)
    assert np.isclose(np.linalg.norm(updated.direction), 1.0)
    assert np.isclose(
        np.linalg.norm(np.asarray(updated.endpoint) - np.asarray(updated.entry_point)),
        40.0,
    )
    assert updated.to_dict()["axial_angle_deg"] == 15.0
    assert updated.to_dict()["sagittal_angle_deg"] == -10.0


def test_screw_plans_round_trip_through_case_json(tmp_path):
    image = sitk.Image((2, 2, 2), sitk.sitkInt16)
    volume = MedicalVolume(
        name="case",
        sitk_image=image,
        vtk_image=None,
        source_path=tmp_path,
    )
    plan = ScrewPlan(
        level="L4",
        side="left",
        entry_point=(10.0, 20.0, 30.0),
        direction=(0.0, -1.0, 0.0),
        endpoint=(10.0, -20.0, 30.0),
        anatomical_length_mm=44.0,
        pedicle_width_mm=7.0,
        diameter_mm=6.0,
        length_mm=40.0,
        endplate_normal=(0.0, 0.0, 1.0),
    ).with_angles(axial_angle_deg=12.0, sagittal_angle_deg=4.0)
    service = PediclePlanningService()

    path = service.save_plans(
        volume,
        {("L4", "left"): plan},
        case_region="L4",
        accepted={("L4", "left")},
    )
    loaded, accepted = service.load_plans(volume)

    assert path == tmp_path / "planning" / "pedicle_screws.json"
    assert np.isclose(loaded[("L4", "left")].axial_angle_deg, 12.0)
    assert np.isclose(loaded[("L4", "left")].sagittal_angle_deg, 4.0)
    assert accepted == {("L4", "left")}


def test_endplate_normal_follows_fitted_superior_surface_slope():
    points = []
    for x in np.linspace(-12.0, 12.0, 13):
        for y in np.linspace(-20.0, 8.0, 15):
            top_z = 30.0 + 0.2 * y
            for z in np.linspace(top_z - 10.0, top_z, 6):
                points.append((x, y, z))
    service = PediclePlanningService()

    normal = service._estimate_endplate_normal(np.asarray(points))
    expected = np.asarray((0.0, -0.2, 1.0))
    expected /= np.linalg.norm(expected)

    assert float(np.dot(normal, expected)) > 0.98
