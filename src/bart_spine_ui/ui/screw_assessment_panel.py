"""Compact level-by-level grading and a separate CT analysis dialog."""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..planning.assessment import DEFAULT_ENTRY_EXCLUSION_MM, ScrewAssessmentService
from ..planning.service import LEVEL_ORDER
from .hu_analysis_dialog import HUAnalysisDialog

GRADE_COLORS = {"A": "#7ee787", "B": "#d7df74", "C": "#f1c96b",
                "D": "#ff9a62", "E": "#ff737e", "—": "#8ea9ba"}


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


class ScrewAssessmentPanel(QFrame):
    locate_breach_requested = Signal(object)
    PAGE_SIZE = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RodCard")
        self.results = {}
        self.levels = []
        self.accepted = set()
        self.skipped = set()
        self.page = 0
        self.selected_key = None
        self.hu_dialog = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        title = QLabel("SCREW GRADING · G–R")
        title.setObjectName("RodTitle")
        title_row = QHBoxLayout()
        title_row.addWidget(title, 1)
        layout.addLayout(title_row)
        self.status = QLabel("No measurements")
        self.status.setObjectName("AssessmentNote")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.rows = QGridLayout()
        self.rows.setSpacing(6)
        self.rows.setColumnStretch(1, 1)
        self.rows.setColumnStretch(2, 1)
        layout.addLayout(self.rows)
        pager = QHBoxLayout()
        self.previous = QPushButton("←")
        self.next = QPushButton("→")
        self.previous.setFixedSize(30, 28)
        self.next.setFixedSize(30, 28)
        self.previous.setAccessibleName("Previous five levels")
        self.next.setAccessibleName("Next five levels")
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previous.clicked.connect(lambda: self._change_page(-1))
        self.next.clicked.connect(lambda: self._change_page(1))
        pager.addWidget(self.previous)
        pager.addWidget(self.page_label, 1)
        pager.addWidget(self.next)
        title_row.addLayout(pager)
        self.detail = QLabel("Select a G–R box for breach details")
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(40)
        self.detail.setObjectName("AssessmentNote")
        layout.addWidget(self.detail)
        self.locate_button = QPushButton("Locate selected breach in 3D")
        self.locate_button.setMinimumHeight(38)
        self.locate_button.setEnabled(False)
        self.locate_button.clicked.connect(self._locate_selected)
        layout.addWidget(self.locate_button)
        layout.addStretch(1)
        # legend = QLabel("G–R: A 0 · B ≤2 · C ≤4 · D ≤6 · E >6 mm")
        # legend.setWordWrap(True)
        # legend.setObjectName("AssessmentNote")
        # layout.addWidget(legend)
        # note = QLabel(f"Estimated whole-vertebra grade · first {DEFAULT_ENTRY_EXCLUSION_MM:g} mm excluded")
        # note.setWordWrap(True)
        # note.setObjectName("AssessmentNote")
        # layout.addWidget(note)
        self.hu_confirmed = QPushButton("Open HU analysis ↗")
        self.hu_confirmed.setCheckable(True)
        self.hu_confirmed.setMinimumHeight(44)
        self.hu_confirmed.setEnabled(False)
        self.hu_confirmed.toggled.connect(self._toggle_hu)
        layout.addWidget(self.hu_confirmed)
        self.setStyleSheet("""
            QLabel#AssessmentNote { color:#bccbd7; font-size:12px; }
            QPushButton { background:#24384a; color:#f2f6ff; border:1px solid #55758f;
                border-radius:6px; padding:5px; font-size:13px; }
            QPushButton:disabled { color:#778a99; border-color:#344452; }
            QPushButton:focus { border:2px solid #f0f5ff; }
            QPushButton:checked { background:#364d67; }
        """)

    def set_targets(self, levels, accepted, skipped):
        self.levels = list(levels)
        self.accepted, self.skipped = set(accepted), set(skipped)
        self.page = 0
        self._populate()

    def _change_page(self, direction):
        self.page = max(0, min(self.page+direction, (len(self.levels)-1)//self.PAGE_SIZE))
        self._populate()

    def set_results(self, results):
        self.hu_confirmed.setChecked(False)
        self.results = results
        if not self.levels:
            self.levels = sorted({key[0] for key in results}, key=LEVEL_ORDER.index)
        self.status.setText("")
        self.status.hide()
        self.hu_confirmed.setEnabled(bool(results))
        self._populate()

    def clear(self, text="Measuring…"):
        self.hu_confirmed.setChecked(False)
        self.hu_confirmed.setEnabled(False)
        self.results = {}
        self.selected_key = None
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self._populate()

    def _populate(self):
        while self.rows.count():
            widget = self.rows.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self.grade_buttons = {}
        for column, text in enumerate(("LEVEL", "LEFT · G–R", "RIGHT · G–R")):
            label = QLabel(text)
            label.setStyleSheet("color:#b7cadb; font-size:12px; font-weight:700;")
            self.rows.addWidget(label, 0, column)
        visible = self.levels[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]
        for row, level in enumerate(visible, 1):
            label = QLabel(level)
            label.setStyleSheet("color:#f0f5ff; font-size:17px; font-weight:700;")
            self.rows.addWidget(label, row, 0)
            for column, side in enumerate(("left", "right"), 1):
                key = (level, side)
                result = self.results.get(key)
                if key in self.skipped:
                    text, color = "Skipped", "#8ea9ba"
                elif result is not None:
                    text = f"G–R {result.grade}  ·  {result.breach_text}"
                    color = GRADE_COLORS.get(result.grade, GRADE_COLORS["—"])
                else:
                    text = "Measuring…" if key in self.accepted else "Not planned"
                    color = "#8ea9ba"
                button = QPushButton(text)
                button.setMinimumHeight(48)
                button.setCheckable(True)
                button.setAccessibleName(f"{level} {side}: {text}")
                button.setStyleSheet(
                    f"QPushButton {{color:{color}; border:1px solid {color}; "
                    "background:#1b2b39; font-size:13px; font-weight:700;}"
                    "QPushButton:checked {background:#31485a; border:2px solid #edf4ff;}"
                )
                button.clicked.connect(lambda checked=False, key=key: self._select(key))
                self.rows.addWidget(button, row, column)
                self.grade_buttons[key] = button
        paged = len(self.levels) > self.PAGE_SIZE
        self.previous.setVisible(paged)
        self.next.setVisible(paged)
        self.page_label.setVisible(paged)
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled((self.page+1)*self.PAGE_SIZE < len(self.levels))
        self.page_label.setText(f"{self.page+1} / {max(1, (len(self.levels)+self.PAGE_SIZE-1)//self.PAGE_SIZE)}")
        if self.selected_key not in self.grade_buttons:
            self.selected_key = next((key for key in self.grade_buttons if key in self.results), None)
        self._select(self.selected_key)

    def _select(self, key):
        self.selected_key = key
        result = self.results.get(key)
        self.locate_button.setEnabled(result is not None and result.breach_point_lps is not None)
        for target, button in self.grade_buttons.items():
            button.setChecked(target == key)
        if result is None:
            self.detail.setText("Select a G–R box for breach details" if key is None else
                                f"{key[0]} {key[1]} · " + ("Skipped" if key in self.skipped else "No measurements"))
            return
        text = f"{key[0]} {key[1].upper()} · G–R {result.grade} · breach {result.breach_text}"
        if result.breach_depth_mm is not None:
            text += f"\nAt {result.breach_depth_mm:.1f} mm from entry"
        if result.below_voxel_spacing:
            text += f" · Below voxel spacing ({min(result.voxel_spacing_mm):g} mm)"
        if result.reason:
            text += f"\n{result.reason}"
        self.detail.setText(text)

    def _locate_selected(self):
        if self.locate_button.isEnabled():
            self.locate_breach_requested.emit(self.selected_key)

    def _toggle_hu(self, checked):
        if not checked:
            if self.hu_dialog is not None:
                self.hu_dialog.close()
            return
        if not self.results:
            self.hu_confirmed.setChecked(False)
            return
        if self.hu_dialog is not None:
            self.hu_dialog.deleteLater()
        self.hu_dialog = HUAnalysisDialog(self.results, self, levels=self.levels, skipped=self.skipped)
        self.hu_dialog.finished.connect(lambda _: self.hu_confirmed.setChecked(False))
        if self.selected_key in self.results:
            self.hu_dialog.focus_target(self.selected_key)
        self.hu_dialog.show()
        self.hu_dialog.raise_()

    def hideEvent(self, event):
        self.hu_confirmed.setChecked(False)
        super().hideEvent(event)
