from collections import OrderedDict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..workflows import WorkflowPage


class ProcedureShell(QWidget):
    """Top-stage workflow shell matching the surgical procedure sequence."""

    stage_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppRoot")
        self._pages: OrderedDict[str, WorkflowPage] = OrderedDict()
        self._buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        self.top_bar.setFixedHeight(56)
        top = QHBoxLayout(self.top_bar)
        top.setContentsMargins(14, 4, 18, 4)
        top.setSpacing(12)

        # PLACEHOLDER: Replace this BART LAB wordmark with the official PNG logo asset.
        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("BART LAB")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("Center for Biomedical and Robotics Technology")
        subtitle.setObjectName("BrandSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        top.addLayout(brand)
        top.addStretch(1)

        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(12)
        top.addLayout(self.stage_row)
        top.addStretch(1)

        root.addWidget(self.top_bar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

    def add_workflow(self, page: WorkflowPage) -> None:
        key = page.workflow_key
        if key in self._pages:
            raise ValueError(f"Workflow already registered: {key}")

        self._pages[key] = page
        self.stack.addWidget(page)

        button = QPushButton(page.workflow_title)
        button.setObjectName("StageButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _checked=False, k=key: self.activate(k))
        self._buttons[key] = button
        self.stage_row.addWidget(button)

        if len(self._pages) == 1:
            self.activate(key)

    def activate(self, key: str) -> None:
        page = self._pages[key]
        previous = self.stack.currentWidget()
        if previous is not None and previous is not page:
            previous.on_deactivated()

        self.stack.setCurrentWidget(page)
        for button_key, button in self._buttons.items():
            button.setChecked(button_key == key)

        page.on_activated()
        self.stage_changed.emit(key)
