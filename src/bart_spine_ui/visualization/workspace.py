from PySide6.QtWidgets import QGridLayout, QWidget

from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from .mpr import MPRPanel
from .volume3d import Volume3DPanel


class ImagingWorkspace(QWidget):
    """Reusable 2×2 viewer workspace with per-panel maximize support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImagingWorkspace")
        self._maximized_panel = None

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(7, 10, 7, 10)
        self._layout.setSpacing(9)

        self.axial = MPRPanel("Axial", SliceOrientation.AXIAL)
        self.coronal = MPRPanel("Coronal", SliceOrientation.CORONAL)
        self.sagittal = MPRPanel("Sagittal", SliceOrientation.SAGITTAL)
        self.three_d = Volume3DPanel()
        self.panels = (self.axial, self.three_d, self.coronal, self.sagittal)
        self._positions = {
            self.axial: (0, 0),
            self.three_d: (0, 1),
            self.coronal: (1, 0),
            self.sagittal: (1, 1),
        }

        self._restore_grid(show_panels=False)
        self._layout.setRowStretch(0, 1)
        self._layout.setRowStretch(1, 1)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

        for panel in self.panels:
            panel.maximize_requested.connect(self.toggle_maximize)

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

    def toggle_maximize(self, panel) -> None:
        if self._maximized_panel is panel:
            self._maximized_panel = None
            self._restore_grid()
            return

        for candidate in self.panels:
            self._layout.removeWidget(candidate)
            candidate.hide()
            candidate.set_maximized_state(False)

        self._layout.addWidget(panel, 0, 0, 2, 2)
        panel.show()
        panel.set_maximized_state(True)
        self._maximized_panel = panel

    def _restore_grid(self, *, show_panels: bool = True) -> None:
        for panel, (row, column) in self._positions.items():
            self._layout.removeWidget(panel)
            self._layout.addWidget(panel, row, column)
            if show_panels:
                panel.show()
            panel.set_maximized_state(False)
