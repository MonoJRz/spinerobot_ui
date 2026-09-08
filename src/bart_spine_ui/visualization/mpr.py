import vtk
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from ..imaging.presets import default_window_level


class MPRPanel(QFrame):
    """Orthogonal MPR panel with slice, window/level, and maximize controls."""

    maximize_requested = Signal(object)

    def __init__(self, title: str, orientation: SliceOrientation, parent=None):
        super().__init__(parent)
        self.setObjectName("ViewerFrame")

        self.title = title
        self.orientation = orientation
        self.image: vtk.vtkImageData | None = None
        self.extent = None
        self.spacing = None
        self.origin = None
        self._window = 1800.0
        self._level = 500.0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(9, 7, 9, 8)
        outer.setSpacing(5)

        header = QHBoxLayout()
        view_icon = QLabel("▧")
        view_icon.setObjectName("ViewerIcon")
        title_label = QLabel(title)
        title_label.setObjectName("ViewerTitle")
        self.position_label = QLabel("Waiting for volume")
        self.position_label.setObjectName("ViewerMeta")
        self.position_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.maximize_button = QPushButton("⛶")
        self.maximize_button.setObjectName("ViewerToolButton")
        self.maximize_button.setToolTip(f"Maximize {title} view")
        self.maximize_button.clicked.connect(lambda: self.maximize_requested.emit(self))
        header.addWidget(view_icon)
        header.addWidget(title_label)
        header.addStretch(1)
        header.addWidget(self.position_label)
        header.addWidget(self.maximize_button)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.vtk_widget.setMinimumSize(180, 170)
        body.addWidget(self.vtk_widget, 1)

        slider_frame = QFrame()
        slider_frame.setObjectName("SliceSliderFrame")
        slider_frame.setFixedWidth(46)
        slider_box = QVBoxLayout(slider_frame)
        slider_box.setContentsMargins(9, 10, 9, 10)

        self.slider = QSlider(Qt.Vertical)
        self.slider.setObjectName("SliceSlider")
        self.slider.setEnabled(False)
        self.slider.setInvertedAppearance(False)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_box.addWidget(self.slider, 1)
        body.addWidget(slider_frame)
        outer.addLayout(body, 1)

        footer = QHBoxLayout()
        self.window_level_label = QLabel("W: 1800    L: 500")
        self.window_level_label.setObjectName("ViewerMeta")
        footer.addWidget(self.window_level_label)
        footer.addStretch(1)
        outer.addLayout(footer)

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.035, 0.04, 0.045)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)

        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.interactor.SetInteractorStyle(vtk.vtkInteractorStyleImage())

        self.reslice = vtk.vtkImageReslice()
        self.reslice.SetOutputDimensionality(2)
        self.reslice.SetInterpolationModeToLinear()

        self.window_level = vtk.vtkImageMapToWindowLevelColors()
        self.window_level.SetInputConnection(self.reslice.GetOutputPort())
        self.window_level.SetOutputFormatToRGBA()

        self.actor = vtk.vtkImageActor()
        self.actor.GetMapper().SetInputConnection(self.window_level.GetOutputPort())
        self._actor_added = False

        self.renderer.GetActiveCamera().ParallelProjectionOn()
        self.interactor.Initialize()

    def set_volume(self, volume: MedicalVolume) -> None:
        image = volume.vtk_image
        self.image = image
        self.extent = image.GetExtent()
        self.spacing = image.GetSpacing()
        self.origin = image.GetOrigin()

        scalar_min, scalar_max = volume.scalar_range
        window, level = default_window_level(scalar_min, scalar_max)
        self.reslice.SetInputData(image)
        self.set_window_level(window, level)

        if not self._actor_added:
            self.renderer.AddActor(self.actor)
            self._actor_added = True

        minimum_index, maximum_index = self._slice_index_range()
        self.slider.blockSignals(True)
        self.slider.setRange(minimum_index, maximum_index)
        self.slider.setValue((minimum_index + maximum_index) // 2)
        self.slider.setEnabled(True)
        self.slider.blockSignals(False)

        self._update_reslice(self.slider.value())
        self.renderer.ResetCamera()
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        self.render()

    def set_window_level(self, window: float, level: float) -> None:
        self._window = float(window)
        self._level = float(level)
        self.window_level.SetWindow(self._window)
        self.window_level.SetLevel(self._level)
        self.window_level_label.setText(f"W: {self._window:.0f}    L: {self._level:.0f}")
        self.render()

    def set_linear_interpolation(self, enabled: bool) -> None:
        if enabled:
            self.reslice.SetInterpolationModeToLinear()
        else:
            self.reslice.SetInterpolationModeToNearestNeighbor()
        self.reslice.Update()
        self.render()

    def set_maximized_state(self, maximized: bool) -> None:
        self.maximize_button.setText("↙" if maximized else "⛶")
        action = "Restore all views" if maximized else f"Maximize {self.title} view"
        self.maximize_button.setToolTip(action)

    def render(self) -> None:
        self.vtk_widget.GetRenderWindow().Render()

    def _slice_index_range(self) -> tuple[int, int]:
        if self.orientation is SliceOrientation.AXIAL:
            return self.extent[4], self.extent[5]
        if self.orientation is SliceOrientation.CORONAL:
            return self.extent[2], self.extent[3]
        return self.extent[0], self.extent[1]

    def _on_slider_changed(self, value: int) -> None:
        if self.image is None:
            return
        self._update_reslice(value)
        self.render()

    def _update_position_label(self, index: int, axis: str) -> None:
        minimum, maximum = self._slice_index_range()
        self.position_label.setText(f"{axis}: {index - minimum + 1} / {maximum - minimum + 1}")

    def _update_reslice(self, index: int) -> None:
        xmin, xmax, ymin, ymax, zmin, zmax = self.extent
        sx, sy, sz = self.spacing
        ox, oy, oz = self.origin

        x_count = xmax - xmin + 1
        y_count = ymax - ymin + 1
        z_count = zmax - zmin + 1

        cx = ox + 0.5 * (xmin + xmax) * sx
        cy = oy + 0.5 * (ymin + ymax) * sy
        cz = oz + 0.5 * (zmin + zmax) * sz

        axes = vtk.vtkMatrix4x4()

        if self.orientation is SliceOrientation.AXIAL:
            position = oz + index * sz
            axes.DeepCopy((
                1, 0, 0, cx,
                0, 1, 0, cy,
                0, 0, 1, position,
                0, 0, 0, 1,
            ))
            self.reslice.SetOutputSpacing(sx, sy, 1.0)
            self.reslice.SetOutputOrigin(
                -0.5 * (x_count - 1) * sx,
                -0.5 * (y_count - 1) * sy,
                0.0,
            )
            self.reslice.SetOutputExtent(0, x_count - 1, 0, y_count - 1, 0, 0)
            self._update_position_label(index, "Z")

        elif self.orientation is SliceOrientation.CORONAL:
            position = oy + index * sy
            axes.DeepCopy((
                1, 0, 0, cx,
                0, 0, 1, position,
                0, 1, 0, cz,
                0, 0, 0, 1,
            ))
            self.reslice.SetOutputSpacing(sx, sz, 1.0)
            self.reslice.SetOutputOrigin(
                -0.5 * (x_count - 1) * sx,
                -0.5 * (z_count - 1) * sz,
                0.0,
            )
            self.reslice.SetOutputExtent(0, x_count - 1, 0, z_count - 1, 0, 0)
            self._update_position_label(index, "Y")

        else:
            position = ox + index * sx
            axes.DeepCopy((
                0, 0, 1, position,
                1, 0, 0, cy,
                0, 1, 0, cz,
                0, 0, 0, 1,
            ))
            self.reslice.SetOutputSpacing(sy, sz, 1.0)
            self.reslice.SetOutputOrigin(
                -0.5 * (y_count - 1) * sy,
                -0.5 * (z_count - 1) * sz,
                0.0,
            )
            self.reslice.SetOutputExtent(0, y_count - 1, 0, z_count - 1, 0, 0)
            self._update_position_label(index, "X")

        self.reslice.SetResliceAxes(axes)
        self.reslice.Update()
