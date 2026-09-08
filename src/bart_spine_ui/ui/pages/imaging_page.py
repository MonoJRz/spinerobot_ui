from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox

from ...controllers import ImagingController
from ...imaging.models import MedicalVolume
from ...visualization import ImagingWorkspace
from ...workflows import WorkflowPage
from ..setup_left_sidebar import SetupLeftSidebar
from ..setup_right_sidebar import SetupRightSidebar


class ImagingPage(WorkflowPage):
    """Setup stage: image import, CT display, system readiness, and four-view verification."""

    def __init__(self, controller: ImagingController | None = None, parent=None):
        super().__init__(parent)

        self.controller = controller or ImagingController(parent=self)

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

        self.controller.volume_loaded.connect(self._on_volume_loaded)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.status_changed.connect(self.status_changed)

        # PLACEHOLDER: Start with synthetic data until a clinical CT is selected.
        self.controller.load_demo()

    @property
    def workflow_key(self) -> str:
        return "setup"

    @property
    def workflow_title(self) -> str:
        return "Setup"

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load CT / medical image",
            str(Path.home()),
            (
                "Medical images (*.nii *.nii.gz *.nrrd *.nhdr *.mha *.mhd *.dcm);;"
                "All files (*)"
            ),
        )
        if path:
            self.controller.load_file(path)

    def _choose_dicom_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select DICOM series folder",
            str(Path.home()),
        )
        if directory:
            self.controller.load_dicom_directory(directory)

    def _on_volume_loaded(self, volume: MedicalVolume) -> None:
        self.workspace.set_volume(volume)
        self.left_sidebar._emit_window_level()
        self.right_sidebar.set_ct_loaded(volume.name, is_demo=volume.is_demo)

    # These entry points are ready for real robot/tracking controller signals.
    def set_robot_connected(self, connected: bool | None) -> None:
        self.left_sidebar.set_robot_arm_connected(connected)
        self.right_sidebar.set_robot_connected(connected)

    def set_end_effector_connected(self, connected: bool | None) -> None:
        self.left_sidebar.set_end_effector_connected(connected)

    def set_tracking_connected(self, connected: bool | None) -> None:
        self.right_sidebar.set_tracking_connected(connected)

    def set_tool_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_tool_marker_tracked(tracked)

    def set_robot_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_robot_marker_tracked(tracked)

    def set_patient_marker_tracked(self, tracked: bool | None) -> None:
        self.left_sidebar.set_patient_marker_tracked(tracked)
        self.right_sidebar.set_patient_marker_tracked(tracked)

    def _on_error(self, message: str) -> None:
        self.right_sidebar.add_log(f"Imaging error: {message}")
        QMessageBox.critical(self, "Imaging error", message)
