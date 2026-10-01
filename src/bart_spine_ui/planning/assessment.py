"""Sampled directed Hausdorff breach and peri-screw CT attenuation.

Distances use the unsmoothed label boundary in patient LPS millimetres.
An explicit entry-distance band is excluded from grading (intentional entry opening).
Whole-vertebra masks yield an estimated G-R category, not an isolated pedicle grade.
"""
from dataclasses import dataclass, field

import numpy as np
import SimpleITK as sitk
import vtk
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

from ..assets.model.src.bart_spine_implant_models import make_screw_actor

DEFAULT_ENTRY_EXCLUSION_MM = 10.0


@dataclass
class ScrewAssessment:
    breach_mm: float | None
    grade: str
    depth_mm: np.ndarray
    hu: np.ndarray
    coverage: np.ndarray
    reason: str = ""
    entry_exclusion_mm: float = DEFAULT_ENTRY_EXCLUSION_MM
    breach_point_lps: tuple[float, float, float] | None = None
    bone_point_lps: tuple[float, float, float] | None = None
    breach_depth_mm: float | None = None
    voxel_spacing_mm: tuple[float, float, float] | None = None
    boundary_mesh: vtk.vtkPolyData | None = field(default=None, repr=False, compare=False)

    screw_mesh: vtk.vtkPolyData | None = field(default=None, repr=False, compare=False)

    @property
    def below_voxel_spacing(self):
        return (self.breach_mm is not None and self.voxel_spacing_mm is not None
                and 0 < self.breach_mm < min(self.voxel_spacing_mm))

    @property
    def breach_text(self):
        if self.breach_mm is None:
            return "—"
        return "<0.1 mm" if 0 < self.breach_mm < .05 else f"{self.breach_mm:.1f} mm"



def gertzbein_robbins(distance):
    if distance is None or not np.isfinite(distance) or distance < 0:
        return "—"
    if distance == 0:
        return "A"
    return "B" if distance <= 2 else "C" if distance <= 4 else "D" if distance <= 6 else "E"


def sample_image(image, points, *, nearest=False):
    """Physical LPS -> voxel coordinates; never clamp out-of-image samples."""
    array = sitk.GetArrayViewFromImage(image)
    direction = np.asarray(image.GetDirection()).reshape(3, 3)
    xyz = ((points - image.GetOrigin()) @ np.linalg.inv(direction).T) / image.GetSpacing()
    valid = np.all((xyz >= 0) & (xyz <= np.array(image.GetSize()) - 1), axis=-1)
    safe = np.where(valid[..., None], xyz, 0)
    if nearest:
        idx = np.rint(safe).astype(int)
        values = array[idx[..., 2], idx[..., 1], idx[..., 0]].astype(float)
    else:
        lo = np.floor(safe).astype(int)
        hi = np.minimum(lo + 1, np.array(image.GetSize()) - 1)
        fraction = safe - lo
        values = np.zeros(valid.shape)
        for x in (0, 1):
            for y in (0, 1):
                for z in (0, 1):
                    index = np.stack([hi[..., k] if bit else lo[..., k]
                                      for k, bit in enumerate((x, y, z))], axis=-1)
                    weight = np.prod(np.stack([fraction[..., k] if bit else 1-fraction[..., k]
                                              for k, bit in enumerate((x, y, z))], axis=-1), axis=-1)
                    values += weight * array[index[..., 2], index[..., 1], index[..., 0]]
    return np.where(valid, values, np.nan)


