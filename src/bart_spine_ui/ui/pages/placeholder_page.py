from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ...workflows import WorkflowPage


class PlaceholderPage(WorkflowPage):
    """
    PLACEHOLDER: Temporary screen for an unimplemented workflow stage.

    Temporary page used for workflow stages that have not been implemented yet.

    This keeps the main workflow navigation functional while allowing each stage
    to be developed independently later.
    """

    def __init__(
        self,
        workflow_key: str,
        workflow_title: str,
        description: str = "",
        parent=None,
    ):
        super().__init__(parent)

        self._workflow_key = workflow_key
        self._workflow_title = workflow_title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel(workflow_title)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 28px; font-weight: 700;"
        )

        description_label = QLabel(
            description or f"{workflow_title} workflow will be implemented here."
        )
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            "font-size: 15px; color: #7a8793;"
        )

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(description_label)
        layout.addStretch(1)

    @property
    def workflow_key(self) -> str:
        return self._workflow_key

    @property
    def workflow_title(self) -> str:
        return self._workflow_title
