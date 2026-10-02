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


def test_model_coverage_is_independent_of_hu_and_ct_sample_support():
    service, volume, plan = scene()
    original = service.assess(plan, volume)
    assert original.model_coverage == 1
    volume.sitk_image = sitk.GetImageFromArray(np.full((64, 64, 64), 35, dtype=np.float32))
    low_hu = service.assess(plan, volume)
    assert low_hu.model_coverage == original.model_coverage
    np.testing.assert_allclose(low_hu.hu, 35)
    volume.sitk_image = sitk.GetImageFromArray(np.full((64, 64, 64), np.nan, dtype=np.float32))
    missing_ct = service.assess(plan, volume)
    assert missing_ct.model_coverage == 1
    assert np.isnan(missing_ct.hu).all()
    assert not missing_ct.coverage.any()


def test_model_coverage_reduces_for_real_geometric_breach():
    service, volume, plan = scene(28.)
    result = service.assess(plan, volume)
    assert 0 < result.model_coverage < 1
    service, volume, plan = scene(47.)
    result = service.assess(plan, volume)
    assert result.model_coverage == 0


def test_surface_coverage_is_area_weighted_and_rejects_open_mesh():
    import pytest
    import vtk

    from bart_spine_ui.planning.assessment import surface_area_coverage

    cube = vtk.vtkCubeSource()
    cube.SetBounds(-1, 3, -1, 3, -1, 1)
    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(cube.GetOutputPort())
    clean.Update()
    # Inside area 2, outside area 0.5: 80%, not a vertex-count percentage of 50%.
    points = vtk.vtkPoints()
    for point in ((0, 0, 0), (2, 0, 0), (0, 2, 0),
                  (4, 0, 0), (5, 0, 0), (4, 1, 0)):
        points.InsertNextPoint(*point)
    cells = vtk.vtkCellArray()
    for ids in ((0, 1, 2), (3, 4, 5)):
        cells.InsertNextCell(3, ids)
    mesh = vtk.vtkPolyData()
    mesh.SetPoints(points)
    mesh.SetPolys(cells)
    assert np.isclose(surface_area_coverage(mesh, clean.GetOutput()), .8)
    with pytest.raises(ValueError, match='not closed'):
        surface_area_coverage(mesh, mesh)


def test_cropped_model_is_unavailable_not_zero_or_full_coverage():
    service, volume, plan = scene()
    array = sitk.GetArrayFromImage(service.segmentation.sitk_image)
    array[0, 30, 30] = 1
    service.segmentation.sitk_image = sitk.GetImageFromArray(array)
    result = service.assess(plan, volume)
    assert result.model_coverage is None
    assert result.model_coverage_reason


def test_shell_sample_fraction_is_not_geometric_screw_coverage():
    from dataclasses import replace

    service, volume, plan = scene()
    plan = replace(plan, entry_point=(10., 6.7, 30.), endpoint=(30., 6.7, 30.))
    result = service.assess(plan, volume)
    assert np.mean(result.coverage) < .95  # External HU shell extends out of bone.
    assert np.isclose(result.model_coverage, 1.)  # Screw itself remains inside.


def test_model_coverage_uses_same_entry_exclusion_as_grading():
    service, volume, plan = scene(-3.)
    result = service.assess(plan, volume)
    assert np.mean(result.coverage) < .8
    assert np.isclose(result.model_coverage, 1.)  # First 10 mm are intentionally excluded.
