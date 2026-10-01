"""Touch-friendly construct assessment with a shared HU scale and entry band."""
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..planning.assessment import DEFAULT_ENTRY_EXCLUSION_MM, ScrewAssessmentService

GRADE_COLORS = {"A": "#7ee787", "B": "#d7df74", "C": "#f1c96b",
                "D": "#ff9a62", "E": "#ff737e", "—": "#8ea9ba"}
HU_MIN, HU_MAX = 0., 1000.


class AssessmentWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, segmentation, volume, plans, parent=None,
                 *, entry_exclusion_mm=DEFAULT_ENTRY_EXCLUSION_MM):
        super().__init__(parent)
        self.segmentation, self.volume, self.plans = segmentation, volume, plans
        self.entry_exclusion_mm = entry_exclusion_mm

    def run(self):
        try:
            service = ScrewAssessmentService(self.segmentation)
            results = {}
            for key, plan in self.plans.items():
                if self.isInterruptionRequested():
                    return
                results[key] = service.assess(
                    plan, self.volume, entry_exclusion_mm=self.entry_exclusion_mm)
            self.completed.emit(results)
        except (ValueError, RuntimeError, TypeError) as error:
            self.failed.emit(str(error))


def hu_color(value):
    if not np.isfinite(value):
        return QColor("#35434d")
    fraction = float(np.clip((value-HU_MIN)/(HU_MAX-HU_MIN), 0, 1))
    return QColor.fromRgbF(.14 + .72*fraction, .30 + .58*fraction, .48 + .46*fraction)


