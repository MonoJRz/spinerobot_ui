from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .status_indicator import StatusIndicator


class SetupLeftSidebar(QFrame):
    import_dicom_requested = Signal()
    load_volume_requested = Signal()
    window_level_changed = Signal(float, float)
    interpolation_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftSidebar")
        self.setFixedWidth(320)

        self._window = 1800
        self._level = 500

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(10)

        self.import_button = QPushButton("IMPORT DICOM")
        self.import_button.setObjectName("PrimaryAction")
        self.load_button = QPushButton("LOAD VOLUME")
        self.load_button.setObjectName("PrimaryAction")
        layout.addWidget(self.import_button)
        layout.addWidget(self.load_button)
        layout.addSpacing(2)

        layout.addWidget(self._section("CT DISPLAY"))

        preset_row = QHBoxLayout()
        preset_label = QLabel("Preset")
        preset_label.setObjectName("SidebarText")
        self.preset = QComboBox()
        self.preset.addItems(["Spine Bone", "Soft Tissue", "Wide CT", "Custom"])
        self.preset.setCurrentText("Spine Bone")
        preset_row.addWidget(preset_label)
        preset_row.addWidget(self.preset, 1)
        layout.addLayout(preset_row)

        self.window_value = QLabel("1800")
        self.window_value.setAlignment(Qt.AlignCenter)
        self.window_value.setObjectName("SidebarText")
        layout.addWidget(self.window_value)
        self.window_slider = QSlider(Qt.Horizontal)
        self.window_slider.setRange(200, 4000)
        self.window_slider.setValue(1800)
        layout.addWidget(self.window_slider)
        window_name = QLabel("Window")
        window_name.setAlignment(Qt.AlignRight)
        window_name.setObjectName("SidebarText")
        layout.addWidget(window_name)

        self.level_value = QLabel("500")
        self.level_value.setAlignment(Qt.AlignCenter)
        self.level_value.setObjectName("SidebarText")
        layout.addWidget(self.level_value)
        self.level_slider = QSlider(Qt.Horizontal)
        self.level_slider.setRange(-1000, 2000)
        self.level_slider.setValue(500)
        layout.addWidget(self.level_slider)
        level_name = QLabel("Level")
        level_name.setAlignment(Qt.AlignRight)
        level_name.setObjectName("SidebarText")
        layout.addWidget(level_name)

        layout.addSpacing(10)
        interpolation = QLabel("Interpolation")
        interpolation.setObjectName("SectionTitle")
        layout.addWidget(interpolation)
        self.linear = QRadioButton("Linear")
        self.nearest = QRadioButton("Nearest")
        self.linear.setChecked(True)
        layout.addWidget(self.linear)
        layout.addWidget(self.nearest)

        layout.addStretch(1)

        layout.addWidget(self._section("Manipulator"))
        self.robot_arm_status = StatusIndicator("Robot arm")
        self.end_effector_status = StatusIndicator("End-effector")
        layout.addWidget(self.robot_arm_status)
        layout.addWidget(self.end_effector_status)
        layout.addWidget(self._section("Tracking"))
        self.tool_status = StatusIndicator("Tool marker")
        self.robot_marker_status = StatusIndicator("Robot marker")
        self.patient_marker_status = StatusIndicator("Patient marker")
        layout.addWidget(self.tool_status)
        layout.addWidget(self.robot_marker_status)
        layout.addWidget(self.patient_marker_status)
        layout.addSpacing(6)

        self.import_button.clicked.connect(self.import_dicom_requested)
        self.load_button.clicked.connect(self.load_volume_requested)
        self.window_slider.valueChanged.connect(self._emit_window_level)
        self.level_slider.valueChanged.connect(self._emit_window_level)
        self.preset.currentTextChanged.connect(self._apply_preset)
        self.linear.toggled.connect(self.interpolation_changed)

    def _section(self, title: str) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        line = QFrame()
        line.setObjectName("SectionLine")
        box.addWidget(label)
        box.addWidget(line)
        return widget

    def _emit_window_level(self) -> None:
        self._window = self.window_slider.value()
        self._level = self.level_slider.value()
        self.window_value.setText(str(self._window))
        self.level_value.setText(str(self._level))
        self.window_level_changed.emit(float(self._window), float(self._level))

    def _apply_preset(self, name: str) -> None:
        presets = {
            "Spine Bone": (1800, 500),
            "Soft Tissue": (400, 40),
            "Wide CT": (3000, 300),
        }
        if name not in presets:
            return
        window, level = presets[name]
        self.window_slider.blockSignals(True)
        self.level_slider.blockSignals(True)
        self.window_slider.setValue(window)
        self.level_slider.setValue(level)
        self.window_slider.blockSignals(False)
        self.level_slider.blockSignals(False)
        self._emit_window_level()

    def set_robot_arm_connected(self, connected: bool | None) -> None:
        self.robot_arm_status.set_connected(connected)

    def set_end_effector_connected(self, connected: bool | None) -> None:
        self.end_effector_status.set_connected(connected, unavailable="Not detected")

    def set_tool_marker_tracked(self, tracked: bool | None) -> None:
        self.tool_status.set_connected(tracked, unavailable="Not tracked")

    def set_robot_marker_tracked(self, tracked: bool | None) -> None:
        self.robot_marker_status.set_connected(tracked, unavailable="Not tracked")

    def set_patient_marker_tracked(self, tracked: bool | None) -> None:
        self.patient_marker_status.set_connected(tracked, unavailable="Not tracked")
