from PySide6.QtWidgets import QMainWindow

from .pages.imaging_page import ImagingPage
from .pages.placeholder_page import PlaceholderPage
from .procedure_shell import ProcedureShell


class MainWindow(QMainWindow):
    """BART Spine surgical workflow application shell."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BART Spine")
        self.resize(1680, 940)
        self.setMinimumSize(1280, 760)

        self.procedure_shell = ProcedureShell()
        self.setCentralWidget(self.procedure_shell)

        self._register_workflows()

    def _register_workflows(self) -> None:
        setup = ImagingPage()
        setup.dataset_changed.connect(self.procedure_shell.set_dataset_status)
        setup.readiness_changed.connect(self.procedure_shell.set_system_status)
        self.procedure_shell.add_workflow(setup)

        # PLACEHOLDER: Replace these pages as each workflow is implemented.
        self.procedure_shell.add_workflow(
            PlaceholderPage("planning", "Planning", "Planning workflow — next development stage")
        )
        self.procedure_shell.add_workflow(
            PlaceholderPage("calibration", "Calibration", "Calibration workflow — next development stage")
        )
        self.procedure_shell.add_workflow(
            PlaceholderPage("navigate", "Navigate", "Navigation workflow — next development stage")
        )
