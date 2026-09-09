from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..planning import ScrewPlan, Side


class ScrewTablePanel(QFrame):
    """Selectable table of the screws stored in the current plan."""

    target_requested = Signal(str, str)
    delete_requested = Signal(str, str)
    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScrewTablePanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(380)
        self.setStyleSheet(
            """
            QFrame#ScrewTablePanel {
                background: #0d171e; border-left: 1px solid #254353;
            }
            QFrame#ScrewTablePanel QLabel#TableTitle {
                color: #e8f7ff; font-size: 14px; font-weight: 700;
            }
            QFrame#ScrewTablePanel QLabel#TableHint { color: #7f9aa9; font-size: 11px; }
            QFrame#ScrewTablePanel QPushButton {
                min-width: 34px; min-height: 32px; background: #12384b;
                color: #82d8ff; border: 1px solid #2c6e8c; border-radius: 5px;
                font-size: 18px; font-weight: 700;
            }
            QFrame#ScrewTablePanel QPushButton:hover { background: #19536c; color: white; }
            QFrame#ScrewTablePanel QTableWidget {
                background: #081116; alternate-background-color: #0d1b23;
                color: #d9e8ef; border: 1px solid #203b49; gridline-color: #1b3441;
                selection-background-color: #18506a; selection-color: #ffffff;
            }
            QFrame#ScrewTablePanel QHeaderView::section {
                background: #10232e; color: #8fcce8; border: 0;
                border-right: 1px solid #24414f; border-bottom: 1px solid #24414f;
                padding: 7px 3px; font-size: 10px; font-weight: 700;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 11, 10, 12)
        root.setSpacing(9)
        header = QHBoxLayout()
        icon = QLabel("▤")
        icon.setObjectName("TableTitle")
        title = QLabel("SCREW TABLE")
        title.setObjectName("TableTitle")
        self.add_button = QPushButton("+")
        self.add_button.setToolTip("Mark or re-mark the active screw entry point")
        self.delete_button = QPushButton("✕")
        self.delete_button.setToolTip("Delete the selected screw")
        self.delete_button.setEnabled(False)
        header.addWidget(icon)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.add_button)
        header.addWidget(self.delete_button)
        root.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Level", "Side", "Ø mm", "L mm", "Status"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(42)
        root.addWidget(self.table, 1)

        self.hint = QLabel(
            "Screws are saved automatically. Select a row to review or adjust it."
        )
        self.hint.setObjectName("TableHint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        self._row_keys: list[tuple[str, Side]] = []
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda row, _column: self._activate_row(row))
        self.add_button.clicked.connect(self.add_requested)
        self.delete_button.clicked.connect(self._request_delete)

    def set_plans(
        self,
        plans: Mapping[tuple[str, Side], ScrewPlan],
        accepted: set[tuple[str, Side]],
        active_key: tuple[str, Side] | None,
    ) -> None:
        selected_key = self.selected_key()
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            self._row_keys = []
            for key, plan in plans.items():
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._row_keys.append(key)
                values = (
                    plan.level,
                    plan.side.upper(),
                    f"{plan.diameter_mm:.1f}",
                    f"{plan.length_mm:.0f}",
                    "ACCEPTED" if key in accepted else "DRAFT",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if column == 4:
                        item.setForeground(QColor("#7ee787" if key in accepted else "#e3b341"))
                    self.table.setItem(row, column, item)

            key_to_select = active_key if active_key in plans else selected_key
            if key_to_select in self._row_keys:
                self.table.selectRow(self._row_keys.index(key_to_select))
        finally:
            self.table.blockSignals(False)
        self._sync_empty_state()
        self.delete_button.setEnabled(self.selected_key() is not None)

    def clear(self) -> None:
        self.table.setRowCount(0)
        self._row_keys.clear()
        self._sync_empty_state()
        self.delete_button.setEnabled(False)

    def selected_key(self) -> tuple[str, Side] | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._row_keys):
            return self._row_keys[row]
        return None

    def _sync_empty_state(self) -> None:
        empty = not self._row_keys
        self.hint.setText(
            "No screws planned yet. Select a level and press + or MARK ENTRY POINT."
            if empty
            else "Screws are saved automatically. Select a row to review or adjust it."
        )

    def _selection_changed(self) -> None:
        key = self.selected_key()
        self.delete_button.setEnabled(key is not None)
        if key is not None:
            self.target_requested.emit(key[0], key[1])

    def _activate_row(self, row: int) -> None:
        if 0 <= row < len(self._row_keys):
            key = self._row_keys[row]
            self.target_requested.emit(key[0], key[1])

    def _request_delete(self) -> None:
        key = self.selected_key()
        if key is not None:
            self.delete_requested.emit(key[0], key[1])
