from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..imaging import ImagingService, MedicalVolume


class ImagingController(QObject):
    """Controller boundary between Qt pages and medical-image services."""

    volume_loaded = Signal(object)
    error_occurred = Signal(str)
    status_changed = Signal(str)

    def __init__(self, *, service: ImagingService | None = None, parent=None):
        super().__init__(parent)
        self.service = service or ImagingService()
        self.current_volume: MedicalVolume | None = None

    def load_file(self, path: str | Path) -> None:
        self._run_load(lambda: self.service.load_file(path))

    def load_dicom_directory(self, directory: str | Path) -> None:
        self._run_load(lambda: self.service.load_dicom_directory(directory))

    def load_demo(self) -> None:
        self._run_load(self.service.create_demo)

    def _run_load(self, loader) -> None:
        try:
            volume = loader()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return

        self.current_volume = volume
        self.volume_loaded.emit(volume)

        sx, sy, sz = volume.spacing
        nx, ny, nz = volume.size
        self.status_changed.emit(
            f"Loaded {volume.name} — size {nx}×{ny}×{nz}, "
            f"spacing {sx:.2f}×{sy:.2f}×{sz:.2f} mm"
        )
