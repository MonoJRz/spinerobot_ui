from dataclasses import dataclass
from pathlib import Path

import SimpleITK as sitk
import vtk


@dataclass(slots=True)
class SegmentationVolume:
    """Label map aligned to a reference CT and ready for VTK visualization."""

    sitk_image: sitk.Image
    vtk_image: vtk.vtkImageData
    labels: dict[int, str]
    source_directory: Path
