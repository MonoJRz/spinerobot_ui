import vtk
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from ..imaging.models import MedicalVolume
from ..imaging.presets import configure_volume_property
from ..segmentation import SegmentationVolume
from .segmentation_colors import VERTEBRA_LABEL_COUNT, create_segmentation_lookup_table


class Volume3DPanel(QFrame):
    """Interactive 3D view switchable between CT bone and segmentation surfaces."""

    maximize_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ViewerFrame")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(9, 7, 9, 8)
        outer.setSpacing(5)

        header = QHBoxLayout()
        icon = QLabel("◇")
        icon.setObjectName("ViewerIcon")
        title = QLabel("3D View")
        title.setObjectName("ViewerTitle")
        self.model_toggle = QPushButton("Bone")
        self.model_toggle.setObjectName("ViewModeButton")
        self.model_toggle.setCheckable(True)
        self.model_toggle.setEnabled(False)
        self.model_toggle.setToolTip("Run segmentation to enable the segmentation model")
        self.model_toggle.toggled.connect(self._set_segmentation_visible)
        self.maximize_button = QPushButton("⛶")
        self.maximize_button.setObjectName("ViewerToolButton")
        self.maximize_button.setToolTip("Maximize 3D view")
        self.maximize_button.clicked.connect(lambda: self.maximize_requested.emit(self))
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.model_toggle)
        header.addWidget(self.maximize_button)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setMinimumSize(180, 170)
        body.addWidget(self.vtk_widget, 1)

        tools = QVBoxLayout()
        tools.setSpacing(6)
        for text, tooltip, callback in (
            ("+", "Zoom in", lambda: self.zoom(1.2)),
            ("−", "Zoom out", lambda: self.zoom(0.8)),
            ("↻", "Reset camera", self.reset_camera),
        ):
            button = QPushButton(text)
            button.setObjectName("ViewerToolButton")
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            tools.addWidget(button)
        tools.addStretch(1)
        body.addLayout(tools)
        outer.addLayout(body, 1)

        hint = QLabel("Drag to rotate   •   Wheel to zoom")
        hint.setObjectName("ViewerMeta")
        outer.addWidget(hint)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.035, 0.04, 0.045)
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

        self.segmentation_contour = vtk.vtkDiscreteMarchingCubes()
        self.segmentation_contour.GenerateValues(VERTEBRA_LABEL_COUNT, 1, VERTEBRA_LABEL_COUNT)
        self.segmentation_mapper = vtk.vtkPolyDataMapper()
        self.segmentation_mapper.SetInputConnection(self.segmentation_contour.GetOutputPort())
        self.segmentation_mapper.SetLookupTable(create_segmentation_lookup_table(opacity=1.0))
        self.segmentation_mapper.SetScalarRange(1, VERTEBRA_LABEL_COUNT)
        self.segmentation_mapper.ScalarVisibilityOn()
        self.segmentation_actor = vtk.vtkActor()
        self.segmentation_actor.SetMapper(self.segmentation_mapper)
        self.segmentation_actor.GetProperty().SetAmbient(0.25)
        self.segmentation_actor.GetProperty().SetDiffuse(0.75)
        self.segmentation_actor.GetProperty().SetSpecular(0.15)
        self.segmentation_actor.GetProperty().SetOpacity(1.0)
        self.segmentation_actor.SetVisibility(False)
        self.renderer.AddActor(self.segmentation_actor)

        self.interactor.Initialize()

    def set_volume(self, volume: MedicalVolume) -> None:
        self.mapper.SetInputData(volume.vtk_image)
        if not self._volume_added:
            self.renderer.AddVolume(self.volume_actor)
            self._volume_added = True

        scalar_min, scalar_max = volume.scalar_range
        configure_volume_property(self.volume_property, scalar_min, scalar_max)
        self.reset_camera()

    def set_segmentation(self, segmentation: SegmentationVolume) -> None:
        self.segmentation_contour.SetInputData(segmentation.vtk_image)
        self.segmentation_contour.Update()
        self.model_toggle.setEnabled(True)
        self.model_toggle.setChecked(True)
        self._set_segmentation_visible(True)
        self.reset_camera()

    def clear_segmentation(self) -> None:
        self.segmentation_contour.RemoveAllInputs()
        self.model_toggle.blockSignals(True)
        self.model_toggle.setChecked(False)
        self.model_toggle.blockSignals(False)
        self.model_toggle.setText("Bone")
        self.model_toggle.setEnabled(False)
        self.model_toggle.setToolTip("Run segmentation to enable the segmentation model")
        self.segmentation_actor.SetVisibility(False)
        self.volume_actor.SetVisibility(True)

    def set_maximized_state(self, maximized: bool) -> None:
        self.maximize_button.setText("↙" if maximized else "⛶")
        self.maximize_button.setToolTip("Restore all views" if maximized else "Maximize 3D view")

    def zoom(self, factor: float) -> None:
        self.renderer.GetActiveCamera().Zoom(factor)
        self.vtk_widget.GetRenderWindow().Render()

    def reset_camera(self) -> None:
        self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()

    def _set_segmentation_visible(self, visible: bool) -> None:
        if visible and not self.model_toggle.isEnabled():
            return
        self.segmentation_actor.SetVisibility(visible)
        self.volume_actor.SetVisibility(not visible)
        self.model_toggle.setText("Segmentation" if visible else "Bone")
        self.model_toggle.setToolTip("Show CT bone model" if visible else "Show segmentation model")
        self.vtk_widget.GetRenderWindow().Render()
