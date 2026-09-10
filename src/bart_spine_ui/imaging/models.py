from dataclasses import dataclass
from pathlib import Path

import SimpleITK as sitk
import vtk


@dataclass(slots=True)
class MedicalVolume:
    """
    Loaded medical volume shared by viewers and future workflows.

    Internal image convention:
        canonical LPS orientation whenever SimpleITK can provide it.
    """

    name: str
    sitk_image: sitk.Image
    vtk_image: vtk.vtkImageData
    is_demo: bool = False
    source_path: Path | None = None

    @property
    def size(self) -> tuple[int, int, int]:
        return tuple(int(v) for v in self.sitk_image.GetSize())

    @property
    def spacing(self) -> tuple[float, float, float]:
        return tuple(float(v) for v in self.sitk_image.GetSpacing())

    @property
    def origin(self) -> tuple[float, float, float]:
        return tuple(float(v) for v in self.sitk_image.GetOrigin())

    @property
    def scalar_range(self) -> tuple[float, float]:
        lo, hi = self.vtk_image.GetScalarRange()
        return float(lo), float(hi)
