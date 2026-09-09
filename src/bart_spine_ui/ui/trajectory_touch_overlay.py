from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class TrajectoryTouchOverlay(QFrame):
    """Large on-image angle control designed for mouse or touch input."""

    delta_requested = Signal(float)

    def __init__(self, title: str, negative_icon: str, positive_icon: str, parent=None):
        super().__init__(parent)
        self.setObjectName("TrajectoryTouchOverlay")
        self.setFixedSize(210, 76)
        self.setStyleSheet(
            """
            QFrame#TrajectoryTouchOverlay {
                background: rgba(5, 18, 25, 215); border: 2px solid #35bff4;
                border-radius: 14px;
            }
            QFrame#TrajectoryTouchOverlay QLabel { color: #eaf9ff; font-weight: 700; }
            QFrame#TrajectoryTouchOverlay QLabel#TouchTitle {
                color: #80dcff; font-size: 10px;
            }
            QFrame#TrajectoryTouchOverlay QLabel#TouchValue { font-size: 15px; }
            QFrame#TrajectoryTouchOverlay QPushButton {
                min-width: 50px; min-height: 48px; background: #123f54; color: #ffffff;
                border: 1px solid #4fd1ff; border-radius: 10px;
                font-size: 25px; font-weight: 700;
            }
            QFrame#TrajectoryTouchOverlay QPushButton:hover,
            QFrame#TrajectoryTouchOverlay QPushButton:pressed { background: #19779b; }
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 7, 8, 7)
        row.setSpacing(7)
        negative = QPushButton(negative_icon)
        positive = QPushButton(positive_icon)
        center = QVBoxLayout()
        center.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("TouchTitle")
        self.value = QLabel("0.0°")
        self.value.setObjectName("TouchValue")
        center.addWidget(label)
        center.addWidget(self.value)
        row.addWidget(negative)
        row.addLayout(center, 1)
        row.addWidget(positive)
        negative.clicked.connect(lambda: self.delta_requested.emit(-1.0))
        positive.clicked.connect(lambda: self.delta_requested.emit(1.0))
        self.setEnabled(False)
        self.hide()

    def set_angle(self, angle_deg: float | None) -> None:
        has_plan = angle_deg is not None
        self.setEnabled(has_plan)
        self.setVisible(has_plan)
        if angle_deg is not None:
            self.value.setText(f"{angle_deg:+.1f}°")