class HULegend(QWidget):
    """The same transfer function as the data strips, with explicit HU ticks."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(78)
        self.setAccessibleName("HU scale: 0, 250, 500, 750, 1000. Gray: no sample.")

    def paintEvent(self, event):
        painter = QPainter(self)
        width = max(1, self.width()-1)
        for x in range(self.width()):
            painter.fillRect(x, 2, 1, 20, hu_color(HU_MIN+x/width*(HU_MAX-HU_MIN)))
        painter.setPen(QColor("#dce9f0"))
        for tick in (0, 250, 500, 750, 1000):
            x = int(tick/HU_MAX*width)
            painter.drawLine(x, 22, x, 27)
            label = f"{tick}"
            label_width = painter.fontMetrics().horizontalAdvance(label)
            left = max(0, min(self.width()-label_width, x-label_width//2))
            painter.drawText(left, 43, label)
        painter.fillRect(0, 57, 14, 14, hu_color(np.nan))
        painter.drawText(21, 69, "No sample")
        painter.drawText(self.width()-28, 69, "HU")


class EntryBand(QWidget):
    """Separate grading band so excluded HU remains visible and unmodified."""
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.setFixedHeight(30)
        self.setAccessibleName(f"First {result.entry_exclusion_mm:g} mm excluded from G–R")

    def paintEvent(self, event):
        painter = QPainter(self)
        length = max(float(self.result.depth_mm[-1]), .001)
        width = int(self.width()*min(self.result.entry_exclusion_mm/length, 1))
        painter.fillRect(0, 1, self.width(), 6, QColor("#497888"))
        painter.fillRect(0, 1, width, 6, QColor("#f1c96b"))
        painter.setPen(QColor("#a9c0ce"))
        painter.drawText(0, 25, "Entry")
        text = f"{length:g} mm · Tip"
        painter.drawText(self.width()-painter.fontMetrics().horizontalAdvance(text), 25, text)


class DensityStrip(QWidget):
    sample_selected = Signal(int)

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.selected_index = None
        self.setMinimumHeight(56)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Peri-screw HU. Tap or use arrow keys to inspect entry to tip.")

    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()/max(1, len(self.result.hu))
        for index, value in enumerate(self.result.hu):
            painter.fillRect(int(index*width), 4, int(width)+1, self.height()-8, hu_color(value))
        if self.selected_index is not None:
            x = int((self.selected_index+.5)*width)
            painter.setPen(QPen(QColor("#0b1014"), 5))
            painter.drawLine(x, 0, x, self.height())
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawLine(x, 0, x, self.height())
        if self.hasFocus():
            painter.setPen(QPen(QColor("#7dd3ed"), 2))
            painter.drawRect(1, 1, self.width()-2, self.height()-2)

    def _select(self, index):
        if not len(self.result.hu):
            return
        self.selected_index = min(len(self.result.hu)-1, max(0, index))
        self.sample_selected.emit(self.selected_index)
        self.update()

    def _select_position(self, event):
        self._select(int(event.position().x()/max(1, self.width())*len(self.result.hu)))
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._select_position(event)

    def mouseMoveEvent(self, event):
        self._select_position(event)

    def keyPressEvent(self, event):
        index = self.selected_index if self.selected_index is not None else 0
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._select(index + (1 if event.key() == Qt.Key.Key_Right else -1))
        elif event.key() == Qt.Key.Key_Home:
            self._select(0)
        elif event.key() == Qt.Key.Key_End:
            self._select(len(self.result.hu)-1)
        else:
            super().keyPressEvent(event)


class ScrewAssessmentPanel(QFrame):
    locate_breach_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RodCard")
        self.results = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("SCREW ASSESSMENT")
        title.setObjectName("RodTitle")
        layout.addWidget(title)
        self.status = QLabel("No measurements")
        self.status.setObjectName("ConstructHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        # entry_note = QLabel("First 10 mm excluded from G–R")
        # entry_note.setStyleSheet("color:#f1c96b; font-size:12px;")
        # layout.addWidget(entry_note)

        # Keep the existing checkable API for volume-reset integration.
        self.hu_confirmed = QPushButton("Show CT values · HU")
        self.hu_confirmed.setObjectName("AssessmentTouch")
        self.hu_confirmed.setCheckable(True)
        self.hu_confirmed.setMinimumHeight(56)
        self.hu_confirmed.setAccessibleName("Show CT values in Hounsfield units")
        self.hu_confirmed.setToolTip("Use with calibrated CT Hounsfield units, not normalized intensities.")
        self.hu_confirmed.toggled.connect(self._toggle_hu)
        layout.addWidget(self.hu_confirmed)
        self.hu_note = QLabel("Use calibrated CT (HU)")
        self.hu_note.setObjectName("AssessmentNote")
        layout.addWidget(self.hu_note)
        self.hu_legend = HULegend()
        self.hu_legend.hide()
        layout.addWidget(self.hu_legend)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(12)
        layout.addLayout(self.rows)
        legend = QLabel("G–R: A 0 · B ≤2 · C ≤4 · D ≤6 · E >6 mm")
        legend.setWordWrap(True)
        legend.setObjectName("AssessmentNote")
        legend.setToolTip(
            "Estimated Gertzbein–Robbins grade after the fixed 10 mm entry exclusion.\n"
            "Whole-vertebra estimate; verify pedicle on CT.\n"
            "HU: mean in segmented bone in a 1 mm shell outside the shaft.\n"
            "0–1000 HU color scale; values outside it use the endpoint colors."
        )
        layout.addWidget(legend)
        self.setStyleSheet("""
            QPushButton#AssessmentTouch {
                background:#204c65; color:#f0f8fc; border:2px solid #548bab;
                border-radius:8px; padding:4px 8px; font-size:15px; font-weight:700;
            }
            QPushButton#AssessmentTouch:checked { background:#196c82; border-color:#84def3; }
            QPushButton#AssessmentTouch:pressed { background:#328ba4; }
            QPushButton#AssessmentTouch:focus { border-color:white; }
            QPushButton#AssessmentTouch:disabled { background:#1a2730; color:#718792; border-color:#344954; }
            QLabel#AssessmentNote { color:#b6cbd6; font-size:12px; }
        """)

    def _toggle_hu(self, checked):
        self.hu_confirmed.setText("Hide CT values · HU" if checked else "Show CT values · HU")
        self.hu_legend.setVisible(checked)
        self.hu_note.setText("Tap strip for HU · Entry → Tip" if checked else "Use calibrated CT (HU)")
        self._populate()

    def set_results(self, results):
        self.results = results
        self.status.setText("Screw mesh breach · estimated G–R")
        self._populate()

    def clear(self, text="Measuring…"):
        self.results = {}
        self.status.setText(text)
        self._populate()

    @staticmethod
    def _sample_text(result, index):
        value = result.hu[index]
        hu = f"{value:.0f} HU" if np.isfinite(value) else "No sample"
        return (f"{hu} · {result.depth_mm[index]:.1f} mm from entry\n"
                f"Bone coverage {result.coverage[index]:.0%}")

    def _populate(self):
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        for (level, side), result in self.results.items():
            card = QWidget()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(0, 5, 0, 5)
            layout.setSpacing(6)
            distance = result.breach_text
            label = QLabel(f"{level} {side[0].upper()}     {result.grade}     {distance}")
            label.setStyleSheet(f"color:{GRADE_COLORS[result.grade]}; font-size:15px; font-weight:700;")
            layout.addWidget(label)
            if result.breach_depth_mm is not None:
                location = QLabel(f"At {result.breach_depth_mm:.1f} mm from entry")
                location.setObjectName("AssessmentNote")
                layout.addWidget(location)
            if result.below_voxel_spacing:
                resolution = QLabel(f"Below voxel spacing ({min(result.voxel_spacing_mm):g} mm)")
                resolution.setStyleSheet("color:#f1c96b; font-size:12px;")
                resolution.setWordWrap(True)
                layout.addWidget(resolution)
            if result.breach_point_lps is not None:
                locate = QPushButton("Locate breach")
                locate.setObjectName("AssessmentTouch")
                locate.setMinimumHeight(56)
                locate.clicked.connect(
                    lambda _checked=False, key=(level, side): self.locate_breach_requested.emit(key))
                layout.addWidget(locate)
            if result.reason:
                reason = QLabel(result.reason)
                reason.setWordWrap(True)
                reason.setObjectName("AssessmentNote")
                layout.addWidget(reason)
            layout.addWidget(EntryBand(result))
            if self.hu_confirmed.isChecked():
                strip = DensityStrip(result)
                layout.addWidget(strip)
                value = QLabel("Tap strip for CT value")
                value.setObjectName("AssessmentNote")
                value.setMinimumHeight(38)
                value.setWordWrap(True)
                strip.sample_selected.connect(
                    lambda index, result=result, value=value: value.setText(self._sample_text(result, index)))
                layout.addWidget(value)
            self.rows.addWidget(card)
