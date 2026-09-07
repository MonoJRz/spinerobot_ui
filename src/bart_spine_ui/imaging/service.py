from pathlib import Path

from .conversion import sitk_to_vtk
from .demo import create_demo_volume
from .io import read_dicom_directory, read_image_file
from .models import MedicalVolume


class ImagingService:
    """
    Application-facing medical image service.

    UI code calls this service instead of calling SimpleITK directly. This makes it possible to
    replace loading behavior, introduce caching, or move expensive operations to worker threads
    without changing the viewer widgets.
    """

    def load_file(self, path: str | Path) -> MedicalVolume:
        image, name = read_image_file(path)
        return self._make_volume(image, name)

    def load_dicom_directory(self, directory: str | Path) -> MedicalVolume:
        image, name = read_dicom_directory(directory)
        return self._make_volume(image, name)

    def create_demo(self) -> MedicalVolume:
        image, name = create_demo_volume()
        return self._make_volume(image, name)

    @staticmethod
    def _make_volume(image, name: str) -> MedicalVolume:
        return MedicalVolume(
            name=name,
            sitk_image=image,
            vtk_image=sitk_to_vtk(image),
        )
