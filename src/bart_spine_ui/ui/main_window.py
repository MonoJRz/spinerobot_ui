from PySide6.QtWidgets import QMainWindow, QStatusBar

from .pages.imaging_page import ImagingPage
from .pages.placeholder_page import PlaceholderPage
from .procedure_shell import ProcedureShell


class MainWindow(QMainWindow):
    """BART Spine surgical workflow application shell."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BART Spine")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)

        self.procedure_shell = ProcedureShell()
        self.setCentralWidget(self.procedure_shell)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("BART Spine — Setup")

        self._register_workflows()
        self.procedure_shell.stage_changed.connect(
            lambda key: self.statusBar().showMessage(f"BART Spine — {key.title()}")
        )

    def _register_workflows(self) -> None:
        setup = ImagingPage()
        setup.status_changed.connect(self.statusBar().showMessage)
        # PLACEHOLDER: Replace these pages as each workflow is implemented.
        self.procedure_shell.add_workflow(setup)

        self.procedure_shell.add_workflow(
            PlaceholderPage("planning", "Planning", "Planning workflow — next development stage")
        )
        self.procedure_shell.add_workflow(
            PlaceholderPage("calibration", "Calibration", "Calibration workflow — next development stage")
        )
        self.procedure_shell.add_workflow(
            PlaceholderPage("navigate", "Navigate", "Navigation workflow — next development stage")
        )
