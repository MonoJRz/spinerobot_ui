import numpy as np
import pytest
import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy

from bart_spine_ui.planning.models import ScrewPlan
from bart_spine_ui.planning.slice_intersection import screw_slice_intersection


def plan(start, end, diameter=6):
    vector = np.asarray(end) - start
    length = np.linalg.norm(vector)
    return ScrewPlan(
        "L4",
        "left",
        tuple(start),
        tuple(vector / length),
        tuple(end),
        length,
        8,
        diameter,
        length,
        (0, 0, 1),
    )


def axes(z=0):
    matrix = vtk.vtkMatrix4x4()
    matrix.Identity()
    matrix.SetElement(2, 3, z)
    return matrix


def area(section):
    properties = vtk.vtkMassProperties()
    properties.SetInputData(section)
    return properties.GetSurfaceArea()


def test_perpendicular_section_has_actual_diameter_and_area():
    section, outline = screw_slice_intersection(plan((0, 0, -10), (0, 0, 10)), axes())
    assert section.GetNumberOfPolys() > 0
    assert outline.GetNumberOfLines() > 0
    assert area(section) == pytest.approx(np.pi * 9, rel=0.002)
    assert section.GetBounds() == pytest.approx((-3, 3, -3, 3, 0, 0), abs=0.005)


def test_parallel_section_shrinks_with_slice_offset_and_stops_at_radius():
    screw = plan((0, -20, 0), (0, 20, 0))
    for z in (0, 1, 2.9):
        section, _ = screw_slice_intersection(screw, axes(z))
        assert area(section) == pytest.approx(40 * 2 * np.sqrt(9 - z * z), rel=0.015)
    section, outline = screw_slice_intersection(screw, axes(3.01))
    assert section.GetNumberOfCells() == outline.GetNumberOfCells() == 0


def test_finite_length_does_not_extend_past_tip_or_entry():
    screw = plan((0, 0, -10), (0, 0, 10))
    for z in (-10.01, 10.01):
        section, outline = screw_slice_intersection(screw, axes(z))
        assert section.GetNumberOfCells() == outline.GetNumberOfCells() == 0


def test_oblique_section_and_patient_transform():
    screw = plan((-20, 0, -20), (20, 0, 20))
    section, _ = screw_slice_intersection(screw, axes())
    assert area(section) == pytest.approx(np.pi * 9 * np.sqrt(2), rel=0.002)
    transform = vtk.vtkTransform()
    transform.Translate(40, -20, 100)
    transform.RotateWXYZ(37, 1, 2, 3)
    moved = plan(
        transform.TransformPoint(screw.entry_point), transform.TransformPoint(screw.endpoint)
    )
    transformed, _ = screw_slice_intersection(moved, transform.GetMatrix())
    assert area(transformed) == pytest.approx(area(section), rel=0.002)
    assert np.max(np.abs(vtk_to_numpy(transformed.GetPoints().GetData())[:, 2])) < 1e-5
