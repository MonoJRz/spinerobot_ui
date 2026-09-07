from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...controllers import ImagingController
from ...imaging.models import MedicalVolume
from ...visualization import ImagingWorkspace
from ...workflows import WorkflowPage


class ImagingPage(WorkflowPage):
    """Current standalone CT/MPR workspace."""

    def __init__(self, controller: ImagingController | None = None, parent=None):
        super().__init__(parent)

        self.controller = controller or ImagingController(parent=self)

        main = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.load_file_button = QPushButton("Load CT / Volume File")
        self.load_dicom_button = QPushButton("Load DICOM Folder")
        self.demo_button = QPushButton("Load Demo Phantom")
        self.reset_3d_button = QPushButton("Reset 3D Camera")

        self.dataset_label = QLabel("No image loaded")
        self.dataset_label.setStyleSheet("font-weight: 600;")

        toolbar.addWidget(self.load_file_button)
        toolbar.addWidget(self.load_dicom_button)
        toolbar.addWidget(self.demo_button)
        toolbar.addWidget(self.reset_3d_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.dataset_label)

        main.addLayout(toolbar)

        self.workspace = ImagingWorkspace()
        main.addWidget(self.workspace, 1)

        self.load_file_button.clicked.connect(self._choose_file)
        self.load_dicom_button.clicked.connect(self._choose_dicom_directory)
        self.demo_button.clicked.connect(self.controller.load_demo)
        self.reset_3d_button.clicked.connect(self.workspace.reset_3d_camera)

        self.controller.volume_loaded.connect(self._on_volume_loaded)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.status_changed.connect(self.status_changed)

        # Preserve the successful prototype behavior: always start with known test data.
        self.controller.load_demo()

    @property
    def workflow_key(self) -> str:
        return "imaging"

    @property
    def workflow_title(self) -> str:
        return "Imaging"

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
        self.dataset_label.setText(volume.name)

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Imaging error", message)
