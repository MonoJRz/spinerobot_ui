from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PlanningLeftSidebar(QFrame):
    segmentation_requested = Signal()
    accept_next_requested = Signal()
    reject_requested = Signal()
    target_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftSidebar")
        self.setFixedWidth(320)
        self._running = False
        self._loading = False
        self._marking = False
        # Explicit plan state; do not infer it from button enabled state.
        self._has_plan = False
        self._target_buttons: dict[tuple[str, str], QPushButton] = {}
        self._planned: set[tuple[str, str]] = set()
        self._active_key: tuple[str, str] | None = None

        shell = QVBoxLayout(self)
        shell.setContentsMargins(10, 10, 7, 10)
        shell.setSpacing(0)
        scroll = QScrollArea()
        scroll.setObjectName("PlanningSidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("PlanningSidebarContent")
        palette = content.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0d151b"))
        content.setPalette(palette)
        content.setAutoFillBackground(True)
        scroll.viewport().setPalette(palette)
        scroll.viewport().setAutoFillBackground(True)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(9)
        scroll.setWidget(content)
        shell.addWidget(scroll)

        self.segmentation_card, segmentation_layout = self._card("◫   SEGMENTATION")
        self.segmentation_button = QPushButton("◈    RUN SEGMENTATION")
        self.segmentation_button.setObjectName("PrimaryAction")
        segmentation_layout.addWidget(self.segmentation_button)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusWaiting")
        self.status_label.setWordWrap(True)
        segmentation_layout.addWidget(self.status_label)
        self.loading_progress = QProgressBar()
        self.loading_progress.setObjectName("SegmentationLoadProgress")
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.hide()
        segmentation_layout.addWidget(self.loading_progress)
        self.content_layout.addWidget(self.segmentation_card)

        self.levels_card, levels_layout = self._card("▤   LEVEL OF INTEREST")
        self.levels_grid = QGridLayout()
        self.levels_grid.setContentsMargins(0, 2, 0, 0)
        self.levels_grid.setHorizontalSpacing(7)
        self.levels_grid.setVerticalSpacing(7)
        levels_layout.addLayout(self.levels_grid)
        self.content_layout.addWidget(self.levels_card)

        self.three_d_host = QVBoxLayout()
        self.three_d_host.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addLayout(self.three_d_host)

        current = QFrame()
        current.setObjectName("SidebarCard")
        current_layout = QVBoxLayout(current)
        current_layout.setContentsMargins(14, 11, 14, 13)
        current_layout.setSpacing(8)
        self.target_label = QLabel("SELECT LEVEL + SIDE")
        self.target_label.setObjectName("StatusGroup")
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        current_layout.addWidget(self.target_label)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(9)
        metrics.setVerticalSpacing(4)
        metrics.addWidget(self._metric_key("Depth"), 0, 0)
        self.depth_value = self._metric_value("—")
        metrics.addWidget(self.depth_value, 0, 1)
        metrics.addWidget(self._metric_key("Pedicle"), 1, 0)
        self.width_value = self._metric_value("—")
        metrics.addWidget(self.width_value, 1, 1)
        metrics.addWidget(self._metric_key("Screw"), 2, 0)
        self.screw_value = self._metric_value("—")
        metrics.addWidget(self.screw_value, 2, 1)
        current_layout.addLayout(metrics)

        decision = QHBoxLayout()
        decision.setSpacing(8)
        self.reject_button = QPushButton("✕")
        self.reject_button.setObjectName("RejectPlanningButton")
        self.reject_button.setToolTip("Reject this entry point and screw")
        self.reject_button.setEnabled(False)
        self.accept_button = QPushButton("✓")
        self.accept_button.setObjectName("AcceptPlanningButton")
        self.accept_button.setToolTip("Accept this screw and continue")
        self.accept_button.setEnabled(False)
        decision.addWidget(self.reject_button)
        decision.addWidget(self.accept_button)
        current_layout.addLayout(decision)
        self.content_layout.addWidget(current)
        self.content_layout.addStretch(1)

        self.segmentation_button.clicked.connect(self.segmentation_requested)
        self.accept_button.clicked.connect(self.accept_next_requested)
        self.reject_button.clicked.connect(self.reject_requested)

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SidebarCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 11, 14, 13)
        layout.setSpacing(7)
        header = QLabel(title)
        header.setObjectName("CardTitle")
        layout.addWidget(header)
        divider = QFrame()
        divider.setObjectName("CardDivider")
        layout.addWidget(divider)
        return card, layout

    @staticmethod
    def _metric_key(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("RangeText")
        return label

    @staticmethod
    def _metric_value(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SidebarValue")
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    def set_three_d_view(self, view: QWidget) -> None:
        view.setMinimumHeight(270)
        view.setMaximumHeight(360)
        self.three_d_host.addWidget(view)
        view.show()

    def set_ct(self, _name: str | None) -> None:
        pass

    def set_output_directory(self, _path: str | None) -> None:
        pass

    def set_case_region(self, _region: str | None, levels: list[str]) -> None:
        self.set_levels(levels)

    def set_levels(self, levels: list[str]) -> None:
        self.levels_card.setMinimumHeight(70 + max(1, len(levels)) * 37)
        while self.levels_grid.count():
            item = self.levels_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._target_buttons.clear()
        if not levels:
            placeholder = QLabel("Set case levels in Setup")
            placeholder.setObjectName("RangeText")
            self.levels_grid.addWidget(placeholder, 0, 0, 1, 3)
            return

        for column, text in ((1, "LEFT"), (2, "RIGHT")):
            label = QLabel(text)
            label.setObjectName("RangeText")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.levels_grid.addWidget(label, 0, column)
        for row, level in enumerate(levels, start=1):
            label = QLabel(level)
            label.setObjectName("StatusGroup")
            self.levels_grid.addWidget(label, row, 0)
            for column, side in ((1, "left"), (2, "right")):
                button = QPushButton("○")
                button.setObjectName("CardAction")
                button.setFixedHeight(30)
                button.setToolTip(f"Mark {level} {side} pedicle entry")
                button.clicked.connect(
                    lambda _checked=False, l=level, s=side: self.target_requested.emit(l, s)
                )
                self.levels_grid.addWidget(button, row, column)
                self._target_buttons[(level, side)] = button
        self._refresh_target_buttons()

    def set_target(
        self,
        _index: int,
        _total: int,
        level: str,
        side: str,
        *,
        has_plan: bool,
    ) -> None:
        self._active_key = (level, side)
        self._has_plan = bool(has_plan)
        self.target_label.setText(f"{level}  ·  {side.upper()}")
        self.accept_button.setEnabled(self._has_plan and not self._marking)
        self.reject_button.setEnabled(True)
        self._refresh_target_buttons()

    def set_marking(self, marking: bool) -> None:
        self._marking = bool(marking)
        if self._active_key is not None:
            level, side = self._active_key
            suffix = "  ·  TAP ENTRY" if marking else ""
            self.target_label.setText(f"{level}  ·  {side.upper()}{suffix}")
        self.accept_button.setEnabled(not marking and self.accept_button.isEnabled())
        self.reject_button.setEnabled(self._active_key is not None)

    def set_plan_measurements(
        self,
        *,
        anatomical_length_mm: float,
        pedicle_width_mm: float,
        diameter_mm: float,
        length_mm: float,
        warning: str | None = None,
    ) -> None:
        self.depth_value.setText(f"{anatomical_length_mm:.1f} mm")
        self.width_value.setText(f"{pedicle_width_mm:.1f} mm")
        self.screw_value.setText(f"Ø{diameter_mm:.1f} × {length_mm:.0f}")
        self._has_plan = True
        self.accept_button.setEnabled(not self._marking)
        if warning:
            self.target_label.setToolTip(warning)

    def clear_plan_measurements(self) -> None:
        self.depth_value.setText("—")
        self.width_value.setText("—")
        self.screw_value.setText("—")
        self._has_plan = False
        self.accept_button.setEnabled(False)

    def set_completed(self, planned: set[tuple[str, str]]) -> None:
        self._planned = set(planned)
        self._refresh_target_buttons()

    def _refresh_target_buttons(self) -> None:
        for key, button in self._target_buttons.items():
            active = key == self._active_key
            done = key in self._planned
            button.setText("●" if active else "✓" if done else "○")
            if active:
                button.setStyleSheet(
                    "QPushButton { background:#15384d; border:1px solid #58a6ff; "
                    "color:#ffffff; border-radius:6px; font-weight:700; }"
                )
            elif done:
                button.setStyleSheet(
                    "QPushButton { color:#7ee787; border:1px solid #355942; "
                    "border-radius:6px; font-weight:700; }"
                )
            else:
                button.setStyleSheet("")

    def set_running(self, running: bool) -> None:
        self._running = running
        self._sync_action_state()

    def set_loading(self, loading: bool) -> None:
        was_loading = self._loading
        self._loading = loading
        self.loading_progress.setVisible(loading)
        if loading and not was_loading:
            self.loading_progress.setValue(0)
        self._sync_action_state()

    def set_loading_progress(self, value: int, text: str) -> None:
        self.loading_progress.setValue(max(0, min(100, value)))
        self.loading_progress.setFormat(f"{text} — %p%")

    def set_segmentation_ready(self, ready: bool = True) -> None:
        self.segmentation_button.setVisible(not ready)
        self.loading_progress.hide()
        if ready:
            self.status_label.setText("✓  SEGMENTATION READY")
            self.status_label.setObjectName("StatusOk")
            self.segmentation_card.setMaximumHeight(74)
        else:
            self.segmentation_card.setMaximumHeight(16777215)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _sync_action_state(self) -> None:
        busy = self._running or self._loading
        self.segmentation_button.setEnabled(not busy)
        self.segmentation_button.setText(
            "◌    SEGMENTING..."
            if self._running
            else "◌    LOADING..."
            if self._loading
            else "◈    RUN SEGMENTATION"
        )

    def set_status(self, text: str, state: str = "waiting") -> None:
        object_names = {
            "waiting": "StatusWaiting",
            "ok": "StatusOk",
            "error": "StatusError",
            "warning": "StatusWarn",
        }
        self.status_label.setText(text)
        self.status_label.setObjectName(object_names.get(state, "StatusWaiting"))
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
