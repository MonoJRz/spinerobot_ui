"""Mesh preparation shared by the CAD exporter and its tests."""

import re
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk

from ..segmentation.colors import MEDICAL_SEGMENTATION_COLORS
from ..segmentation.surfaces import create_smoothed_segmentation_surface


def clean(poly):
    c = vtk.vtkCleanPolyData()
    c.SetInputData(poly)
    c.Update()
    t = vtk.vtkTriangleFilter()
    t.SetInputConnection(c.GetOutputPort())
    t.Update()
    n = vtk.vtkPolyDataNormals()
    n.SetInputConnection(t.GetOutputPort())
    n.ConsistencyOn()
    n.AutoOrientNormalsOn()
    n.SplittingOff()
    n.Update()
    p = vtk.vtkPolyData()
    p.DeepCopy(n.GetOutput())
    return p


def transform(poly, matrix):
    mat = vtk.vtkMatrix4x4()
    for i in range(4):
        for j in range(4):
            mat.SetElement(i, j, float(matrix[i, j]))
    tr = vtk.vtkTransform()
    tr.SetMatrix(mat)
    f = vtk.vtkTransformPolyDataFilter()
    f.SetInputData(poly)
    f.SetTransform(tr)
    f.Update()
    return clean(f.GetOutput())


def threaded_screw(diameter, length):
    # One closed radial surface avoids overlapping internal thread/core meshes.
    radius = diameter / 2
    pitch = 2.5
    n = 24
    nz = max(2, round(length / pitch * 6))
    tip_length = diameter * 0.75
    pts = []
    for j in range(nz):
        z = length * j / nz
        for k in range(n):
            theta = 2 * np.pi * k / n
            phase = (z / pitch - k / n) % 1
            crest = max(0.0, 1 - abs(phase - 0.5) / 0.35)
            r = radius * (0.72 + 0.28 * crest) * min(1.0, (length - z) / tip_length)
            pts.append((r * np.cos(theta), r * np.sin(theta), z))
    bottom = len(pts)
    pts.append((0, 0, 0))
    tip = len(pts)
    pts.append((0, 0, length))
    faces = []
    for j in range(nz - 1):
        for k in range(n):
            a = j * n + k
            b = j * n + (k + 1) % n
            c = (j + 1) * n + (k + 1) % n
            d = (j + 1) * n + k
            faces.extend([(a, b, c), (a, c, d)])
    for k in range(n):
        faces.append((bottom, (k + 1) % n, k))
        faces.append(((nz - 1) * n + k, (nz - 1) * n + (k + 1) % n, tip))
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.array(pts), deep=True))
    cells = vtk.vtkCellArray()
    for face in faces:
        cells.InsertNextCell(3)
        for v in face:
            cells.InsertCellPoint(v)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    return clean(poly)


def write_stl(poly, path):
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(str(path))
    writer.SetFileTypeToBinary()
    writer.SetInputData(poly)
    if not writer.Write():
        raise OSError(f"Could not write {path}")


def vertebra_surfaces(label_image, labels, target_faces=12000):
    """Apply exactly the viewer's extraction, then reduce only the CAD copy."""
    surface = create_smoothed_segmentation_surface(label_image)
    for label, name in labels.items():
        if not re.fullmatch(r"[CTL][1-9][0-9]?", name):
            raise ValueError(f"Unsupported vertebra name: {name}")
        threshold = vtk.vtkThreshold()
        threshold.SetInputData(surface)
        threshold.SetInputArrayToProcess(
            0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS, "VertebraLabel"
        )
        threshold.SetLowerThreshold(int(label))
        threshold.SetUpperThreshold(int(label))
        threshold.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
        geometry = vtk.vtkGeometryFilter()
        geometry.SetInputConnection(threshold.GetOutputPort())
        geometry.Update()
        full = clean(geometry.GetOutput())
        if not full.GetNumberOfCells():
            continue
        reduced = full
        if full.GetNumberOfCells() > target_faces:
            decimate = vtk.vtkQuadricDecimation()
            decimate.SetInputData(full)
            decimate.SetTargetReduction(1 - target_faces / full.GetNumberOfCells())
            decimate.VolumePreservationOn()
            decimate.Update()
            reduced = clean(decimate.GetOutput())
        color = tuple(c / 255 for c in MEDICAL_SEGMENTATION_COLORS[int(label) - 1])
        yield name, reduced, full, color


def screw_transform(plan):
    entry = np.asarray(plan["entry_point_lps_mm"], dtype=float)
    z = np.asarray(plan["direction_lps"], dtype=float)
    length = float(plan["screw_length_mm"])
    diameter = float(plan["screw_diameter_mm"])
    if (
        entry.shape != (3,)
        or z.shape != (3,)
        or not np.isfinite(entry).all()
        or not np.isfinite(z).all()
        or np.linalg.norm(z) < 1e-9
        or not np.isfinite([length, diameter]).all()
        or length <= 0
        or diameter <= 0
    ):
        raise ValueError("Screw coordinates and dimensions must be finite and nonzero.")
    z /= np.linalg.norm(z)
    reference = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(z, reference)) > 0.99:
        reference = np.array([1.0, 0.0, 0.0])
    x = reference - z * np.dot(reference, z)
    x /= np.linalg.norm(x)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack([x, np.cross(z, x), z])
    matrix[:3, 3] = entry
    endpoint = entry + length * z
    if "endpoint_lps_mm" in plan and not np.allclose(
        endpoint, plan["endpoint_lps_mm"], atol=1e-3, rtol=0
    ):
        raise ValueError("Screw endpoint disagrees with its direction and length.")
    return matrix


def implant_surfaces(plans):
    head_file = (
        Path(__file__).resolve().parents[1]
        / "assets/model/src/bart_spine_implant_models/assets/tulip/tulip_head.stl"
    )
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(head_file))
    reader.Update()
    if not reader.GetOutput().GetNumberOfCells():
        raise FileNotFoundError(f"Tulip mesh unavailable: {head_file}")
    seen = set()
    for plan in plans:
        level, side = plan["level"], plan["side"]
        if not re.fullmatch(r"[CTL][1-9][0-9]?", level) or side not in ("left", "right"):
            raise ValueError("Invalid screw level or side.")
        if (level, side) in seen:
            raise ValueError(f"Duplicate screw: {level} {side}")
        seen.add((level, side))
        matrix = screw_transform(plan)
        shaft = threaded_screw(float(plan["screw_diameter_mm"]), float(plan["screw_length_mm"]))
        yield f"Screw_{level}_{side}", transform(shaft, matrix), (0.15, 0.7, 0.95)
        yield f"Head_{level}_{side}", transform(reader.GetOutput(), matrix), (0.95, 0.64, 0.16)
