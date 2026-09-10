from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ArrowButton(QPushButton):
    """Clean vector arrow button that does not depend on Unicode glyphs."""

    def __init__(self, direction: str, parent=None):
        super().__init__(parent)

        if direction not in {"left", "right", "up", "down"}:
            raise ValueError(f"Unsupported arrow direction: {direction}")

        self.direction = direction

        self.setObjectName("TrajectoryArrowButton")
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        # Let Qt draw background/border using the stylesheet.
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self.isEnabled():
            color = QColor(125, 155, 168, 130)
        elif self.isDown() or self.underMouse():
            color = QColor(255, 255, 255)
        else:
            color = QColor(226, 247, 255)

        pen = QPen(color)
        pen.setWidthF(2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        size = 7.0

        if self.direction == "left":
            points = [
                QPointF(cx + size / 2, cy - size),
                QPointF(cx - size / 2, cy),
                QPointF(cx + size / 2, cy + size),
            ]

        elif self.direction == "right":
            points = [
                QPointF(cx - size / 2, cy - size),
                QPointF(cx + size / 2, cy),
                QPointF(cx - size / 2, cy + size),
            ]

        elif self.direction == "up":
            points = [
                QPointF(cx - size, cy + size / 2),
                QPointF(cx, cy - size / 2),
                QPointF(cx + size, cy + size / 2),
            ]

        else:  # down
            points = [
                QPointF(cx - size, cy - size / 2),
                QPointF(cx, cy + size / 2),
                QPointF(cx + size, cy - size / 2),
            ]

        painter.drawPolyline(points)


class TrajectoryTouchOverlay(QFrame):
    """Transparent on-image trajectory angle controller."""

    delta_requested = Signal(float)

    def __init__(
        self,
        title: str,
        negative_direction: str,
        positive_direction: str,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("TrajectoryTouchOverlay")
        self.setFixedSize(206, 64)

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

        self.setStyleSheet(
            """
            QFrame#TrajectoryTouchOverlay {
                background: transparent;
                border: none;
            }

            QLabel#TouchTitle {
                background: transparent;
                border: none;

                color: rgba(180, 230, 246, 235);

                font-size: 8px;
                font-weight: 700;
                letter-spacing: 0.6px;
            }

            QLabel#TouchValue {
                background: transparent;
                border: none;

                color: rgba(245, 252, 255, 250);

                font-size: 17px;
                font-weight: 800;
            }

            QPushButton#TrajectoryArrowButton {
                background: transparent;

                border: 1px solid rgba(80, 207, 248, 190);
                border-radius: 14px;
            }

            QPushButton#TrajectoryArrowButton:hover {
                background-color: rgba(20, 101, 130, 125);
                border-color: rgba(110, 225, 255, 235);
            }

            QPushButton#TrajectoryArrowButton:pressed {
                background-color: rgba(31, 135, 169, 165);
                border-color: #91E8FF;
            }

            QPushButton#TrajectoryArrowButton:disabled {
                background: transparent;
                border-color: rgba(65, 110, 125, 100);
            }
            """
        )

        # --------------------------------------------------------------
        # Layout
        # --------------------------------------------------------------
        row = QHBoxLayout(self)
        row.setContentsMargins(9, 8, 9, 8)
        row.setSpacing(10)

        self.negative_button = ArrowButton(
            negative_direction,
            self,
        )

        self.positive_button = ArrowButton(
            positive_direction,
            self,
        )

        center = QVBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(1)
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("TouchTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.value = QLabel("0.0°")
        self.value.setObjectName("TouchValue")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center.addWidget(self.title_label)
        center.addWidget(self.value)

        row.addWidget(
            self.negative_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        row.addLayout(center, 1)

        row.addWidget(
            self.positive_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        self.negative_button.clicked.connect(
            lambda: self.delta_requested.emit(-1.0)
        )

        self.positive_button.clicked.connect(
            lambda: self.delta_requested.emit(1.0)
        )

        self.setEnabled(False)
        self.hide()

    def paintEvent(self, event) -> None:
        # Explicit painting also works when this hidden template has no backing window.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(5, 22, 31, 107))
        painter.setPen(QPen(QColor(72, 205, 248, 190), 1.0))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 18, 18)

    def set_angle(self, angle_deg: float | None) -> None:
        has_plan = angle_deg is not None

        self.setEnabled(has_plan)
        # Kept hidden: this widget supplies pixels to the VTK overlay.

        if angle_deg is not None:
            self.value.setText(f"{angle_deg:+.1f}°")