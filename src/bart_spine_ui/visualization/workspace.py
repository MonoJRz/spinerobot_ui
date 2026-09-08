from PySide6.QtWidgets import QGridLayout, QWidget

from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from .mpr import MPRPanel
from .volume3d import Volume3DPanel


class ImagingWorkspace(QWidget):
    """Reusable 2×2 medical viewer workspace for Setup/Planning/Navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImagingWorkspace")

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self.axial = MPRPanel("Axial", SliceOrientation.AXIAL)
        self.coronal = MPRPanel("Coronal", SliceOrientation.CORONAL)
        self.sagittal = MPRPanel("Sagittal", SliceOrientation.SAGITTAL)
        self.three_d = Volume3DPanel()

        layout.addWidget(self.axial, 0, 0)
        layout.addWidget(self.three_d, 0, 1)
        layout.addWidget(self.coronal, 1, 0)
        layout.addWidget(self.sagittal, 1, 1)

        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    @property
    def mpr_views(self):
        return self.axial, self.coronal, self.sagittal

    def set_volume(self, volume: MedicalVolume) -> None:
        for view in self.mpr_views:
            view.set_volume(volume)
        self.three_d.set_volume(volume)

    def set_window_level(self, window: float, level: float) -> None:
        for view in self.mpr_views:
            view.set_window_level(window, level)

    def set_linear_interpolation(self, enabled: bool) -> None:
        for view in self.mpr_views:
            view.set_linear_interpolation(enabled)

    def reset_3d_camera(self) -> None:
        self.three_d.reset_camera()
