"""Compact, keyboard-accessible anatomical level selection."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..planning.service import LEVEL_ORDER


class SpineLevelSelector(QFrame):
    selection_changed = Signal()

    def __init__(self, selected=(), parent=None):
        super().__init__(parent)
        self.buttons = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Screw levels · tap to select"))
        regions = QHBoxLayout()
        for prefix, name in (("C", "Cervical"), ("T", "Thoracic"),
                             ("L", "Lumbar"), ("S", "Sacral")):
            column = QVBoxLayout()
            column.setSpacing(3)
            column.addWidget(QLabel(name))
            for level in LEVEL_ORDER:
                if not level.startswith(prefix):
                    continue
                button = QPushButton(level)
                button.setCheckable(True)
                button.setChecked(level in selected)
                button.setMinimumSize(70, 27)
                button.setAccessibleName(f"{level} screw level")
                button.setToolTip(f"Select {level} for left and right screws")
                button.toggled.connect(lambda _checked: self.selection_changed.emit())
                column.addWidget(button)
                self.buttons[level] = button
            column.addStretch(1)
            regions.addLayout(column)
        layout.addLayout(regions)
        self.setStyleSheet("""
            QLabel { color:#b9d6e6; }
            QPushButton { background:#182d3a; color:#c5d7e2; border:1px solid #39586b;
                          border-radius:5px; padding:3px; }
            QPushButton:checked { background:#236a83; color:white; border:2px solid #7dd3ed; }
            QPushButton:focus { border:2px solid white; }
        """)

    def selected_levels(self):
        return [level for level, button in self.buttons.items() if button.isChecked()]
