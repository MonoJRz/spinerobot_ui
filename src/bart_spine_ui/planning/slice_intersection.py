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
