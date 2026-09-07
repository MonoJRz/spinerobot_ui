from PySide6.QtWidgets import QMainWindow, QStatusBar

from .pages import ImagingPage
from .workflow_shell import WorkflowShell


class MainWindow(QMainWindow):
    """
    Thin application shell.

    Keep this class thin. Procedure logic belongs in workflow pages/controllers, not here.
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("BART Spine")
        self.resize(1420, 920)

        self.workflow_shell = WorkflowShell()
        self.setCentralWidget(self.workflow_shell)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(
            "Standalone mode — PySide6 + VTK + SimpleITK"
        )

        self._register_workflows()

    def _register_workflows(self) -> None:
        imaging_page = ImagingPage()
        imaging_page.status_changed.connect(self.statusBar().showMessage)

        self.workflow_shell.add_workflow(imaging_page)

        # Add future pages here, for example:
        #
        # self.workflow_shell.add_workflow(PlanningPage(...))
        # self.workflow_shell.add_workflow(RegistrationPage(...))
        # self.workflow_shell.add_workflow(RobotPage(...))
        # self.workflow_shell.add_workflow(NavigationPage(...))
