from __future__ import annotations

from functools import lru_cache

import numpy as np
import vtk

from .catalog import screw_asset_path, tulip_asset_path


def _unit(vector) -> np.ndarray:
    v = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(v))
    if norm < 1e-9:
        raise ValueError("Direction vector must be non-zero.")
    return v / norm


def _default_slot(shank: np.ndarray) -> np.ndarray:
    reference = np.array([0.0, 0.0, 1.0], dtype=float)
    slot = np.cross(shank, reference)
    if float(np.linalg.norm(slot)) < 1e-8:
        reference = np.array([1.0, 0.0, 0.0], dtype=float)
        slot = np.cross(shank, reference)
    return _unit(slot)


def local_to_world_matrix(
    origin_lps_mm,
    shank_direction_lps,
    slot_direction_lps=None,
) -> vtk.vtkMatrix4x4:
    """Return local implant frame -> patient LPS transform.

    Local model convention:
      origin = pedicle entry / distal tulip plane
      +Z = screw axis from entry toward screw tip
      +X = tulip U-slot / rod direction
      +Y = right-handed across-slot direction

    For the screw shaft, rotation around +Z is visually irrelevant.
    For the tulip, pass the local rod tangent as slot_direction_lps.
    The slot is projected into the plane normal to the screw shank,
    matching the existing BART rod-planning logic.
    """
    origin = np.asarray(origin_lps_mm, dtype=float)
    z_axis = _unit(shank_direction_lps)

    if slot_direction_lps is None:
        x_axis = _default_slot(z_axis)
    else:
        requested = np.asarray(slot_direction_lps, dtype=float)
        x_axis = requested - z_axis * float(np.dot(requested, z_axis))
        if float(np.linalg.norm(x_axis)) < 1e-8:
            x_axis = _default_slot(z_axis)
        else:
            x_axis = _unit(x_axis)

    y_axis = _unit(np.cross(z_axis, x_axis))
    # Re-orthogonalize X to avoid accumulated numerical error.
    x_axis = _unit(np.cross(y_axis, z_axis))

    matrix = vtk.vtkMatrix4x4()
    matrix.Identity()
    for row in range(3):
        matrix.SetElement(row, 0, float(x_axis[row]))
        matrix.SetElement(row, 1, float(y_axis[row]))
        matrix.SetElement(row, 2, float(z_axis[row]))
        matrix.SetElement(row, 3, float(origin[row]))
    return matrix


@lru_cache(maxsize=300)
def _read_stl(path_string: str) -> vtk.vtkPolyData:
    reader = vtk.vtkSTLReader()
    reader.SetFileName(path_string)
    reader.Update()
    poly = vtk.vtkPolyData()
    poly.DeepCopy(reader.GetOutput())
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.SplittingOff()
    normals.Update()
    out = vtk.vtkPolyData()
    out.DeepCopy(normals.GetOutput())
    return out


def _actor(polydata: vtk.vtkPolyData, matrix: vtk.vtkMatrix4x4, color, opacity: float):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.SetUserMatrix(matrix)
    actor.GetProperty().SetColor(*[float(v) for v in color])
    actor.GetProperty().SetOpacity(float(opacity))
    actor.GetProperty().SetInterpolationToPhong()
    actor.GetProperty().SetAmbient(0.12)
    actor.GetProperty().SetDiffuse(0.72)
    actor.GetProperty().SetSpecular(0.32)
    actor.GetProperty().SetSpecularPower(36.0)
    actor.PickableOff()
    return actor


def make_screw_actor(
    diameter_mm: float,
    length_mm: float,
    entry_point_lps_mm,
    shank_direction_lps,
    *,
    color=(0.20, 0.78, 1.0),
    opacity: float = 1.0,
) -> vtk.vtkActor:
    path = screw_asset_path(diameter_mm, length_mm)
    matrix = local_to_world_matrix(entry_point_lps_mm, shank_direction_lps)
    return _actor(_read_stl(str(path)), matrix, color, opacity)


def make_tulip_actor(
    entry_point_lps_mm,
    shank_direction_lps,
    rod_slot_direction_lps=None,
    *,
    color=(1.0, 0.70, 0.16),
    opacity: float = 1.0,
) -> vtk.vtkActor:
    path = tulip_asset_path()
    matrix = local_to_world_matrix(
        entry_point_lps_mm,
        shank_direction_lps,
        rod_slot_direction_lps,
    )
    return _actor(_read_stl(str(path)), matrix, color, opacity)


def assembly_actors(
    plan,
    *,
    rod_slot_direction_lps=None,
    screw_color=(0.20, 0.78, 1.0),
    tulip_color=(1.0, 0.70, 0.16),
    opacity: float = 1.0,
) -> tuple[vtk.vtkActor, vtk.vtkActor]:
    """Create separate screw and tulip actors from a BART ScrewPlan-like object."""
    screw = make_screw_actor(
        plan.diameter_mm,
        plan.length_mm,
        plan.entry_point,
        plan.direction,
        color=screw_color,
        opacity=opacity,
    )
    tulip = make_tulip_actor(
        plan.entry_point,
        plan.direction,
        rod_slot_direction_lps,
        color=tulip_color,
        opacity=opacity,
    )
    return screw, tulip
