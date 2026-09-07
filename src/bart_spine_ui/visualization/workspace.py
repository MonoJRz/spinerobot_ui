from PySide6.QtWidgets import QGridLayout, QWidget

from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from .mpr import MPRPanel
from .volume3d import Volume3DPanel


class ImagingWorkspace(QWidget):
    """
    Reusable 2×2 medical viewer workspace.

    Future planning/navigation pages can reuse this widget and add overlays through dedicated
    visualization controllers rather than duplicating the base MPR implementation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.axial = MPRPanel("RED — Axial", SliceOrientation.AXIAL)
        self.coronal = MPRPanel("GREEN — Coronal", SliceOrientation.CORONAL)
        self.sagittal = MPRPanel("YELLOW — Sagittal", SliceOrientation.SAGITTAL)
        self.three_d = Volume3DPanel()

        # Preserve the proven prototype layout.
        layout.addWidget(self.axial, 0, 0)
        layout.addWidget(self.three_d, 0, 1)
        layout.addWidget(self.coronal, 1, 0)
        layout.addWidget(self.sagittal, 1, 1)

        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    @property
    def mpr_views(self) -> tuple[MPRPanel, MPRPanel, MPRPanel]:
        return self.axial, self.coronal, self.sagittal

    def set_volume(self, volume: MedicalVolume) -> None:
        for view in self.mpr_views:
            view.set_volume(volume)
        self.three_d.set_volume(volume)

    def reset_3d_camera(self) -> None:
        self.three_d.reset_camera()
