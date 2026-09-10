from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class ScrewAdjustmentOverlay(QFrame):
    """Large embedded controls for screw size and trajectory."""

    diameter_changed = Signal(float)
    length_changed = Signal(float)
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScrewAdjustmentOverlay")
        self.setMinimumHeight(164)
        self.setStyleSheet(
            """
            QFrame#ScrewAdjustmentOverlay {
                background: #101920;
                border: 1px solid #29485a;
                border-radius: 9px;
            }
            QFrame#ScrewAdjustmentOverlay QLabel { color: #b8cad5; font-size: 12px; }
            QFrame#ScrewAdjustmentOverlay QLabel#OverlayTitle {
                color: #eaf7ff; font-size: 14px; font-weight: 700;
            }
            QFrame#ScrewAdjustmentOverlay QLabel#ControlLabel {
                color: #78cfff; font-size: 11px; font-weight: 700;
            }
            QFrame#ScrewControl {
                background: #0a1218; border: 1px solid #203b4a; border-radius: 7px;
            }
            QFrame#ScrewControl QDoubleSpinBox, QFrame#ScrewControl QSpinBox {
                min-height: 38px; background: #071016; color: #ffffff;
                border: 1px solid #315a70; border-radius: 5px;
                font-size: 16px; font-weight: 700; padding: 0 7px;
            }
            QFrame#ScrewControl QPushButton {
                min-width: 36px; min-height: 38px; background: #123d52;
                color: #83d8ff; border: 1px solid #2b7899; border-radius: 5px;
                font-size: 21px; font-weight: 700;
            }
            QFrame#ScrewControl QPushButton:hover { background: #19526c; color: #ffffff; }
            QFrame#ScrewAdjustmentOverlay QPushButton#AutoButton {
                min-height: 34px; padding: 0 14px; background: #162c38; color: #9fdcff;
                border: 1px solid #315a70; border-radius: 6px; font-weight: 700;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 11, 14, 12)
        root.setSpacing(9)
        header = QHBoxLayout()
        self.title = QLabel("SCREW ADJUSTMENT")
        self.title.setObjectName("OverlayTitle")
        self.estimate = QLabel("Mark an entry point to create a screw")
        self.estimate.setWordWrap(True)
        self.reset_button = QPushButton("RESTORE AUTO SIZE")
        self.reset_button.setObjectName("AutoButton")
        self.reset_button.setToolTip("Restore the automatically estimated diameter and length")
        header.addWidget(self.title)
        header.addWidget(self.estimate, 1)
        header.addWidget(self.reset_button)
        root.addLayout(header)

        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(9)

        self.diameter_spin = QDoubleSpinBox()
        self.diameter_spin.setDecimals(1)
        self.diameter_spin.setRange(3.0, 10.0)
        self.diameter_spin.setSingleStep(0.5)
        self.diameter_spin.setSuffix(" mm")
        controls.addWidget(self._control("DIAMETER", self.diameter_spin), 0, 0)

        self.length_spin = QSpinBox()
        self.length_spin.setRange(20, 100)
        self.length_spin.setSingleStep(5)
        self.length_spin.setSuffix(" mm")
        controls.addWidget(self._control("LENGTH", self.length_spin), 0, 1)

        for column in range(2):
            controls.setColumnStretch(column, 1)
        root.addLayout(controls)

        self._syncing = False
        self._auto_diameter = 0.0
        self._auto_length = 0.0
        self.setEnabled(False)

        self.diameter_spin.valueChanged.connect(self._diameter_changed)
        self.length_spin.valueChanged.connect(self._length_changed)
        self.reset_button.clicked.connect(self.reset_requested)

    @staticmethod
    def _control(label_text: str, spin: QDoubleSpinBox | QSpinBox) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ScrewControl")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("ControlLabel")
        layout.addWidget(label)
        row = QHBoxLayout()
        row.setSpacing(5)
        minus = QPushButton("−")
        plus = QPushButton("+")
        minus.clicked.connect(spin.stepDown)
        plus.clicked.connect(spin.stepUp)
        row.addWidget(minus)
        row.addWidget(spin, 1)
        row.addWidget(plus)
        layout.addLayout(row)
        return frame

    def set_plan(
        self,
        *,
        level: str,
        side: str,
        diameter_mm: float,
        length_mm: float,
        anatomical_length_mm: float,
        pedicle_width_mm: float,
        remember_auto: bool = True,
    ) -> None:
        self.setEnabled(True)
        self.title.setText(f"SCREW: {level} {side.upper()}")
        self.estimate.setText(
            f"Auto width {pedicle_width_mm:.1f} mm  ·  depth {anatomical_length_mm:.1f} mm"
        )
        if remember_auto:
            self._auto_diameter = float(diameter_mm)
            self._auto_length = float(length_mm)
        self._syncing = True
        try:
            self.diameter_spin.setValue(float(diameter_mm))
            self.length_spin.setValue(round(float(length_mm) / 5.0) * 5)
        finally:
            self._syncing = False

    def clear_plan(self) -> None:
        self.title.setText("SCREW ADJUSTMENT")
        self.estimate.setText("Mark an entry point to create a screw")
        self.setEnabled(False)

    def auto_values(self) -> tuple[float, float]:
        return self._auto_diameter, self._auto_length

    def _diameter_changed(self, value: float) -> None:
        if not self._syncing:
            self.diameter_changed.emit(float(value))

    def _length_changed(self, value: int) -> None:
        if not self._syncing:
            self.length_changed.emit(float(value))
