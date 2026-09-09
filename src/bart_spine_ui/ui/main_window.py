from PySide6.QtWidgets import QMainWindow

from ..controllers import ImagingController
from .pages.imaging_page import ImagingPage
from .pages.placeholder_page import PlaceholderPage
from .pages.planning_page import PlanningPage
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
        # Setup and Planning share the same CT state.
        self.imaging_controller = ImagingController(parent=self)

        setup = ImagingPage(controller=self.imaging_controller)
        setup.dataset_changed.connect(self.procedure_shell.set_dataset_status)
        setup.readiness_changed.connect(self.procedure_shell.set_system_status)
        self.procedure_shell.add_workflow(setup)

        planning = PlanningPage(controller=self.imaging_controller)
        self.procedure_shell.add_workflow(planning)

        # Planning consumes the Region already shown in CASE INFORMATION.
        planning.set_case_region(setup.right_sidebar.case_values["Region"].text())
        setup.right_sidebar.case_changed.connect(
            lambda _case_id, _modality, _anatomy, region, _patient: planning.set_case_region(region)
        )

        # PLACEHOLDER: Replace these pages as each workflow is implemented.
        self.procedure_shell.add_workflow(
            PlaceholderPage(
                "calibration",
                "Calibration",
                "Calibration workflow — next development stage",
            )
        )
        self.procedure_shell.add_workflow(
            PlaceholderPage(
                "navigate",
                "Navigate",
                "Navigation workflow — next development stage",
            )
        )
