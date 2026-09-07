import vtk
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from ..imaging.models import MedicalVolume
from ..imaging.presets import configure_volume_property


class Volume3DPanel(QWidget):
    """Interactive VTK 3D medical-volume view."""

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("3D — Volume Rendering")
        title.setStyleSheet("font-weight: 600;")
        hint = QLabel("Drag: rotate · Wheel: zoom")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hint.setStyleSheet("color: #777;")

        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(hint)
        outer.addLayout(header)

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setMinimumSize(320, 235)
        outer.addWidget(self.vtk_widget, 1)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.04, 0.05, 0.06)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        self.mapper = vtk.vtkSmartVolumeMapper()

        self.volume_property = vtk.vtkVolumeProperty()
        self.volume_property.ShadeOn()
        self.volume_property.SetInterpolationTypeToLinear()
        self.volume_property.SetAmbient(0.2)
        self.volume_property.SetDiffuse(0.8)
        self.volume_property.SetSpecular(0.2)

        self.volume_actor = vtk.vtkVolume()
        self.volume_actor.SetMapper(self.mapper)
        self.volume_actor.SetProperty(self.volume_property)
        self._volume_added = False

        self.interactor.Initialize()

    def set_volume(self, volume: MedicalVolume) -> None:
        self.mapper.SetInputData(volume.vtk_image)

        if not self._volume_added:
            self.renderer.AddVolume(self.volume_actor)
            self._volume_added = True

        scalar_min, scalar_max = volume.scalar_range
        configure_volume_property(
            self.volume_property,
            scalar_min,
            scalar_max,
        )

        self.reset_camera()

    def reset_camera(self) -> None:
        self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()
