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
)

from .status_indicator import StatusIndicator, StatusState


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

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 7, 10)
        root.setSpacing(10)

        image_card, image_layout = self._card("▣   IMAGE DATA")
        self.import_button = QPushButton("▰    IMPORT DICOM")
        self.import_button.setObjectName("PrimaryAction")
        self.load_button = QPushButton("●    LOAD VOLUME")
        self.load_button.setObjectName("SecondaryAction")
        image_layout.addWidget(self.import_button)
        image_layout.addWidget(self.load_button)
        root.addWidget(image_card)

        display_card, display = self._card("▤   CT DISPLAY")
        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        preset_label = QLabel("Preset")
        preset_label.setObjectName("SidebarText")
        self.preset = QComboBox()
        self.preset.addItems(["Spine Bone", "Soft Tissue", "Wide CT", "Custom"])
        self.preset.setCurrentText("Spine Bone")
        preset_row.addWidget(preset_label)
        preset_row.addWidget(self.preset, 1)
        display.addLayout(preset_row)

        self.window_value = QLabel("1800")
        display.addLayout(self._value_row("Window (HU)", self.window_value))
        self.window_slider = QSlider(Qt.Horizontal)
        self.window_slider.setRange(200, 4000)
        self.window_slider.setValue(1800)
        display.addWidget(self.window_slider)
        display.addLayout(self._range_row("200", "4000"))

        self.level_value = QLabel("500")
        display.addLayout(self._value_row("Level (HU)", self.level_value))
        self.level_slider = QSlider(Qt.Horizontal)
        self.level_slider.setRange(-1000, 2000)
        self.level_slider.setValue(500)
        display.addWidget(self.level_slider)
        display.addLayout(self._range_row("-1000", "2000"))

        interpolation = QLabel("Interpolation")
        interpolation.setObjectName("SidebarText")
        display.addWidget(interpolation)
        interpolation_row = QHBoxLayout()
        self.linear = QRadioButton("Linear")
        self.nearest = QRadioButton("Nearest")
        self.linear.setChecked(True)
        interpolation_row.addWidget(self.linear)
        interpolation_row.addStretch(1)
        interpolation_row.addWidget(self.nearest)
        display.addLayout(interpolation_row)
        root.addWidget(display_card)

        status_card, status = self._card("⌁   TRACKING & ROBOT")
        manipulator = QLabel("Manipulator")
        manipulator.setObjectName("StatusGroup")
        status.addWidget(manipulator)
        self.robot_arm_status = self._compact_status("Robot arm")
        self.end_effector_status = self._compact_status("End-effector")
        status.addWidget(self.robot_arm_status)
        status.addWidget(self.end_effector_status)

        divider = QFrame()
        divider.setObjectName("CardDivider")
        status.addWidget(divider)

        tracking = QLabel("Tracking")
        tracking.setObjectName("StatusGroup")
        status.addWidget(tracking)
        self.tool_status = self._compact_status("Tool marker")
        self.robot_marker_status = self._compact_status("Robot marker")
        self.patient_marker_status = self._compact_status("Patient marker")
        status.addWidget(self.tool_status)
        status.addWidget(self.robot_marker_status)
        status.addWidget(self.patient_marker_status)
        root.addWidget(status_card)
        root.addStretch(1)

        self.import_button.clicked.connect(self.import_dicom_requested)
        self.load_button.clicked.connect(self.load_volume_requested)
        self.window_slider.valueChanged.connect(self._emit_window_level)
        self.level_slider.valueChanged.connect(self._emit_window_level)
        self.preset.currentTextChanged.connect(self._apply_preset)
        self.linear.toggled.connect(self.interpolation_changed)

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SidebarCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(7)
        header = QLabel(title)
        header.setObjectName("CardTitle")
        layout.addWidget(header)
        divider = QFrame()
        divider.setObjectName("CardDivider")
        layout.addWidget(divider)
        return card, layout

    @staticmethod
    def _value_row(name: str, value: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(name)
        label.setObjectName("SidebarText")
        value.setObjectName("SidebarValue")
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value)
        return row

    @staticmethod
    def _range_row(minimum: str, maximum: str) -> QHBoxLayout:
        row = QHBoxLayout()
        low = QLabel(minimum)
        high = QLabel(maximum)
        low.setObjectName("RangeText")
        high.setObjectName("RangeText")
        row.addWidget(low)
        row.addStretch(1)
        row.addWidget(high)
        return row

    @staticmethod
    def _compact_status(name: str) -> StatusIndicator:
        indicator = StatusIndicator(name)
        indicator.set_status(StatusState.WAITING)
        return indicator

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
