"""Slice sections of the finite, cylindrical planned screw envelope (millimetres)."""

import vtk

from .models import ScrewPlan


def screw_slice_intersection(plan: ScrewPlan, slice_axes: vtk.vtkMatrix4x4):
    """Return filled section and outline in slice coordinates at z=0.

    The envelope uses the planned outer diameter and entry/endpoint, with flat
    end caps. Threads, tip taper and tulip are not represented by this model.
    """
    line = vtk.vtkLineSource()
    line.SetPoint1(*plan.entry_point)
    line.SetPoint2(*plan.endpoint)
    tube = vtk.vtkTubeFilter()
    tube.SetInputConnection(line.GetOutputPort())
    tube.SetRadius(plan.diameter_mm / 2.0)
    tube.SetNumberOfSides(128)
    tube.CappingOn()

    inverse = vtk.vtkMatrix4x4()
    vtk.vtkMatrix4x4.Invert(slice_axes, inverse)
    transform = vtk.vtkTransform()
    transform.SetMatrix(inverse)
    local = vtk.vtkTransformPolyDataFilter()
    local.SetTransform(transform)
    local.SetInputConnection(tube.GetOutputPort())
    plane = vtk.vtkPlane()
    plane.SetOrigin(0, 0, 0)
    plane.SetNormal(0, 0, 1)
    cutter = vtk.vtkCutter()
    cutter.SetCutFunction(plane)
    cutter.SetInputConnection(local.GetOutputPort())
    clean = vtk.vtkCleanPolyData()
    clean.SetInputConnection(cutter.GetOutputPort())
    fill = vtk.vtkContourTriangulator()
    fill.SetInputConnection(clean.GetOutputPort())
    fill.Update()
    section = vtk.vtkPolyData()
    section.DeepCopy(fill.GetOutput())
    outline = vtk.vtkPolyData()
    outline.DeepCopy(clean.GetOutput())
    return section, outline


def screw_alignment_guide(plan: ScrewPlan, slice_axes: vtk.vtkMatrix4x4) -> vtk.vtkPolyData:
    """Long dotted projection of the screw axis, centered on its entry point.

    This orientation guide is independent of the finite screw/slice intersection.
    A perpendicular screw has no projected direction and produces no guide.
    """
    import math

    inverse = vtk.vtkMatrix4x4()
    vtk.vtkMatrix4x4.Invert(slice_axes, inverse)
    entry = inverse.MultiplyPoint((*plan.entry_point, 1.0))
    end = inverse.MultiplyPoint((*plan.endpoint, 1.0))
    dx, dy = end[0] - entry[0], end[1] - entry[1]
    length = math.hypot(dx, dy)
    geometry = vtk.vtkPolyData()
    if length < 1e-6:
        return geometry
    dx, dy = dx / length, dy / length
    points = vtk.vtkPoints()
    lines = vtk.vtkCellArray()
    # Explicit short segments work across VTK renderers without line-stipple support.
    for distance in range(-600, 601):
        first = points.InsertNextPoint(entry[0] + distance * dx, entry[1] + distance * dy, 0)
        last = points.InsertNextPoint(
            entry[0] + (distance + 0.7) * dx, entry[1] + (distance + 0.7) * dy, 0
        )
        lines.InsertNextCell(2)
        lines.InsertCellPoint(first)
        lines.InsertCellPoint(last)
    geometry.SetPoints(points)
    geometry.SetLines(lines)
    return geometry
