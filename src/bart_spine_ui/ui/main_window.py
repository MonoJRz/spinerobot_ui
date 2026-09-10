from PySide6.QtWidgets import QMainWindow

from ..controllers import ImagingController
from ..robot.ros_client import RobotRosClient
from .pages.imaging_page import ImagingPage
from .pages.placeholder_page import PlaceholderPage
from .pages.planning_construct_page import PlanningPage
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

        # Build UI first so setup_page exists before ROS signals are connected.
        self._register_workflows()

        # Shared ROS 2 robot client.
        self.robot_client = RobotRosClient(parent=self)

        # Update the TRACKING & ROBOT card and SETUP STATUS.
        self.robot_client.connection_changed.connect(
            self.setup_page.set_robot_connected
        )

        # Optional diagnostic signal.
        self.robot_client.joint_state_changed.connect(
            self._on_joint_state_changed
        )

        # Report ROS errors in the setup log.
        self.robot_client.ros_error.connect(
            self._on_robot_ros_error
        )

    def _register_workflows(self) -> None:
        # Setup and Planning share the same CT state.
        self.imaging_controller = ImagingController(parent=self)

        self.setup_page = ImagingPage(
            controller=self.imaging_controller
        )

        self.setup_page.dataset_changed.connect(
            self.procedure_shell.set_dataset_status
        )

        self.setup_page.readiness_changed.connect(
            self.procedure_shell.set_system_status
        )

        self.procedure_shell.add_workflow(
            self.setup_page
        )

        self.planning_page = PlanningPage(
            controller=self.imaging_controller
        )

        self.procedure_shell.add_workflow(
            self.planning_page
        )

        # Planning consumes the Region already shown in CASE INFORMATION.
        self.planning_page.set_case_region(
            self.setup_page.right_sidebar.case_values["Region"].text()
        )

        self.setup_page.right_sidebar.case_changed.connect(
            lambda _case_id,
                   _modality,
                   _anatomy,
                   region,
                   _patient:
            self.planning_page.set_case_region(region)
        )

        self.procedure_shell.add_workflow(
            PlaceholderPage(
                "calibration",
                "Calibration",
                "Calibration workflow — next development stage",
            )
        )

        self.procedure_shell.add_workflow(
            PlaceholderPage(
                "navigation",
                "Navigation",
                "Navigation workflow — next development stage",
            )
        )

    def _on_joint_state_changed(self, state):
        """
        Joint-state communication is intentionally received here,
        but do not continuously print it because xArm publishes rapidly.
        """
        pass

    def _on_robot_ros_error(self, message: str):
        print(f"[ROS ERROR] {message}")

        self.setup_page.right_sidebar.add_log(
            f"Robot ROS error: {message}"
        )

    def closeEvent(self, event):
        if hasattr(self, "robot_client"):
            self.robot_client.shutdown()

        super().closeEvent(event)