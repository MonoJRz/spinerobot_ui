"""Focused checks for the reference-aligned mesh/coverage grading."""
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from bart_spine_ui.imaging.conversion import sitk_to_vtk
from bart_spine_ui.imaging.models import MedicalVolume
from bart_spine_ui.planning.assessment import ScrewAssessmentService, gertzbein_robbins
from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.segmentation.models import SegmentationVolume


def scene(entry_x=10.):
    mask = np.zeros((64, 64, 64), dtype=np.uint8)
    mask[5:59, 5:59, 5:45] = 1
    image = sitk.GetImageFromArray(mask)
    ct = sitk.GetImageFromArray(np.full(mask.shape, 350, dtype=np.float32))
    segmentation = SegmentationVolume(image, sitk_to_vtk(image), {1: 'L3'}, Path('.'))
    volume = MedicalVolume('CT', ct, sitk_to_vtk(ct))
    plan = ScrewPlan('L3', 'left', (entry_x, 30., 30.), (1., 0., 0.),
                     (entry_x+20, 30., 30.), 20, 8, 4, 20, (0, 0, 1))
    return ScrewAssessmentService(segmentation), volume, plan


def test_reference_thresholds():
    for value, grade in ((0, 'A'), (.1, 'B'), (2, 'B'), (2.01, 'C'),
                         (4, 'C'), (4.01, 'D'), (6, 'D'), (6.01, 'E')):
        assert gertzbein_robbins(value) == grade


def test_contained_real_mesh_and_hu():
    service, volume, plan = scene()
    result = service.assess(plan, volume)
    assert result.grade == 'A'
    assert result.breach_mm == 0
    assert result.screw_mesh.GetNumberOfPoints() > 100
    assert result.screw_mesh.GetBounds()[0] >= 20-1e-5  # fixed 10 mm exclusion
    np.testing.assert_allclose(result.hu, 350)


def test_voxel_coverage_does_not_grade_tiny_surface_offset():
    service, volume, plan = scene(24.7)
    # Tip at 44.7: 0.2 mm beyond the 44.5 isosurface, still positive
    # interpolated label coverage. The old envelope method flagged a B.
    result = service.assess(plan, volume)
    assert result.grade == 'A'
    assert result.breach_point_lps is None


def test_outside_mesh_distance_and_red_line_agree():
    service, volume, plan = scene(28.)
    result = service.assess(plan, volume)
    assert result.grade == 'C'
    assert 2 < result.breach_mm <= 4
    assert np.isclose(np.linalg.norm(np.array(result.breach_point_lps)-result.bone_point_lps),
                      result.breach_mm)
    assert result.breach_depth_mm >= 10
