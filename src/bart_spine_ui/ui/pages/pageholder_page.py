from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ...workflows import WorkflowPage


class PlaceholderPage(WorkflowPage):
    """PLACEHOLDER: Legacy temporary screen for an unimplemented workflow stage."""
    def __init__(self, key: str, title: str, message: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._title = title

        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 22px; color: #8fa6bc;")
        layout.addWidget(label, 1)

    @property
    def workflow_key(self) -> str:
        return self._key

    @property
    def workflow_title(self) -> str:
        return self._title