class ScrewAssessmentService:
    def __init__(self, segmentation):
        self.segmentation = segmentation
        self._surfaces = {}
        self._meshes = {}

    def _boundary(self, label):
        if label in self._surfaces:
            return self._surfaces[label]
        image = self.segmentation.sitk_image
        mask = sitk.GetArrayViewFromImage(image) == label
        indices = np.argwhere(mask)
        if not len(indices):
            raise ValueError("Empty segmentation")
        # A cropped mask cannot establish a complete outer bone boundary.
        if np.any(indices.min(0) == 0) or np.any(indices.max(0) == np.array(mask.shape)-1):
            raise ValueError("Segmentation touches image edge")
        low = indices.min(0)-1
        high = indices.max(0)+2
        crop = np.ascontiguousarray(mask[tuple(slice(a, b) for a, b in zip(low, high))], dtype=np.uint8)
        data = vtk.vtkImageData()
        data.SetDimensions(*crop.shape[::-1])
        data.GetPointData().SetScalars(numpy_to_vtk(crop.ravel(), deep=True))
        contour = vtk.vtkFlyingEdges3D()
        contour.SetInputData(data)
        contour.SetValue(0, .5)
        contour.Update()
        matrix = vtk.vtkMatrix4x4()
        linear = np.asarray(image.GetDirection()).reshape(3, 3) @ np.diag(image.GetSpacing())
        origin = np.asarray(image.GetOrigin()) + linear @ low[::-1]
        for row in range(3):
            for col in range(3):
                matrix.SetElement(row, col, linear[row, col])
            matrix.SetElement(row, 3, origin[row])
        transform = vtk.vtkTransform()
        transform.SetMatrix(matrix)
        physical = vtk.vtkTransformPolyDataFilter()
        physical.SetTransform(transform)
        physical.SetInputConnection(contour.GetOutputPort())
        physical.Update()
        distance = vtk.vtkImplicitPolyDataDistance()
        distance.SetInput(physical.GetOutput())
        mesh = vtk.vtkPolyData()
        mesh.DeepCopy(physical.GetOutput())
        self._meshes[label] = mesh
        self._surfaces[label] = distance
        return distance

    @staticmethod
    def _screw_surface(plan, exclusion):
        actor = make_screw_actor(plan.diameter_mm, plan.length_mm,
                                 plan.entry_point, plan.direction)
        transform = vtk.vtkTransform()
        transform.SetMatrix(actor.GetMatrix())
        world = vtk.vtkTransformPolyDataFilter()
        world.SetTransform(transform)
        world.SetInputData(actor.GetMapper().GetInput())
        axis = np.asarray(plan.direction, dtype=float)
        axis /= np.linalg.norm(axis)
        plane = vtk.vtkPlane()
        plane.SetNormal(*axis)
        plane.SetOrigin(*(np.asarray(plan.entry_point)+axis*exclusion))
        clip = vtk.vtkClipPolyData()
        clip.SetInputConnection(world.GetOutputPort())
        clip.SetClipFunction(plane)
        clip.Update()
        mesh = vtk.vtkPolyData()
        mesh.DeepCopy(clip.GetOutput())
        return mesh

    def assess(self, plan, volume, *, entry_exclusion_mm=DEFAULT_ENTRY_EXCLUSION_MM):
        exclusion = float(entry_exclusion_mm)
        if not np.isfinite(exclusion) or exclusion < 0:
            raise ValueError("Entry exclusion must be a finite nonnegative distance")
        depth = np.linspace(0, plan.length_mm, max(2, int(np.ceil(plan.length_mm/.5))+1))
        missing = lambda reason: ScrewAssessment(None, "—", depth, np.full(depth.shape, np.nan),
                                                 np.zeros(depth.shape), reason, exclusion)
        label = next((key for key, name in self.segmentation.labels.items() if name == plan.level), None)
        if label is None:
            return missing("No segmentation")
        axis = np.asarray(plan.direction, dtype=float)
        if not np.all(np.isfinite(axis)) or np.linalg.norm(axis) == 0:
            return missing("Invalid trajectory")
        axis /= np.linalg.norm(axis)
        helper = np.eye(3)[np.argmin(np.abs(axis))]
        u = np.cross(axis, helper); u /= np.linalg.norm(u)
        v = np.cross(axis, u)
        theta = np.linspace(0, 2*np.pi, 72, endpoint=False)
        radial = np.cos(theta)[:, None]*u + np.sin(theta)[:, None]*v
        centers = np.asarray(plan.entry_point) + depth[:, None]*axis
        radius = plan.diameter_mm/2
        reason = ""
        breach = None
        grade = "—"
        breach_point = bone_point = breach_depth = None
        screw_mesh = None
        try:
            if exclusion >= plan.length_mm:
                raise ValueError("Entry band covers entire screw; no graded region")
            self._boundary(label)
            screw_mesh = self._screw_surface(plan, exclusion)
            if screw_mesh.GetNumberOfPoints() == 0:
                raise ValueError("No screw surface beyond entry exclusion")
            points = vtk_to_numpy(screw_mesh.GetPoints().GetData())
            # BART_Planning probes the mesh with the labelmap: positive coverage
            # is inside. Use a binary target mask to avoid mixing adjacent labels.
            mask = sitk.Cast(self.segmentation.sitk_image == label, sitk.sitkUInt8)
            coverage = sample_image(mask, points)
            if not np.all(np.isfinite(coverage)):
                raise ValueError("Screw outside image")
            inside = coverage > 0
            breach = 0.
            grade = "A"
            if not np.all(inside):
                scalars = numpy_to_vtk(inside.astype(np.uint8), deep=True)
                scalars.SetName("Coverage")
                screw_mesh.GetPointData().SetScalars(scalars)
                outside = vtk.vtkThreshold()
                outside.SetInputData(screw_mesh)
                outside.SetInputArrayToProcess(0, 0, 0, 0, "Coverage")
                outside.SetLowerThreshold(0)
                outside.SetUpperThreshold(0)
                outside.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
                outside.AllScalarsOn()
                outside.Update()
                vertices = outside.GetOutput().GetPoints()
                if vertices is not None and vertices.GetNumberOfPoints():
                    candidates = vtk_to_numpy(vertices.GetData())
                    # Unsigned nearest-cell distance, only after the coverage gate.
                    locator = vtk.vtkStaticCellLocator()
                    locator.SetDataSet(self._meshes[label])
                    locator.BuildLocator()
                    for point in candidates:
                        closest = [0., 0., 0.]
                        cell, sub, squared = vtk.mutable(0), vtk.mutable(0), vtk.mutable(0.)
                        locator.FindClosestPoint(point, closest, cell, sub, squared)
                        distance = float(np.sqrt(float(squared)))
                        if distance > breach:
                            breach = distance
                            breach_point = tuple(float(v) for v in point)
                            bone_point = tuple(closest)
                            breach_depth = float(np.dot(point-np.asarray(plan.entry_point), axis))
                    grade = gertzbein_robbins(breach) if np.any(inside) else "E"
                    if not np.any(inside):
                        reason = "No segmentation coverage"
                else:
                    # Unlike the reference's error fallback E, do not classify
                    # ambiguous mixed triangles as a demonstrated breach or A.
                    breach = None
                    grade = "—"
                    reason = "Boundary contact; no fully outside triangles"
        except (ValueError, FileNotFoundError) as error:
            breach = None
            grade = "—"
            reason = str(error)
        # Equal-area radial sampling of the 1 mm shell just outside the screw.
        radii = np.sqrt(radius**2 + (np.arange(3)+.5)/3*((radius+1)**2-radius**2))
        shell = centers[:, None, None, :] + radii[None, :, None, None]*radial[None, None, :, :]
        labels = sample_image(self.segmentation.sitk_image, shell, nearest=True)
        values = sample_image(volume.sitk_image, shell)
        valid = (labels == label) & np.isfinite(values)
        count = valid.sum(axis=(1, 2))
        hu = np.divide(np.where(valid, values, 0).sum(axis=(1, 2)), count,
                       out=np.full(depth.shape, np.nan), where=count > 0)
        return ScrewAssessment(breach, grade, depth, hu,
                               count/(3*len(theta)), reason, exclusion,
                               breach_point, bone_point, breach_depth,
                               tuple(self.segmentation.sitk_image.GetSpacing()),
                               self._meshes.get(label), screw_mesh)
