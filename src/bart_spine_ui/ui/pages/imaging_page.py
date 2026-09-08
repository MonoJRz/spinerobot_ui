from os import environ
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox

from ...controllers import ImagingController
from ...imaging.models import MedicalVolume
from ...visualization import ImagingWorkspace
from ...workflows import WorkflowPage
from ..setup_left_sidebar import SetupLeftSidebar
from ..setup_right_sidebar import SetupRightSidebar


class ImagingPage(WorkflowPage):
    """Setup stage: image import, CT display, system readiness, and four-view verification."""

    dataset_changed = Signal(str)
    readiness_changed = Signal(str, str)

    def __init__(self, controller: ImagingController | None = None, parent=None):
        super().__init__(parent)

        self.controller = controller or ImagingController(parent=self)
        self._setup_states: dict[str, bool | None] = {
            "case": None,
            "ct": None,
            "robot": None,
            "end_effector": None,
            "tracking": None,
            "tool_marker": None,
            "robot_marker": None,
            "patient_marker": None,
        }

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.left_sidebar = SetupLeftSidebar()
        self.workspace = ImagingWorkspace()
        self.right_sidebar = SetupRightSidebar()

        main.addWidget(self.left_sidebar)
        main.addWidget(self.workspace, 1)
        main.addWidget(self.right_sidebar)

        self.left_sidebar.import_dicom_requested.connect(self._choose_dicom_directory)
        self.left_sidebar.load_volume_requested.connect(self._choose_file)
        self.left_sidebar.window_level_changed.connect(self.workspace.set_window_level)
        self.left_sidebar.interpolation_changed.connect(self.workspace.set_linear_interpolation)
        self.right_sidebar.case_changed.connect(self.set_case)

        self.controller.volume_loaded.connect(self._on_volume_loaded)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.status_changed.connect(self.status_changed)

        # PLACEHOLDER: Start with synthetic data until a clinical CT is selected.
        QTimer.singleShot(0, self.controller.load_demo)

    @property
    def workflow_key(self) -> str:
        return "setup"

    @property
    def workflow_title(self) -> str:
        return "Setup"

    def _choose_file(self) -> None:
        initial_directory = environ.get("BART_DATA_DIR", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load CT / medical image",
            initial_directory,
            (
                "Medical images (*.nii *.nii.gz *.nrrd *.nhdr *.mha *.mhd *.dcm);;"
                "All files (*)"
            ),
        )
        if path:
            self.controller.load_file(path)

    def _choose_dicom_directory(self) -> None:
        initial_directory = environ.get("BART_DATA_DIR", str(Path.home()))
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select DICOM series folder",
            initial_directory,
        )
        if directory:
            self.controller.load_dicom_directory(directory)

    def _on_volume_loaded(self, volume: MedicalVolume) -> None:
        self.workspace.set_volume(volume)
        self.left_sidebar._emit_window_level()
        self.right_sidebar.set_ct_loaded(volume.name, is_demo=volume.is_demo)

        nx, ny, nz = volume.size
        if volume.is_demo:
            self.dataset_changed.emit(f"Demo CT    {nx} × {ny} × {nz}")
        else:
            self.dataset_changed.emit(f"DICOM    {nx} × {ny} × {nz}")
        self._set_state("ct", None if volume.is_demo else True)

    def set_case(
        self,
        case_id: str,
        modality: str,
        anatomy: str,
        region: str,
        patient: str,
    ) -> None:
        self.right_sidebar.set_case(case_id, modality, anatomy, region, patient)
        self._set_state("case", True)

    def set_robot_connected(self, connected: bool | None) -> None:
        self.left_sidebar.set_robot_arm_connected(connected)
        self.right_sidebar.set_robot_connected(connected)
        self._set_state("robot", connected)

    def set_end_effector_connected(self, connected: bool | None) -> None:
        self.left_sidebar.set_end_effector_connected(connected)
        self._set_state("end_effector", connected)

    def set_tracking_connected(self, connected: bool | None) -> None:
        self.right_sidebar.set_tracking_connected(connected)
        self._set_state("tracking", connected)

    def set_tool_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_tool_marker_tracked(tracked)
        self._set_state("tool_marker", tracked)

    def set_robot_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_robot_marker_tracked(tracked)
        self._set_state("robot_marker", tracked)

    def set_patient_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_patient_marker_tracked(tracked)
        self.right_sidebar.set_patient_marker_tracked(tracked)
        self._set_state("patient_marker", tracked)

    def _set_state(self, name: str, state: bool | None) -> None:
        self._setup_states[name] = state
        states = self._setup_states.values()
        if any(value is False for value in states):
            self.readiness_changed.emit("System attention required", "warning")
        elif all(value is True for value in states):
            self.readiness_changed.emit("System ready", "ready")
        else:
            self.readiness_changed.emit("Waiting for system status", "waiting")

    def _on_error(self, message: str) -> None:
        self.right_sidebar.add_log(f"Imaging error: {message}")
        QMessageBox.critical(self, "Imaging error", message)
