from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QWidget,
)

from ..workflows import WorkflowPage, WorkflowRegistry


class WorkflowShell(QWidget):
    """
    Main page host.

    The current starter has one Imaging workflow. As Planning, Registration, Robot, and
    Navigation are implemented, register them and they appear in the left workflow rail.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.registry = WorkflowRegistry()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.navigation = QListWidget()
        self.navigation.setFixedWidth(150)
        self.navigation.setFocusPolicy(Qt.NoFocus)

        self.stack = QStackedWidget()

        layout.addWidget(self.navigation)
        layout.addWidget(self.stack, 1)

        self.navigation.currentRowChanged.connect(self._switch_page)

    def add_workflow(self, page: WorkflowPage) -> None:
        self.registry.register(page)

        item = QListWidgetItem(page.workflow_title)
        item.setData(Qt.UserRole, page.workflow_key)
        self.navigation.addItem(item)
        self.stack.addWidget(page)

        if self.navigation.count() == 1:
            self.navigation.setCurrentRow(0)

    def _switch_page(self, row: int) -> None:
        if row < 0 or row >= self.stack.count():
            return

        old_page = self.stack.currentWidget()
        new_page = self.stack.widget(row)

        if old_page is not None and old_page is not new_page:
            old_page.on_deactivated()

        self.stack.setCurrentIndex(row)

        if new_page is not None:
            new_page.on_activated()
